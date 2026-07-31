from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


CONFIG_DIR = Path(__file__).resolve().parent


def _load_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"Configuration file not found: {path}")
    with path.open("r", encoding="utf-8") as file:
        data = yaml.safe_load(file) or {}
    if not isinstance(data, dict):
        raise ValueError(f"Configuration root must be a mapping: {path}")
    return data


def load_sources(path: Path | None = None) -> dict[str, Any]:
    """Load source definitions without starting network or scraping work."""
    return _load_yaml(path or CONFIG_DIR / "sources.yaml")


def load_keywords(path: Path | None = None) -> dict[str, Any]:
    """Load the weighted keyword taxonomy."""
    return _load_yaml(path or CONFIG_DIR / "keywords.yaml")


def load_company_watchlist(path: Path | None = None) -> dict[str, Any]:
    """Load identities, Southeast Asia footprints and approved mappings."""
    return _load_yaml(path or CONFIG_DIR / "company_watchlist.yaml")
