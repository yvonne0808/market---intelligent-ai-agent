from __future__ import annotations

import hashlib
import json
import re
from datetime import date, datetime
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit


PRIORITY_RELEVANCE = {"direct_customer", "competitor"}
EXCLUDED_RELEVANCE = {"none"}
TRACKING_QUERY_KEYS = {"_sp", "fbclid", "gclid"}
CJK_CHARACTERS = re.compile(r"[\u3400-\u9fff\uf900-\ufaff]")


def canonical_url(value: object) -> str:
    """Return a stable URL identity without fragments or tracking parameters."""
    raw = str(value or "").strip()
    if not raw:
        return ""
    parsed = urlsplit(raw)
    query = [
        (key, item)
        for key, item in parse_qsl(parsed.query, keep_blank_values=True)
        if key.lower() not in TRACKING_QUERY_KEYS and not key.lower().startswith("utm_")
    ]
    return urlunsplit((parsed.scheme.lower(), parsed.netloc.lower(), parsed.path, urlencode(query), ""))


def article_identity(article: dict[str, Any]) -> str:
    """Use the analyzed ID when present, otherwise derive one from the source URL."""
    existing = str(article.get("article_id") or "").strip()
    if existing:
        return existing
    url = canonical_url(article.get("url"))
    digest = hashlib.sha256(url.encode("utf-8")).hexdigest()[:20]
    return f"customer_analysis_{digest}"


def event_year(value: object) -> int | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    for parser in (
        lambda: parsedate_to_datetime(raw),
        lambda: datetime.fromisoformat(raw.replace("Z", "+00:00")),
        lambda: datetime.strptime(raw, "%Y-%m-%d"),
    ):
        try:
            return parser().year
        except (TypeError, ValueError, IndexError):
            pass
    match = re.search(r"\b(20\d{2})\b", raw)
    return int(match.group(1)) if match else None


def event_date(value: object) -> date | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    for parser in (
        lambda: parsedate_to_datetime(raw),
        lambda: datetime.fromisoformat(raw.replace("Z", "+00:00")),
        lambda: datetime.strptime(raw, "%Y-%m-%d"),
    ):
        try:
            return parser().date()
        except (TypeError, ValueError, IndexError):
            pass
    return None


def _issue_end(issue: str) -> date:
    year, month = (int(part) for part in issue.split("-"))
    if month == 12:
        return date(year + 1, 1, 1)
    return date(year, month + 1, 1)


def _score(article: dict[str, Any]) -> int:
    value = article.get("relevance_score", 0)
    return value if isinstance(value, int) else 0


def _event_sort_key(article: dict[str, Any]) -> tuple[int, str, str]:
    return (-_score(article), str(article.get("published_date") or ""), str(article.get("article_id") or ""))


def _compact_event(article: dict[str, Any], source_label: str) -> dict[str, Any]:
    url = canonical_url(article.get("url"))
    identity = article_identity(article)
    existing_provenance = article.get("provenance")
    if not isinstance(existing_provenance, dict):
        existing_provenance = {}
    source_labels = list(existing_provenance.get("source_labels") or [source_label])
    source_article_ids = list(existing_provenance.get("source_article_ids") or [identity])
    return {
        "article_id": identity,
        "canonical_url": url,
        "url": str(article.get("url") or url),
        "title": str(article.get("title") or ""),
        "organization": str(article.get("organization") or article.get("company_name") or ""),
        "published_date": str(article.get("published_date") or ""),
        "year": event_year(article.get("published_date")),
        "customer_relevance": str(article.get("customer_relevance") or "industry_only"),
        "relevance_score": _score(article),
        "importance_level": str(article.get("importance_level") or "low"),
        "primary_category": str(article.get("primary_category") or "Other"),
        "summary_cn": str(article.get("summary_cn") or ""),
        "one_sentence_takeaway": str(article.get("one_sentence_takeaway") or ""),
        "customer_impact_cn": str(article.get("customer_impact_cn") or ""),
        "packaging_relevance_score": article.get("packaging_relevance_score", 0),
        "packaging_relevance_reason": str(article.get("packaging_relevance_reason") or ""),
        "matched_customers": list(article.get("matched_customers") or []),
        "related_customer_groups": list(article.get("related_customer_groups") or []),
        "competitor_companies": list(article.get("competitor_companies") or []),
        "report_countries": list(article.get("report_countries") or []),
        "source_name": str(article.get("source_name") or ""),
        "source_confidence": str(article.get("source_confidence") or ""),
        "provenance": {
            "source_labels": sorted(set(str(item) for item in source_labels if item)),
            "source_article_ids": sorted(set(str(item) for item in source_article_ids if item)),
        },
    }


