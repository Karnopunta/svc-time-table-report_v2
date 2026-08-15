"""
Microsoft identity-platform OAuth 2.0 token manager.

* Reads current tokens from the database via :mod:`oauth_repository`.
* Auto-refreshes when expired (or on 401 from Graph API).
* Writes the new pair back to the database.
"""
from __future__ import annotations

import logging
import time
from typing import Dict, Optional

import requests

from ..db.repository import oauth_repository

logger = logging.getLogger(__name__)

# Microsoft token endpoint template
_TOKEN_URL = "https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token"


def _refresh_token_request(
    tenant_id: str,
    client_id: str,
    client_secret: str,
    refresh_token: str,
    scope: str = "https://graph.microsoft.com/.default offline_access",
) -> Dict[str, str]:
    """
    Call the Microsoft token endpoint to exchange a refresh token for
    a fresh access + refresh token pair.

    Raises on HTTP errors.
    """
    url = _TOKEN_URL.format(tenant_id=tenant_id)
    payload = {
        "grant_type":    "refresh_token",
        "client_id":     client_id,
        "client_secret": client_secret,
        "refresh_token": refresh_token,
        "scope":         scope,
    }

    resp = requests.post(url, data=payload, timeout=30)
    resp.raise_for_status()

    data = resp.json()
    return {
        "access_token":  data["access_token"],
        "refresh_token": data.get("refresh_token", refresh_token),
        "expires_in":    data.get("expires_in", 3600),
    }


def get_valid_token(
    conn,
    process_name: str,
    tenant_id: str,
    client_id: str,
    client_secret: str,
    force_refresh: bool = False,
) -> str:
    """
    Return a (hopefully) valid access token.

    1. Read current tokens from DB.
    2. If *force_refresh* is ``True`` → refresh immediately.
    3. Otherwise return the stored access token (Graph API will 401 if
       it's really expired, and the caller should retry with
       ``force_refresh=True``).

    The refreshed pair is persisted back to the DB so the next call
    picks it up.
    """
    token_row = oauth_repository.get_oauth_token(conn, process_name)
    if not token_row:
        raise RuntimeError(f"No OAuth token found for process_name='{process_name}'")

    access_token = token_row["access_token"]
    refresh_tok = token_row["refresh_token"]

    if not force_refresh and access_token:
        return access_token

    logger.info(f"Refreshing OAuth token for '{process_name}' …")
    new_tokens = _refresh_token_request(
        tenant_id=tenant_id,
        client_id=client_id,
        client_secret=client_secret,
        refresh_token=refresh_tok,
    )

    oauth_repository.update_oauth_token(
        conn,
        process_name=process_name,
        access_token=new_tokens["access_token"],
        refresh_token=new_tokens["refresh_token"],
    )

    logger.info("OAuth token refreshed and persisted to DB")
    return new_tokens["access_token"]
