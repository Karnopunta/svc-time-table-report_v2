"""Reusable AWB batch processor for large IN-clause queries.

Splits a list of AWB numbers into configurable chunks and executes
a parameterised SQL query per batch, then merges all results into
a single DataFrame.  Designed for e-bill lookups and similar
enrichment joins where the AWB list can exceed 100 k items.
"""
from __future__ import annotations

import logging
import math
from typing import Iterator, List, Optional

import pandas as pd

from . import query_loader

logger = logging.getLogger(__name__)

DEFAULT_BATCH_SIZE = 10_001


class AWBBatcher:
    """Batch AWB processing for parameterised SQL queries.

    Parameters
    ----------
    conn
        A *psycopg2* connection for the **target** database (e.g. finance DB).
    sql_text : str
        Raw SQL containing a ``${AWB_NUMBER}`` placeholder.
    batch_size : int
        Maximum AWBs per batch (default 10 001).
    """

    def __init__(
        self,
        conn,
        sql_text: str,
        batch_size: int = DEFAULT_BATCH_SIZE,
    ) -> None:
        self.conn = conn
        self.sql_text = sql_text
        self.batch_size = batch_size

    # ------------------------------------------------------------------
    # Public helpers
    # ------------------------------------------------------------------

    @staticmethod
    def split_awbs(awbs: List[str], batch_size: int = DEFAULT_BATCH_SIZE) -> Iterator[List[str]]:
        """Yield successive chunks of *batch_size* AWBs."""
        for i in range(0, len(awbs), batch_size):
            yield awbs[i : i + batch_size]

    @staticmethod
    def format_awb_in_clause(awbs: List[str]) -> str:
        """Format AWB list for SQL ``IN (...)`` clause.

        Returns string like ``'10008683870901','10008759184776'``
        (without outer parentheses — the SQL template provides those).
        """
        return ",".join(f"'{a}'" for a in awbs)

    # ------------------------------------------------------------------
    # Core: batched fetch
    # ------------------------------------------------------------------

    def fetch_data_batched(
        self,
        awbs: List[str],
        params: Optional[dict] = None,
    ) -> pd.DataFrame:
        """Execute the SQL query in batches and return merged results.

        Parameters
        ----------
        awbs : list[str]
            Full list of AWB numbers to look up.
        params : dict, optional
            Additional ``${PLACEHOLDER}`` values (e.g. STARTDATE, ENDDATE).

        Returns
        -------
        pd.DataFrame
            Concatenated results from all batches.
        """
        if not awbs:
            logger.warning("Empty AWB list – returning empty DataFrame")
            return pd.DataFrame()

        params = params or {}
        total = len(awbs)
        total_batches = math.ceil(total / self.batch_size)
        logger.info(
            f"AWB batch fetch: {total} AWBs -> {total_batches} batch(es) "
            f"of {self.batch_size}"
        )

        all_dfs: List[pd.DataFrame] = []

        for batch_num, batch_awbs in enumerate(
            self.split_awbs(awbs, self.batch_size), 1
        ):
            awb_clause = self.format_awb_in_clause(batch_awbs)

            batch_params = {**params, "AWB_NUMBER": awb_clause}
            rendered_sql = query_loader.inject_parameters(
                self.sql_text, batch_params
            )

            df = pd.read_sql(rendered_sql, self.conn)
            all_dfs.append(df)
            logger.info(
                f"  Batch {batch_num}/{total_batches}: "
                f"{len(batch_awbs)} AWBs -> {len(df)} rows"
            )

        if not all_dfs:
            logger.warning("No data returned from any batch")
            return pd.DataFrame()

        combined = pd.concat(all_dfs, ignore_index=True)
        logger.info(f"AWB batch fetch complete: {len(combined)} total rows")
        return combined