def build_event_ledger(
    articles: Iterable[dict[str, Any]], *, source_label: str
) -> dict[str, Any]:
    """Build displayable evidence, excluding explicit non-medical/no-value rows."""
    source_articles = 0
    excluded_none = 0
    candidates: dict[str, dict[str, Any]] = {}
    duplicate_count = 0
    for article in articles:
        if not isinstance(article, dict):
            continue
        source_articles += 1
        relevance = str(article.get("customer_relevance") or "industry_only")
        if relevance in EXCLUDED_RELEVANCE:
            excluded_none += 1
            continue
        item = _compact_event(article, source_label)
        key = item["canonical_url"] or item["article_id"]
        existing = candidates.get(key)
        if existing is None:
            candidates[key] = item
            continue
        duplicate_count += 1
        if _event_sort_key(item) < _event_sort_key(existing):
            item["provenance"]["source_labels"] = sorted(
                set(existing["provenance"]["source_labels"] + item["provenance"]["source_labels"])
            )
            item["provenance"]["source_article_ids"] = sorted(
                set(existing["provenance"]["source_article_ids"] + item["provenance"]["source_article_ids"])
            )
            candidates[key] = item
        else:
            existing["provenance"]["source_labels"] = sorted(
                set(existing["provenance"]["source_labels"] + item["provenance"]["source_labels"])
            )
            existing["provenance"]["source_article_ids"] = sorted(
                set(existing["provenance"]["source_article_ids"] + item["provenance"]["source_article_ids"])
            )
    events = sorted(candidates.values(), key=_event_sort_key)
    priority_evidence = [
        item for item in events if item["customer_relevance"] in PRIORITY_RELEVANCE
    ]
    return {
        "events": events,
        "priority_evidence": priority_evidence,
        "counts": {
            "source_articles": source_articles,
            "excluded_none": excluded_none,
            "deduplicated": duplicate_count,
            "events": len(events),
            "priority_evidence": len(priority_evidence),
        },
    }


def merge_ledgers(ledgers: Iterable[dict[str, Any]]) -> dict[str, Any]:
    """Merge previously prepared ledgers while preserving every source label."""
    source_rows: list[dict[str, Any]] = []
    for ledger in ledgers:
        for item in ledger.get("events", []):
            if not isinstance(item, dict):
                continue
            source_rows.append(item)
    merged = build_event_ledger(source_rows, source_label="merged-ledger")
    return merged


