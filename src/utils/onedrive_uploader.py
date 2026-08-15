"""
OneDrive / SharePoint file uploader via Microsoft Graph API.

Handles:
* Uploading files (small ≤4 MB via simple PUT, large via upload session).
* Chunked upload for large files (50 MB chunks, matching Pentaho pattern).
* Creating share links for files and folders.
* Auto-retry with token refresh on 401.

Configuration sources:
* OAuth credentials (tenant_id, client_id, …) → DB ``config_process_switch``
* Drive ID and upload folder              → YAML ``ONEDRIVE`` section
* Access / refresh tokens                 → DB ``config_process_switch``
"""
from __future__ import annotations

import json
import logging
import os
from urllib.parse import quote
from typing import Dict, Optional

import requests

from . import oauth_manager
from ..db.repository.oauth_repository import get_upload_config

logger = logging.getLogger(__name__)

GRAPH_BASE = "https://graph.microsoft.com/v1.0"
SIMPLE_UPLOAD_LIMIT = 4 * 1024 * 1024  # 4 MB


# ------------------------------------------------------------------
# Config resolution (DB-first, YAML fallback)
# ------------------------------------------------------------------

def _resolve_config(conn, config: Dict) -> Dict:
    """
    Resolve OneDrive configuration from two sources:

    * **DB**   → OAuth credentials (tenant_id, client_id, client_secret,
      scope, url_token) via ``UPLOAD_CONFIG_NAME``.
    * **YAML** → drive_id, upload_folder, token_name.

    This matches the Pentaho/Kettle pattern where OAuth credentials live
    in ``config_process_switch`` and the drive path is configured per job.
    """
    onedrive_cfg = config.get("ONEDRIVE", {})
    upload_config_name = onedrive_cfg.get("UPLOAD_CONFIG_NAME")

    db_cfg = {}
    if upload_config_name:
        db_cfg = get_upload_config(conn, upload_config_name) or {}
        if db_cfg:
            logger.info(f"OAuth credentials loaded from DB: {upload_config_name}")

    return {
        # OAuth credentials from DB
        "tenant_id":     db_cfg.get("tenant_id", ""),
        "client_id":     db_cfg.get("client_id", ""),
        "client_secret": db_cfg.get("client_secret", ""),
        "scope":         db_cfg.get("scope", "User.Read Files.Read offline_access Files.ReadWrite"),
        "url_token":     db_cfg.get("url_token", ""),
        # Drive path from YAML
        "drive_id":      onedrive_cfg.get("DRIVE_ID", ""),
        "upload_folder": onedrive_cfg.get("UPLOAD_FOLDER", "/Reports"),
        "token_name":    onedrive_cfg.get("TOKEN_CONFIG_NAME", "config_token_finance"),
    }


def _drive_url(resolved: Dict, config: Dict) -> str:
    """Build the Graph API drive base URL."""
    drive_id = resolved["drive_id"]
    site_id = config.get("ONEDRIVE", {}).get("SITE_ID")

    if drive_id:
        return f"{GRAPH_BASE}/drives/{drive_id}"
    if site_id:
        return f"{GRAPH_BASE}/sites/{site_id}/drive"
    return f"{GRAPH_BASE}/me/drive"


# ------------------------------------------------------------------
# Internal helpers
# ------------------------------------------------------------------

def _headers(access_token: str) -> Dict[str, str]:
    return {"Authorization": f"Bearer {access_token}"}


def _normalize_remote_folder(remote_folder: str) -> str:
    """Normalize remote folder path to forward-slash style without leading/trailing slash."""
    return (remote_folder or "").replace("\\", "/").strip("/")


def _item_by_path(drive_url: str, path: str, access_token: str) -> requests.Response:
    """Retrieve a drive item by path."""
    encoded = quote(path, safe="/")
    url = f"{drive_url}/root:/{encoded}"
    return requests.get(url, headers=_headers(access_token), timeout=30)


def _ensure_remote_folder_exists(
    drive_url: str,
    remote_folder: str,
    access_token: str,
) -> None:
    """Create remote folder hierarchy when it does not exist."""
    normalized = _normalize_remote_folder(remote_folder)
    if not normalized:
        return

    current = ""
    for segment in normalized.split("/"):
        current = f"{current}/{segment}" if current else segment
        exists_resp = _item_by_path(drive_url, current, access_token)
        if exists_resp.status_code == 200:
            continue
        if exists_resp.status_code != 404:
            exists_resp.raise_for_status()

        parent = current.rsplit("/", 1)[0] if "/" in current else ""
        if parent:
            parent_encoded = quote(parent, safe="/")
            create_url = f"{drive_url}/root:/{parent_encoded}:/children"
        else:
            create_url = f"{drive_url}/root/children"

        body = {
            "name": segment,
            "folder": {},
            "@microsoft.graph.conflictBehavior": "fail",
        }
        create_resp = requests.post(
            create_url,
            headers={**_headers(access_token), "Content-Type": "application/json"},
            json=body,
            timeout=30,
        )

        if create_resp.status_code in (200, 201, 409):
            # 409 means folder already exists (created concurrently) and is safe to continue.
            continue
        create_resp.raise_for_status()


