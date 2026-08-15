"""SQL query loader – read .sql files, inject ${PARAM} placeholders."""
import json
import os
import re
import logging
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


def load_manifest(manifest_path: str) -> List[Dict]:
    """
    Load and return the queries list from a manifest.json file.

    Expected format::

        {
          "template_file": "data/template_files/template.xlsx",
          "template_header_rows": 2,
          "queries": [
            {"name": "p01", "file": "query_p01.sql", "sheet_name": "P01"}
          ]
        }
    """
    if not os.path.exists(manifest_path):
        raise FileNotFoundError(f"Manifest not found: {manifest_path}")

    with open(manifest_path, "r", encoding="utf-8") as fh:
        data = json.load(fh)

    queries = data.get("queries", [])
    logger.info(f"Manifest loaded: {len(queries)} queries from {manifest_path}")
    return queries


def load_manifest_meta(manifest_path: str) -> Dict:
    """
    Load template metadata from manifest (template_file, template_header_rows).

    Returns dict with keys:
      - template_file: relative path to template xlsx (or None)
      - template_header_rows: number of header rows in template (default 1)
    """
    if not os.path.exists(manifest_path):
        raise FileNotFoundError(f"Manifest not found: {manifest_path}")

    with open(manifest_path, "r", encoding="utf-8") as fh:
        data = json.load(fh)

    base_dir = os.path.dirname(manifest_path)
    template_rel = data.get("template_file")
    template_abs = None
    if template_rel:
        # resolve relative to project root (grandparent of sql dir)
        # manifest lives in src/sql/ -> parent = src/ -> grandparent = project root
        project_root = os.path.dirname(os.path.dirname(base_dir))
        template_abs = os.path.normpath(os.path.join(project_root, template_rel))

    return {
        "template_file": template_abs,
        "template_header_rows": data.get("template_header_rows", 1),
    }


def load_query_file(sql_path: str) -> str:
    """Read a single .sql file and return its content."""
    if not os.path.exists(sql_path):
        raise FileNotFoundError(f"SQL file not found: {sql_path}")

    with open(sql_path, "r", encoding="utf-8") as fh:
        return fh.read()


def inject_parameters(query_text: str, params: Dict) -> str:
    """
    Replace ``${PARAM_NAME}`` placeholders with values from *params*.

    String values are **NOT** automatically quoted – the SQL file should
    already contain the surrounding single-quotes where needed, e.g.::

        WHERE date >= '${STARTDATE}'

    This keeps the loader agnostic about SQL dialects.
    """
    result = query_text
    for key, value in params.items():
        placeholder = f"${{{key}}}"
        replacement = str(value) if value is not None else "NULL"
        result = result.replace(placeholder, replacement)
        logger.debug(f"Injected {placeholder} -> {replacement}")

    unresolved = re.findall(r"\$\{(\w+)\}", result)
    if unresolved:
        logger.warning(f"Unresolved placeholders: {unresolved}")

    return result


def load_all_queries(manifest_path: str) -> List[Dict]:
    """
    Load every query listed in the manifest *with* its raw SQL content.

    Returns a list of dicts, each having::

        {
          "name":       "summary",
          "file":       "query_summary.sql",
          "sheet_name": "Summary",
          "sql":        "<raw SQL text>"
        }
    """
    entries = load_manifest(manifest_path)
    base_dir = os.path.dirname(manifest_path)

    results: List[Dict] = []
    for entry in entries:
        sql_path = os.path.join(base_dir, entry["file"])
        sql_content = load_query_file(sql_path)
        results.append({
            "name":       entry["name"],
            "file":       entry["file"],
            "sheet_name": entry["sheet_name"],
            "sql":        sql_content,
        })

    logger.info(f"Loaded {len(results)} SQL queries from manifest")
    return results


def validate_manifest(manifest_path: str) -> bool:
    """
    Check that every file referenced in the manifest actually exists.

    Raises on the first missing file. Returns ``True`` when everything is OK.
    """
    entries = load_manifest(manifest_path)
    base_dir = os.path.dirname(manifest_path)

    for entry in entries:
        for required_key in ("name", "file", "sheet_name"):
            if required_key not in entry:
                raise ValueError(f"Manifest entry missing '{required_key}': {entry}")

        sql_path = os.path.join(base_dir, entry["file"])
        if not os.path.exists(sql_path):
            raise FileNotFoundError(f"SQL file not found: {sql_path}")

        logger.info(f"  [OK] {entry['name']} -> {entry['file']} (sheet: {entry['sheet_name']})")

    return True


