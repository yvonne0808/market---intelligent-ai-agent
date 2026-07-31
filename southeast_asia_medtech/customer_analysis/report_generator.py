from __future__ import annotations

import json
import time
from datetime import datetime
from pathlib import Path
from typing import Any

import requests

from southeast_asia_medtech.processors.analyze_with_deepseek import config, extract_json

from .workflow import read_records, validate_report, write_json


PROMPT_VERSION = "customer-analysis-report-v2"
PROMPT_PATH = Path(__file__).resolve().parent / "prompts" / "customer_analysis_report_prompt.txt"


def _call_report_api(
    *, prompt: str, payload: dict[str, Any], retries: int = 3
) -> dict[str, Any]:
    cfg = config()
    headers = {"Authorization": f"Bearer {cfg['api_key']}", "Content-Type": "application/json"}
    request_payload = {
        "model": cfg["model"],
        "messages": [
            {"role": "system", "content": prompt},
            {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
        ],
        "temperature": 0.1,
        "response_format": {"type": "json_object"},
    }
    last_error: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            response = requests.post(
                f"{cfg['base_url']}/chat/completions",
                headers=headers,
                json=request_payload,
                timeout=180,
            )
            response.raise_for_status()
            return extract_json(response.json()["choices"][0]["message"]["content"])
        except Exception as exc:
            last_error = exc
            if attempt < retries:
                time.sleep(2**attempt)
    raise RuntimeError(f"Customer analysis report generation failed after {retries} attempts: {last_error}")


def generate_draft(*, output_root: Path, issue: str) -> Path:
    """Generate and validate one issue draft without overwriting an approved report."""
    issue_dir = output_root / "issues" / issue
    evidence = read_records(issue_dir / "prompt_evidence.json")
    if len(evidence) < 10:
        raise ValueError("at least 10 priority-evidence articles are required")
    prompt = PROMPT_PATH.read_text(encoding="utf-8")
    payload = {
        "issue": issue,
        "coverage_period": "2025–2026",
        "source_evidence_count": len(evidence),
        "evidence": evidence,
    }
    report = _call_report_api(prompt=prompt, payload=payload)
    metadata = report.setdefault("report_metadata", {})
    metadata.update(
        {
            "issue": issue,
            "language": "en",
            "coverage_period": payload["coverage_period"],
            "source_evidence_count": len(evidence),
        }
    )
    validate_report(report, evidence)
    report["_analysis_meta"] = {
        "provider": "deepseek",
        "prompt_version": PROMPT_VERSION,
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
    }
    draft_path = issue_dir / "draft.json"
    write_json(draft_path, report)
    return draft_path
