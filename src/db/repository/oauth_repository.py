"""
Repository helpers for the ``analysis_services.config_process_switch`` table.

Used for:
* Reading job-level config (email recipients, subject, etc.)
* Reading / updating OAuth tokens (access_token, refresh_token)
"""
from __future__ import annotations

import json
import logging
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


# ------------------------------------------------------------------
# Email config lookup (SMTP credentials + recipients)
# ------------------------------------------------------------------

def get_smtp_config(conn, process_name: str) -> Optional[Dict[str, Any]]:
    """
    Fetch SMTP credentials and email recipients for a job.

    Joins ``config_process_switch`` on ``config_smtp`` to retrieve
    SMTP host/port/username/password from the linked SMTP config row.

    Returns a dict with keys:
        ``email`` (TO addresses),
        ``cc_email``, ``bcc_email``,
        ``subject_body``,
        ``username``, ``password``, ``host``, ``port``
    """
    sql = """
        SELECT split_part(cps.email, ' | ', 1)          AS email,
               split_part(cps.email, ' | ', 2)          AS cc_email,
               split_part(cps.email, ' | ', 3)          AS bcc_email,
               split_part(cps.description, ' | ', 1)    AS subject_body,
               cpsb.description::json ->> 'username'    AS username,
               cpsb.description::json ->> 'password'    AS password,
               cpsb.description::json ->> 'host'        AS host,
               cpsb.description::json ->> 'port'        AS port
          FROM analysis_services.config_process_switch cps
          LEFT JOIN analysis_services.config_process_switch cpsb
              ON cps.config_smtp = cpsb.process_name
         WHERE cps.process_name = %s
           AND cps.switch = true
    """
    try:
        with conn.cursor() as cur:
            cur.execute(sql, (process_name,))
            row = cur.fetchone()
            if not row:
                logger.warning(f"No SMTP config for process_name='{process_name}'")
                return None
            cols = [d[0] for d in cur.description]
            return dict(zip(cols, row))
    except Exception:
        logger.exception("get_smtp_config failed")
        raise


# ------------------------------------------------------------------
# OAuth token read / write
# ------------------------------------------------------------------

def get_oauth_token(conn, process_name: str) -> Optional[Dict[str, str]]:
    """
    Fetch OAuth credentials from ``config_process_switch``.

    The ``description`` column is expected to be a JSON string containing
    at least ``access_token`` and ``refresh_token_new``.

    Returns::

        {
          "access_token":     "...",
          "refresh_token":    "...",
          "process_name":     "..."
        }
    """
    sql = """
        SELECT description::json ->> 'access_token'      AS access_token,
               description::json ->> 'refresh_token_new'  AS refresh_token,
               process_name
          FROM analysis_services.config_process_switch
         WHERE process_name = %s
    """
    try:
        with conn.cursor() as cur:
            cur.execute(sql, (process_name,))
            row = cur.fetchone()
            if not row:
                logger.warning(f"No OAuth token row for process_name='{process_name}'")
                return None
            cols = [d[0] for d in cur.description]
            return dict(zip(cols, row))
    except Exception:
        logger.exception("get_oauth_token failed")
        raise


def get_upload_config(conn, process_name: str) -> Optional[Dict[str, str]]:
    """
    Fetch OneDrive/SharePoint OAuth credentials from
    ``analysis_services.config_process_switch``.

    The ``description`` column stores a JSON with OAuth client
    credentials (same row used by the Kettle .ktr
    ``config_upload_onedrive_finance``)::

        {
          "tenant_id":     "fe822fb5-...",
          "client_id":     "24e2a753-...",
          "client_secret": "WE~7tser...",
          "scope":         "User.Read Files.Read offline_access Files.ReadWrite",
          "url_token":     "https://login.microsoftonline.com/${tenant_id}/oauth2/v2.0/token"
        }

    Note: ``drive_id`` and ``upload_folder`` are NOT stored in this DB
    row — they come from the YAML config instead.
    """
    sql = """
        SELECT description::json ->> 'tenant_id'      AS tenant_id,
               description::json ->> 'client_id'      AS client_id,
               description::json ->> 'client_secret'   AS client_secret,
               description::json ->> 'scope'           AS scope,
               description::json ->> 'url_token'       AS url_token
          FROM analysis_services.config_process_switch
         WHERE process_name = %s
    """
    try:
        with conn.cursor() as cur:
            cur.execute(sql, (process_name,))
            row = cur.fetchone()
            if not row:
                logger.warning(f"No upload config for process_name='{process_name}'")
                return None
            cols = [d[0] for d in cur.description]
            return dict(zip(cols, row))
    except Exception:
        logger.exception("get_upload_config failed")
        raise


