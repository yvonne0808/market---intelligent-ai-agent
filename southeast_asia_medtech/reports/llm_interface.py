from __future__ import annotations

from typing import Any


def generate_llm_summary(
    article: dict[str, Any],
    provider: Any | None = None,
) -> str:
    """Reserved extension point; Step 5 deliberately performs no provider call."""
    del article, provider
    return ""
