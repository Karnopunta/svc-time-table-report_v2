"""
Helpers for per-run artifacts (manifests, outputs).
"""
from __future__ import annotations

import json
import os
from typing import Any, Dict


def init_run_dir(base_dir: str, run_id: int | str) -> str:
    """
    Create and return the per-run directory path.
    """
    run_dir = os.path.join(base_dir, str(run_id))
    os.makedirs(run_dir, exist_ok=True)
    return run_dir


def write_run_manifest(run_dir: str, payload: Dict[str, Any]) -> str:
    """
    Write a manifest.json file into the run directory.
    """
    manifest_path = os.path.join(run_dir, "manifest.json")
    with open(manifest_path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2)
    return manifest_path
