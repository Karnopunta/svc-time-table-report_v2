"""
Two-layer configuration helper.

Layer 1 – ``.env``   (secrets, loaded via python-dotenv)
Layer 2 – YAML file  (everything else, env-specific)

Sensitive values in the YAML may reference env-vars with the ``${VAR}``
syntax; if found they are resolved at load time.
"""
from __future__ import annotations

import logging
import os
import re
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

_ENV_VAR_RE = re.compile(r"\$\{(\w+)\}")


def _resolve_env_vars(value: str) -> str:
    """Replace ``${VAR}`` tokens in *value* with ``os.environ[VAR]``."""
    def _replacer(match: re.Match) -> str:
        var = match.group(1)
        env_val = os.getenv(var)
        if env_val is None:
            logger.warning(f"Env var ${{{var}}} not set – left as-is")
            return match.group(0)
        return env_val

    return _ENV_VAR_RE.sub(_replacer, value)


def resolve_config(cfg: Dict[str, Any]) -> Dict[str, Any]:
    """
    Walk a nested dict and resolve ``${VAR}`` in all string values.

    Returns a *new* dict (shallow-copied at each level).
    """
    resolved: Dict[str, Any] = {}
    for key, val in cfg.items():
        if isinstance(val, dict):
            resolved[key] = resolve_config(val)
        elif isinstance(val, str):
            resolved[key] = _resolve_env_vars(val)
        elif isinstance(val, list):
            resolved[key] = [
                _resolve_env_vars(v) if isinstance(v, str) else v for v in val
            ]
        else:
            resolved[key] = val
    return resolved


def resolve_path(path_template: str, config: Dict[str, Any]) -> str:
    """
    Resolve path variables like ``${PROJECT_ROOT}``, ``${DATE}``.

    Also replaces env-vars (``${FILE_PATH}`` etc.).
    """
    result = path_template

    # Built-in tokens
    project_root = config.get("PROJECT_ROOT", os.getcwd())
    result = result.replace("${PROJECT_ROOT}", project_root)

    # Additional variables supplied in config
    for key, val in config.items():
        if isinstance(val, str):
            result = result.replace(f"${{{key}}}", val)

    # Fall back to env-vars for anything still unresolved
    result = _resolve_env_vars(result)
    return result


def get_nested(cfg: Dict, *keys, default=None):
    """
    Safely traverse a nested dict.

    >>> get_nested(cfg, 'SMTP', 'HOST', default='localhost')
    """
    current = cfg
    for k in keys:
        if isinstance(current, dict):
            current = current.get(k)
        else:
            return default
        if current is None:
            return default
    return current


def parse_pipe_separated(text: Optional[str]) -> Dict[str, Optional[str]]:
    """
    Parse the Pentaho-style ``'to | cc | bcc'`` email string.

    Returns ``{'to': ..., 'cc': ..., 'bcc': ...}`` (any may be *None*).
    """
    if not text:
        return {"to": None, "cc": None, "bcc": None}

    parts = [p.strip() or None for p in text.split("|")]
    return {
        "to":  parts[0] if len(parts) > 0 else None,
        "cc":  parts[1] if len(parts) > 1 else None,
        "bcc": parts[2] if len(parts) > 2 else None,
    }
