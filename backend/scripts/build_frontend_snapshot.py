#!/usr/bin/env python3
"""Bake a static, offline copy of every deterministic API response the site reads.

WHY THIS EXISTS
---------------
The backend is hosted on a free tier that sleeps after 15 minutes of inactivity
and takes 20-30 s to wake. Almost every panel on the site renders `null` until
its fetch resolves, so a visitor arriving at a cold instance sees a title and
empty space — with no reason to believe the space will ever fill in. A judge with
ninety seconds is exactly the visitor who arrives cold.

So the frontend ships with a snapshot: the same JSON the live API returns,
generated from the same commit, written into `frontend/public/snapshot/`. When a
fetch fails the client serves the snapshot, the page renders in full at once, and
a banner states plainly that the numbers are precomputed and names the commit.

WHAT IS AND IS NOT SNAPSHOTTED
------------------------------
Only endpoints that are pure functions of committed data. Every validation
artifact, the graph, the scenario list, and one full simulation of the flagship
scenario qualify: re-running them on the same commit reproduces them byte for
byte, which is what tests/test_frontend_snapshot.py asserts.

Deliberately excluded, because a stale copy of them would be a false claim rather
than a slow one:

    /narrative, /crisis-radar   LLM output, non-deterministic, has its own cache
    /news/*                     live headlines; a frozen "current signal" is a lie
    /data/last-refresh          a timestamp; frozen, it misreports freshness

Those panels stay empty while the backend is asleep, which is correct — they have
nothing truthful to show.

USAGE
    python backend/scripts/build_frontend_snapshot.py
    python backend/scripts/build_frontend_snapshot.py --check   # verify, no writes
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "backend"))

OUT_DIR = REPO / "frontend" / "public" / "snapshot"

# The scenario the site auto-runs on load. Snapshotting it means the cascade map,
# the timeline, the counters and the metrics panel are populated on a cold open
# rather than waiting on a websocket that cannot connect.
FLAGSHIP = "taiwan-semi-75"

GET_PATHS: list[str] = [
    "/api/v1/graph",
    "/api/v1/graph?version=v3",
    "/api/v1/scenarios",
    "/api/v1/cv-report",
    "/api/v1/cascade-validation",
    "/api/v1/data/historical-events-csv",
    "/api/v1/posterior",
    "/api/v1/research-metrics",
    "/api/v1/calibration-report",
    "/api/v1/ablation",
    "/api/v1/benchmark",
    "/api/v1/loo-de-report",
    "/api/v1/portwatch-validation",
    "/api/v1/gscpi-validation",
    "/api/v1/icio-edge-check",
    "/api/v1/icio-c26-split",
]

# Only the flagship scenario is baked — a snapshot is a cold-open aid, not an
# offline mode, and someone who has picked another scenario has already waited.
POST_CALLS: list[tuple[str, dict]] = [
    ("/api/v1/simulate", {"scenario_id": FLAGSHIP}),
    ("/api/v1/baseline-compare", {"scenario_id": FLAGSHIP}),
    ("/api/v1/forecast-band", {"scenario_id": FLAGSHIP}),
    ("/api/v1/policy", {"scenario_id": FLAGSHIP}),
]


def slug(path: str) -> str:
    """Path -> snapshot filename stem.

    Must stay byte-identical to `snapshotKey` in frontend/lib/api.ts; the two are
    pinned together by tests/test_frontend_snapshot.py::test_slug_matches_frontend.
    """
    return re.sub(r"[^a-zA-Z0-9._-]+", "_", path.strip("/"))


def post_slug(path: str, body: dict) -> str:
    return f"post_{slug(path)}__{slug(str(body.get('scenario_id', 'custom')))}"


def _git(*args: str) -> str:
    try:
        return subprocess.run(
            ["git", *args], cwd=REPO, capture_output=True, text=True, check=True
        ).stdout.strip()
    except Exception:
        return "unknown"


def build() -> dict[str, object]:
    """Return {filename: payload} for everything that should be on disk."""
    from fastapi.testclient import TestClient

    from app.main import app

    files: dict[str, object] = {}
    with TestClient(app) as client:
        for path in GET_PATHS:
            r = client.get(path)
            if r.status_code != 200:
                print(f"  skip {path} -> {r.status_code}", file=sys.stderr)
                continue
            files[f"{slug(path)}.json"] = r.json()

        for path, body in POST_CALLS:
            r = client.post(path, json=body)
            if r.status_code != 200:
                print(f"  skip POST {path} -> {r.status_code}", file=sys.stderr)
                continue
            files[f"{post_slug(path, body)}.json"] = r.json()

    return files


def manifest(files: dict[str, object]) -> dict[str, object]:
    """Provenance for the banner. Carries no wall-clock time deliberately: a
    timestamp would change every run and make the freshness test unusable. The
    commit is what matters, and it is verifiable."""
    return {
        "commit": _git("rev-parse", "HEAD"),
        "commit_short": _git("rev-parse", "--short", "HEAD"),
        "commit_date": _git("log", "-1", "--format=%cI"),
        "flagship_scenario": FLAGSHIP,
        "files": sorted(files),
        "note": (
            "Precomputed responses from the deterministic endpoints of this commit. "
            "Served only when the live backend is unreachable. Regenerate with "
            "python backend/scripts/build_frontend_snapshot.py"
        ),
    }


def serialise(payload: object) -> str:
    # sort_keys + fixed separators: the file must be reproducible, so a diff means
    # a real change in model output and never a dict-ordering artefact.
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


# Keys recording WHEN a payload was produced or HOW LONG it took. They change on
# every run by construction, so comparing them would make the freshness check
# fail constantly and train everyone to ignore it. They stay in the written file
# — that provenance is worth having — and are dropped only from comparisons.
#
# Verified before this list existed: with these removed, all 20 payloads are
# byte-identical across runs. Every number the site reads is deterministic, which
# is the property that makes shipping a snapshot defensible at all.
VOLATILE_KEYS = {"timestamp", "runtime_seconds", "generated_at"}


def strip_volatile(payload: object) -> object:
    if isinstance(payload, dict):
        return {k: strip_volatile(v) for k, v in payload.items() if k not in VOLATILE_KEYS}
    if isinstance(payload, list):
        return [strip_volatile(v) for v in payload]
    return payload


def comparable(payload: object) -> str:
    return serialise(strip_volatile(payload))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="verify only; exit 1 if stale")
    args = ap.parse_args()

    files = build()
    files["manifest.json"] = manifest(dict(files))

    if args.check:
        stale = []
        for name, payload in files.items():
            p = OUT_DIR / name
            if not p.exists():
                stale.append(f"missing {name}")
            elif comparable(json.loads(p.read_text(encoding="utf-8"))) != comparable(payload):
                stale.append(f"changed {name}")
        for name in sorted(p.name for p in OUT_DIR.glob("*.json")):
            if name not in files:
                stale.append(f"orphan  {name}")
        if stale:
            print("snapshot is stale:", file=sys.stderr)
            for s in stale:
                print(f"  {s}", file=sys.stderr)
            print("\nregenerate: python backend/scripts/build_frontend_snapshot.py",
                  file=sys.stderr)
            return 1
        print(f"snapshot fresh ({len(files)} files)")
        return 0

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for name in sorted(p.name for p in OUT_DIR.glob("*.json")):
        if name not in files:
            (OUT_DIR / name).unlink()
            print(f"  removed {name}")

    total = 0
    for name, payload in sorted(files.items()):
        text = serialise(payload)
        (OUT_DIR / name).write_text(text, encoding="utf-8")
        total += len(text)
        print(f"  {name:52s} {len(text) / 1024:8.1f} KB")

    print(f"\n{len(files)} files, {total / 1024 / 1024:.2f} MB total -> {OUT_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
