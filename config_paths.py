"""
Helpers for locating configuration files (API keys, credentials, etc.).

Supports the following precedence when resolving a file:
1. Environment variable pointing directly to the file path
2. `<repo_root>/config/<filename>`
3. `<repo_root>/<filename>` (legacy location)
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Optional


def _find_repo_root(marker: str = "pyproject.toml") -> Path:
    """Walk upwards from this file to locate the repository root."""
    current = Path(__file__).resolve()
    for parent in [current] + list(current.parents):
        if (parent / marker).exists():
            return parent
    return current.parent  # Fallback: best-effort


REPO_ROOT = _find_repo_root()
CONFIG_DIR = REPO_ROOT / "config"


def _resolve_candidate(filename: str, env_var: Optional[str]) -> Path:
    """Return the first existing path for filename based on precedence."""
    env_value = os.environ.get(env_var or "")
    if env_value:
        env_path = Path(env_value).expanduser()
        if env_path.is_file():
            return env_path

    config_path = CONFIG_DIR / filename
    if config_path.is_file():
        return config_path

    legacy_path = REPO_ROOT / filename
    if legacy_path.is_file():
        return legacy_path

    raise FileNotFoundError(
        f"Could not find {filename}. Checked env var {env_var or 'N/A'}, "
        f"{config_path}, and {legacy_path}."
    )


def read_secret_text(filename: str, env_var: Optional[str] = None) -> str:
    """Read a UTF-8 text secret (stripping whitespace)."""
    path = _resolve_candidate(filename, env_var)
    return path.read_text(encoding="utf-8").strip()


def read_secret_bytes(filename: str, env_var: Optional[str] = None) -> bytes:
    """Read a binary secret."""
    path = _resolve_candidate(filename, env_var)
    return path.read_bytes()