def _upload_simple(
    file_path: str,
    remote_path: str,
    access_token: str,
    drive_url: str,
) -> Dict:
    """PUT ≤ 4 MB file."""
    url = f"{drive_url}/root:/{remote_path}:/content"
    with open(file_path, "rb") as fh:
        resp = requests.put(
            url,
            headers={**_headers(access_token), "Content-Type": "application/octet-stream"},
            data=fh,
            timeout=120,
        )
    resp.raise_for_status()
    return resp.json()


def _upload_session(
    file_path: str,
    remote_path: str,
    access_token: str,
    drive_url: str,
    chunk_size: int = 50 * 1024 * 1024,  # 50 MB chunks (matches Pentaho)
) -> Dict:
    """Resumable upload session for files > 4 MB.

    Mirrors the Pentaho/Kettle chunked upload pattern:
    1. POST createUploadSession → get uploadUrl
    2. Split file into 50 MB chunks
    3. PUT each chunk with Content-Range header (sequential)
    4. Last chunk response contains the file metadata
    """
    filename = os.path.basename(file_path)

    # 1. Create upload session
    url = f"{drive_url}/root:/{remote_path}:/createUploadSession"
    body = {
        "@microsoft.graph.conflictBehavior": "replace",
        "description": "upload",
        "fileSystemInfo": {"@odata.type": "microsoft.graph.fileSystemInfo"},
        "name": filename,
    }
    resp = requests.post(
        url,
        headers={**_headers(access_token), "Content-Type": "application/json"},
        json=body,
        timeout=30,
    )
    resp.raise_for_status()
    upload_url = resp.json()["uploadUrl"]
    logger.info(f"Upload session created for {filename}")

    # 2. Upload chunks sequentially
    file_size = os.path.getsize(file_path)
    with open(file_path, "rb") as fh:
        offset = 0
        chunk_num = 0
        while offset < file_size:
            chunk = fh.read(chunk_size)
            end = offset + len(chunk) - 1
            chunk_num += 1
            headers = {
                "Content-Length": str(len(chunk)),
                "Content-Range": f"bytes {offset}-{end}/{file_size}",
                "Content-Type": "application/octet-stream",
            }
            resp = requests.put(upload_url, headers=headers, data=chunk, timeout=300)
            resp.raise_for_status()
            pct = int((end + 1) / file_size * 100)
            logger.info(f"  chunk {chunk_num}: bytes {offset}-{end} ({pct}%)")
            offset += len(chunk)

    return resp.json()


# ------------------------------------------------------------------
# Public API
# ------------------------------------------------------------------

