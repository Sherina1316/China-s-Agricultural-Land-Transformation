"""Configuration loading helpers for the reproducible workflow."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


def load_config(path: str | Path) -> dict[str, Any]:
    """Load a YAML configuration file."""
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Configuration file not found: {path}")
    with path.open("r", encoding="utf-8") as f:
        config = yaml.safe_load(f)
    if not isinstance(config, dict):
        raise ValueError("Configuration file must contain a YAML mapping.")
    return config


def get_nested(config: dict[str, Any], *keys: str, default: Any = None) -> Any:
    """Safely retrieve nested configuration values."""
    cur: Any = config
    for key in keys:
        if not isinstance(cur, dict) or key not in cur:
            return default
        cur = cur[key]
    return cur


def ensure_output_dir(config: dict[str, Any]) -> Path:
    """Return and create the configured output directory."""
    out = Path(get_nested(config, "paths", "outputs", default="outputs"))
    out.mkdir(parents=True, exist_ok=True)
    return out
