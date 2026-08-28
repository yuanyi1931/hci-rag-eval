from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG_PATH = ROOT / "config.yaml"


def load_config(config_path: str | Path | None = None) -> dict[str, Any]:
    """Load the project YAML config and return it as a nested Python dictionary."""
    resolved_path = Path(config_path) if config_path is not None else DEFAULT_CONFIG_PATH
    with resolved_path.open("r", encoding="utf-8") as fh:
        config = yaml.safe_load(fh) or {}
    if not isinstance(config, dict):
        raise TypeError(f"Config file must contain a dictionary at the top level: {resolved_path}")
    return config
