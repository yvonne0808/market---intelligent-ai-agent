from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


def load_website_sources(config_path: Path) -> list[dict[str, Any]]:
    """Load enabled website sources from website_sources.yaml."""
    if not config_path.exists():
        raise FileNotFoundError(f"Website source config not found: {config_path}")

    with config_path.open("r", encoding="utf-8") as file:
        config = yaml.safe_load(file) or {}

    sources = config.get("sources", [])
    if not isinstance(sources, list):
        raise ValueError("website_sources.yaml must contain a list field named 'sources'.")

    enabled_sources: list[dict[str, Any]] = []
    for source in sources:
        if not isinstance(source, dict):
            continue
        if source.get("enabled") is True:
            source.setdefault("selectors", {})
            enabled_sources.append(source)

    return enabled_sources