# ------------------------------------------------------------------
# Process switch check / update
# ------------------------------------------------------------------

def get_process_switch(conn, process_name: str) -> bool:
    """
    Check whether a process is enabled in ``config_process_switch``.

    Returns ``True`` if the row exists and ``switch = true``,
    ``False`` otherwise.
    """
    sql = """
        SELECT switch
          FROM analysis_services.config_process_switch
         WHERE process_name = %s
    """
    try:
        with conn.cursor() as cur:
            cur.execute(sql, (process_name,))
            row = cur.fetchone()
            if not row:
                logger.warning(f"No config_process_switch row for '{process_name}'")
                return False
            return bool(row[0])
    except Exception:
        logger.exception("get_process_switch failed")
        raise


def update_last_execute_time(
    conn,
    process_name: str,
    execute_time=None,
    filenames: list | None = None,
) -> None:
    """
    Update ``last_execute_time`` (and optionally ``filename``) in
    ``config_process_switch``.

    Parameters
    ----------
    execute_time : datetime, optional
        Timestamp to record (in Jakarta timezone).
        Will strip timezone info before storage to preserve the Jakarta time value.
        Defaults to ``NOW() AT TIME ZONE 'Asia/Jakarta'`` if not supplied.
    filenames : list[dict], optional
        List of generated file metadata stored as JSON in ``filename``.
        Format: ``[{"filename": "report.xlsx", "type": "xlsx"}, ...]``
        If omitted, ``filename`` column is not updated.
    """
    execute_time_naive = None
    if execute_time is not None and hasattr(execute_time, 'tzinfo') and execute_time.tzinfo is not None:
        execute_time_naive = execute_time.replace(tzinfo=None)
    else:
        execute_time_naive = execute_time

    if filenames is not None:
        sql = """
            UPDATE analysis_services.config_process_switch
               SET last_execute_time = COALESCE(%s, NOW() AT TIME ZONE 'Asia/Jakarta'),
                   filename = %s
             WHERE process_name = %s
        """
        params = (execute_time_naive, json.dumps(filenames), process_name)
    else:
        sql = """
            UPDATE analysis_services.config_process_switch
               SET last_execute_time = COALESCE(%s, NOW() AT TIME ZONE 'Asia/Jakarta')
             WHERE process_name = %s
        """
        params = (execute_time_naive, process_name)

    try:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            conn.commit()
            logger.info(f"last_execute_time updated for '{process_name}'"
                        + (f" | filename={filenames}" if filenames else ""))
    except Exception:
        conn.rollback()
        logger.exception("update_last_execute_time failed")
        raise


def update_oauth_token(
    conn,
    process_name: str,
    access_token: str,
    refresh_token: str,
) -> None:
    """
    Persist refreshed OAuth tokens back to the database.

    Updates the JSON inside the ``description`` column, setting
    ``access_token`` and ``refresh_token_new`` while preserving any
    other keys already present.
    """
    sql = """
        UPDATE analysis_services.config_process_switch
           SET description = jsonb_set(
                  jsonb_set(
                      description::jsonb,
                      '{access_token}',
                      to_jsonb(%s::text)
                  ),
                  '{refresh_token_new}',
                  to_jsonb(%s::text)
               )::text
         WHERE process_name = %s
    """
    try:
        with conn.cursor() as cur:
            cur.execute(sql, (access_token, refresh_token, process_name))
            conn.commit()
            logger.info(f"OAuth tokens updated for process_name='{process_name}'")
    except Exception:
        conn.rollback()
        logger.exception("update_oauth_token failed")
        raise
