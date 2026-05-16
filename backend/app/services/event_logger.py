"""ML training-set logger: pairs (news event, suggested deltas) with subsequent
(simulation prediction, observed outcome) for a future shock-magnitude predictor.

JSONL append-only format (one record per line) keeps it trivially parseable
from pandas, polars, or duckdb without any schema migration burden.

Path: data/ml_dataset/events.jsonl
"""

from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .news import ParsedEvent


_PATH = Path(__file__).parent.parent.parent / "data" / "ml_dataset" / "events.jsonl"


def _ensure_dir() -> None:
    _PATH.parent.mkdir(parents=True, exist_ok=True)


def log_event(parsed: ParsedEvent, prediction: dict | None = None) -> None:
    """Append one parsed event + (optional) downstream prediction snapshot.

    `prediction` is the engine's forecast for the affected nodes — used later
    as the "predicted" side of the supervised learning pair.  Observed outcome
    is filled in by a separate reconciliation job once enough time has passed.
    """
    _ensure_dir()
    rec = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "headline": asdict(parsed.headline),
        "event_type": parsed.event_type,
        "matched_nodes": parsed.matched_nodes,
        "entities": parsed.entities,
        "deltas": [asdict(d) for d in parsed.deltas],
        "prediction": prediction,
        "observed": None,           # filled in later by reconcile job
    }
    with _PATH.open("a", encoding="utf-8") as f:
        f.write(json.dumps(rec, default=str) + "\n")


def reconcile_observed(
    event_hash: str,
    observed: dict[str, Any],
) -> bool:
    """Update a previously logged record with the realised outcome.

    Returns True if a record was updated.  Used by a scheduled job that runs
    weeks after each event to attach 'what actually happened' for ML training.
    """
    _ensure_dir()
    if not _PATH.exists():
        return False
    lines = _PATH.read_text(encoding="utf-8").splitlines()
    updated = False
    for i, line in enumerate(lines):
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            continue
        h = rec.get("headline") or {}
        # Match by URL (acts as the stable key for a headline).
        if h.get("url") == event_hash and rec.get("observed") is None:
            rec["observed"] = observed
            rec["reconciled_at"] = datetime.now(timezone.utc).isoformat()
            lines[i] = json.dumps(rec, default=str)
            updated = True
            break
    if updated:
        _PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return updated


def load_dataset() -> list[dict]:
    """Read the full event log — for training scripts."""
    if not _PATH.exists():
        return []
    out = []
    for line in _PATH.read_text(encoding="utf-8").splitlines():
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return out


__all__ = ["log_event", "reconcile_observed", "load_dataset"]