def upload_file(
    file_path: str,
    remote_folder: str,
    conn,
    config: Dict,
    access_token: Optional[str] = None,
) -> Dict:
    """
    Upload *file_path* to OneDrive / SharePoint.

    All credentials and destination settings are resolved from the
    database when ``ONEDRIVE.UPLOAD_CONFIG_NAME`` is configured in YAML.
    This mirrors the Kettle .ktr pattern where ``config_process_switch``
    stores tenant_id, client_id, client_secret, drive_id, and
    upload_folder in a single JSON row.

    Parameters
    ----------
    file_path : str
        Local path to the file.
    remote_folder : str
        Destination folder on OneDrive.  When empty/None, the value
        stored in the DB config row (``upload_folder``) is used.
    conn
        DB connection (for token refresh and config lookup).
    config : dict
        YAML config.  Only ``ONEDRIVE.UPLOAD_CONFIG_NAME`` and
        ``ONEDRIVE.TOKEN_CONFIG_NAME`` are required when using DB mode.
    access_token : str, optional
        Pre-fetched token.  Obtained from DB if not supplied.

    Returns
    -------
    dict  with at least ``id``, ``name``, ``webUrl``.
    """
    resolved = _resolve_config(conn, config)
    drive = _drive_url(resolved, config)

    # Use DB upload_folder when caller didn't provide one
    if not remote_folder:
        remote_folder = resolved["upload_folder"]
    remote_folder = _normalize_remote_folder(remote_folder)

    filename = os.path.basename(file_path)
    remote_path = f"{remote_folder}/{filename}" if remote_folder else filename
    file_size = os.path.getsize(file_path)

    # Get token if not provided
    if not access_token:
        access_token = oauth_manager.get_valid_token(
            conn=conn,
            process_name=resolved["token_name"],
            tenant_id=resolved["tenant_id"],
            client_id=resolved["client_id"],
            client_secret=resolved["client_secret"],
        )

    try:
        _ensure_remote_folder_exists(drive, remote_folder, access_token)
    except requests.HTTPError as exc:
        if exc.response is not None and exc.response.status_code == 401:
            logger.warning("401 while ensuring folder path – refreshing token and retrying…")
            access_token = oauth_manager.get_valid_token(
                conn=conn,
                process_name=resolved["token_name"],
                tenant_id=resolved["tenant_id"],
                client_id=resolved["client_id"],
                client_secret=resolved["client_secret"],
                force_refresh=True,
            )
            _ensure_remote_folder_exists(drive, remote_folder, access_token)
        else:
            raise

    logger.info(f"Uploading {filename} ({file_size:,} bytes) -> {remote_path}")

    upload_fn = _upload_simple if file_size <= SIMPLE_UPLOAD_LIMIT else _upload_session

    try:
        result = upload_fn(file_path, remote_path, access_token, drive)
    except requests.HTTPError as exc:
        if exc.response is not None and exc.response.status_code == 401:
            logger.warning("401 – refreshing token and retrying upload…")
            access_token = oauth_manager.get_valid_token(
                conn=conn,
                process_name=resolved["token_name"],
                tenant_id=resolved["tenant_id"],
                client_id=resolved["client_id"],
                client_secret=resolved["client_secret"],
                force_refresh=True,
            )
            result = upload_fn(file_path, remote_path, access_token, drive)
        else:
            raise

    logger.info(f"Upload complete: {result.get('webUrl', result.get('id'))}")
    return result


def create_share_link(
    item_id: str,
    conn,
    config: Dict,
    access_token: Optional[str] = None,
    link_type: str = "view",
    link_scope: str = "organization",
) -> str:
    """
    Create a sharing link for a Drive item and return its URL.
    """
    resolved = _resolve_config(conn, config)
    drive_id = resolved["drive_id"]
    site_id = config.get("ONEDRIVE", {}).get("SITE_ID")

    if drive_id:
        url = f"{GRAPH_BASE}/drives/{drive_id}/items/{item_id}/createLink"
    elif site_id:
        url = f"{GRAPH_BASE}/sites/{site_id}/drive/items/{item_id}/createLink"
    else:
        url = f"{GRAPH_BASE}/me/drive/items/{item_id}/createLink"

    if not access_token:
        access_token = oauth_manager.get_valid_token(
            conn=conn,
            process_name=resolved["token_name"],
            tenant_id=resolved["tenant_id"],
            client_id=resolved["client_id"],
            client_secret=resolved["client_secret"],
        )

    body = {"type": link_type, "scope": link_scope}
    resp = requests.post(url, headers=_headers(access_token), json=body, timeout=30)
    resp.raise_for_status()

    link = resp.json().get("link", {}).get("webUrl", "")
    logger.info(f"Share link created: {link}")
    return link


def create_folder_share_link(
    conn,
    config: Dict,
    access_token: Optional[str] = None,
    link_type: str = "view",
    link_scope: str = "organization",
) -> str:
    """
    Create a sharing link for the upload *folder* (not a specific file).

    Mirrors Pentaho's ``urlFolderShareString``::

        /drives/{drive_id}/root:/{folder}:/createLink
    """
    resolved = _resolve_config(conn, config)
    drive_id = resolved["drive_id"]
    folder = resolved["upload_folder"].strip("/")

    if drive_id:
        url = f"{GRAPH_BASE}/drives/{drive_id}/root:/{folder}:/createLink"
    else:
        url = f"{GRAPH_BASE}/me/drive/root:/{folder}:/createLink"

    if not access_token:
        access_token = oauth_manager.get_valid_token(
            conn=conn,
            process_name=resolved["token_name"],
            tenant_id=resolved["tenant_id"],
            client_id=resolved["client_id"],
            client_secret=resolved["client_secret"],
        )

    body = {"type": link_type, "scope": link_scope}
    resp = requests.post(url, headers=_headers(access_token), json=body, timeout=30)
    resp.raise_for_status()

    link = resp.json().get("link", {}).get("webUrl", "")
    logger.info(f"Folder share link created: {link}")
    return link