def compact_prompt_evidence(events: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    """Restrict report-model input to evidence needed for factual report synthesis."""
    return [
        {
            "article_id": item["article_id"],
            "date": item["published_date"],
            "organization": item["organization"],
            "role": item["customer_relevance"],
            "category": item["primary_category"],
            "relevance_score": item["relevance_score"],
            "title": item["title"],
            "summary_cn": item["summary_cn"],
            "customer_impact_cn": item["customer_impact_cn"],
            "packaging_score": item["packaging_relevance_score"],
            "packaging_reason_cn": item["packaging_relevance_reason"],
            "customers": item["matched_customers"] or item["related_customer_groups"],
            "url": item["url"],
        }
        for item in events
        if item.get("customer_relevance") in PRIORITY_RELEVANCE
    ]


def _require_english(value: object, field: str, *, allow_empty: bool = False) -> None:
    text = str(value or "").strip()
    if not text and allow_empty:
        return
    if not text or CJK_CHARACTERS.search(text):
        raise ValueError(f"{field} must be a non-empty English string")


def validate_report(report: dict[str, Any], evidence: Iterable[dict[str, Any]]) -> None:
    """Reject ungrounded or malformed AI/editorial report output before publishing."""
    if not isinstance(report, dict):
        raise ValueError("report must be an object")
    metadata = report.get("report_metadata")
    if not isinstance(metadata, dict) or metadata.get("language") != "en":
        raise ValueError("report_metadata.language must be en")
    _require_english(report.get("executive_summary"), "executive_summary")
    actions = report.get("priority_actions")
    if not isinstance(actions, list) or len(actions) != 10:
        raise ValueError("report must contain exactly 10 priority actions")
    known_ids = {str(item.get("article_id") or "") for item in evidence}
    used_evidence: set[str] = set()
    titles: set[str] = set()
    required_action_fields = {
        "title", "companies", "event_type", "commercial_implication_en",
        "packaging_angle_en", "recommended_next_step_en", "priority",
        "evidence_article_ids",
    }
    for action in actions:
        if not isinstance(action, dict):
            raise ValueError("priority action must be an object")
        missing = sorted(required_action_fields - action.keys())
        if missing:
            raise ValueError(f"priority action missing fields: {', '.join(missing)}")
        for field in (
            "title", "event_type", "commercial_implication_en",
            "packaging_angle_en", "recommended_next_step_en",
        ):
            _require_english(
                action.get(field), field, allow_empty=field == "packaging_angle_en"
            )
        title = str(action["title"]).strip().lower()
        if not title or title in titles:
            raise ValueError("duplicate priority action")
        titles.add(title)
        evidence_ids = action["evidence_article_ids"]
        if not isinstance(evidence_ids, list) or not evidence_ids:
            raise ValueError("priority action must cite evidence")
        for article_id in evidence_ids:
            if article_id not in known_ids:
                raise ValueError(f"unknown evidence article_id: {article_id}")
            if article_id in used_evidence:
                raise ValueError("duplicate priority action evidence")
            used_evidence.add(article_id)
def resolve_display_report(
    draft: dict[str, Any] | None, approved: dict[str, Any] | None
) -> tuple[dict[str, Any] | None, str]:
    """Return the editorially approved issue whenever it exists."""
    if approved is not None:
        return approved, "approved"
    return draft, "draft"


def read_records(path: Path) -> list[dict[str, Any]]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(value, dict):
        value = value.get("records", value.get("events", []))
    if not isinstance(value, list):
        raise ValueError(f"{path} must contain a JSON list or records array")
    return [item for item in value if isinstance(item, dict)]


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(path)


def _read_existing_events(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict) or not isinstance(value.get("events"), list):
        raise ValueError(f"{path} must contain an event ledger")
    return [item for item in value["events"] if isinstance(item, dict)]


def prepare_issue(
    source_paths: Iterable[Path], *, issue: str, output_root: Path
) -> dict[str, Any]:
    """Append analyzed sources to the master ledger and emit a reproducible issue bundle."""
    if not re.fullmatch(r"20\d{2}-(0[1-9]|1[0-2])", issue):
        raise ValueError("issue must use YYYY-MM")
    source_paths = [Path(path) for path in source_paths]
    if not source_paths:
        raise ValueError("at least one analyzed source is required")
    master_path = output_root / "master_events.json"
    ledgers = [
        build_event_ledger(read_records(path), source_label=path.name)
        for path in source_paths
    ]
    previous = _read_existing_events(master_path)
    merged = merge_ledgers([{"events": previous}, *ledgers])
    cutoff = _issue_end(issue)
    issue_ledger = build_event_ledger(
        [
            item
            for item in merged["events"]
            if event_date(item.get("published_date")) is None
            or event_date(item.get("published_date")) < cutoff
        ],
        source_label="issue-ledger",
    )
    manifest = {
        "issue": issue,
        "created_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "input_files": [str(path) for path in source_paths],
        "master_counts": merged["counts"],
        "issue_counts": issue_ledger["counts"],
        "prompt_evidence_count": len(issue_ledger["priority_evidence"]),
    }
    issue_dir = output_root / "issues" / issue
    write_json(master_path, {"events": merged["events"], "counts": merged["counts"]})
    write_json(issue_dir / "evidence.json", {"events": issue_ledger["events"], "counts": issue_ledger["counts"]})
    write_json(issue_dir / "prompt_evidence.json", compact_prompt_evidence(issue_ledger["priority_evidence"]))
    write_json(issue_dir / "source_manifest.json", manifest)
    return issue_ledger


def _read_json_object(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value


def export_site_assets(
    output_root: Path, *, issue: str, site_public_dir: Path
) -> tuple[Path, Path]:
    """Publish only reviewed/draft report JSON and source-linked evidence to the static site."""
    issue_dir = output_root / "issues" / issue
    draft = _read_json_object(issue_dir / "draft.json")
    approved = _read_json_object(issue_dir / "approved.json")
    report, status = resolve_display_report(draft, approved)
    if report is None:
        raise ValueError(f"no draft or approved report exists for issue {issue}")
    evidence = _read_json_object(issue_dir / "evidence.json")
    if evidence is None or not isinstance(evidence.get("events"), list):
        raise ValueError(f"issue evidence is missing for {issue}")
    report_asset = dict(report)
    report_asset.pop("opportunity_themes", None)
    report_asset["editorial_status"] = status
    report_asset["issue"] = issue
    target = site_public_dir / "customer-analysis"
    report_path = target / "report.json"
    events_path = target / "events.json"
    write_json(report_path, report_asset)
    write_json(events_path, evidence["events"])
    return report_path, events_path