# ---------------------------------------------------------------------------
# Prep-queries support (staging / data-preparation layer)
# ---------------------------------------------------------------------------

def load_staging_config(manifest_path: str) -> Dict:
    """
    Load staging table configuration from the manifest.

    Returns dict with keys:
      - temp_schema: schema name (e.g. 'dad_dev')
      - temp_table:  table name  (e.g. 'temp_week_robotic_summary')

    Returns empty dict when ``staging`` is not defined in the manifest.
    """
    with open(manifest_path, "r", encoding="utf-8") as fh:
        data = json.load(fh)

    staging = data.get("staging", {})
    if staging:
        logger.info(f"Staging config: {staging['temp_schema']}.{staging['temp_table']}")
    return staging


def load_prep_queries(manifest_path: str) -> List[Dict]:
    """
    Load prep queries from the manifest, sorted by *sequence*.

    Each returned dict has::

        {
          "name":     "robotic",
          "file":     "query_robotic.sql",
          "sequence": 1,
          "sql":      "<raw SQL text>"
        }

    Returns an empty list when ``prep_queries`` is not defined.
    """
    with open(manifest_path, "r", encoding="utf-8") as fh:
        data = json.load(fh)

    entries = data.get("prep_queries", [])
    if not entries:
        logger.info("No prep_queries defined in manifest")
        return []

    base_dir = os.path.dirname(manifest_path)
    results: List[Dict] = []

    for entry in sorted(entries, key=lambda e: e.get("sequence", 0)):
        sql_path = os.path.join(base_dir, entry["file"])
        if not os.path.exists(sql_path):
            raise FileNotFoundError(f"Prep SQL file not found: {sql_path}")

        sql_content = load_query_file(sql_path)
        results.append({
            "name":     entry["name"],
            "file":     entry["file"],
            "sequence": entry.get("sequence", 0),
            "sql":      sql_content,
        })
        logger.info(f"  [OK] prep: {entry['name']} -> {entry['file']} (seq {entry.get('sequence', 0)})")

    logger.info(f"Loaded {len(results)} prep queries from manifest")
    return results


# ---------------------------------------------------------------------------
# Region-query support (region-aware jobs)
# ---------------------------------------------------------------------------

def load_region_query(manifest_path: str) -> Optional[str]:
    """
    Load the region query SQL from the manifest ``region_query`` section.

    Returns the raw SQL text, or ``None`` when no ``region_query`` is defined.
    """
    with open(manifest_path, "r", encoding="utf-8") as fh:
        data = json.load(fh)

    region_cfg = data.get("region_query")
    if not region_cfg:
        logger.info("No region_query defined in manifest")
        return None

    base_dir = os.path.dirname(manifest_path)
    sql_path = os.path.join(base_dir, region_cfg["file"])
    sql_content = load_query_file(sql_path)
    logger.info(f"Region query loaded: {region_cfg['name']} -> {region_cfg['file']}")
    return sql_content


def load_awb_query(manifest_path: str) -> Optional[str]:
    """
    Load the AWB-list query SQL from the manifest ``awb_query`` section.

    Returns the raw SQL text, or ``None`` when no ``awb_query`` is defined.
    """
    with open(manifest_path, "r", encoding="utf-8") as fh:
        data = json.load(fh)

    awb_cfg = data.get("awb_query")
    if not awb_cfg:
        logger.info("No awb_query defined in manifest")
        return None

    base_dir = os.path.dirname(manifest_path)
    sql_path = os.path.join(base_dir, awb_cfg["file"])
    sql_content = load_query_file(sql_path)
    logger.info(f"AWB query loaded: {awb_cfg['name']} -> {awb_cfg['file']}")
    return sql_content


def load_batch_size(manifest_path: str) -> int:
    """Return the ``batch_size`` from the manifest, default 3000."""
    with open(manifest_path, "r", encoding="utf-8") as fh:
        data = json.load(fh)
    return data.get("batch_size", 3000)
