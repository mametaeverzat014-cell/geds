"""The shipped offline snapshot must equal what the API actually returns.

A precomputed copy of the site's data is only defensible while it is provably the
same data. Left unchecked it decays into a second, invisible source of truth:
someone corrects a number in the engine, the live API reports the new value, and
every visitor arriving at a sleeping backend is quietly shown the old one —
labelled, on the page, as real model output.

So the snapshot is treated like the golden regression snapshots: committed, and
compared. If a change moves any number the site can read, this fails and names
the file. The fix is to regenerate.

    python backend/scripts/build_frontend_snapshot.py
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "backend" / "scripts"))

import build_frontend_snapshot as snap  # noqa: E402


def test_snapshot_dir_exists():
    assert snap.OUT_DIR.is_dir(), (
        f"{snap.OUT_DIR} is missing — run: python backend/scripts/build_frontend_snapshot.py"
    )


def test_slug_matches_frontend():
    """`slug()` in the builder and `snapshotKey()` in lib/api.ts must agree.

    They are the only thing linking a request path to a file on disk. If they
    drift, every fallback 404s — silently, because the client rethrows the
    original network error and the panel simply stays empty. Nothing else in the
    system would notice, so the function body is pinned character for character.
    """
    api_ts = (REPO / "frontend" / "lib" / "api.ts").read_text(encoding="utf-8")
    expected = 'return path.replace(/^\\/+|\\/+$/g, "").replace(/[^a-zA-Z0-9._-]+/g, "_");'
    assert expected in api_ts, (
        "snapshotKey() in frontend/lib/api.ts no longer has the body this test pins.\n"
        f"expected exactly:  {expected}\n"
        "If the naming scheme changed on purpose, change slug() in "
        "backend/scripts/build_frontend_snapshot.py to match, update this string, "
        "and regenerate the snapshot."
    )
    for probe in ["/api/v1/graph", "/api/v1/graph?version=v3", "/api/v1/data/last-refresh"]:
        assert snap.slug(probe) == re.sub(r"[^a-zA-Z0-9._-]+", "_", probe.strip("/"))


@pytest.mark.parametrize("name", ["manifest.json", "api_v1_graph.json", "api_v1_scenarios.json"])
def test_core_files_present(name: str):
    assert (snap.OUT_DIR / name).exists(), f"snapshot/{name} missing — regenerate the snapshot"


def test_no_volatile_endpoint_is_snapshotted():
    """Time-dependent and LLM-backed endpoints must never be baked.

    A stale number is merely old. A frozen "current news signal", a frozen "last
    refreshed 2 h ago", or a frozen LLM narrative presented as the model's live
    reading are false claims — a visitor cannot tell them from live output, and
    unlike a validation artifact they are SUPPOSED to change. An empty panel beats
    a confident wrong one.
    """
    baked = [p.name for p in snap.OUT_DIR.glob("*.json")]
    for bad in ("last-refresh", "news", "narrative", "crisis-radar"):
        offenders = [n for n in baked if bad in n]
        assert not offenders, f"volatile endpoint baked into the snapshot: {offenders}"


def test_manifest_names_every_file():
    manifest = json.loads((snap.OUT_DIR / "manifest.json").read_text(encoding="utf-8"))
    on_disk = {p.name for p in snap.OUT_DIR.glob("*.json")} - {"manifest.json"}
    assert set(manifest["files"]) == on_disk, (
        "manifest.files disagrees with the directory — regenerate the snapshot"
    )
    assert manifest["flagship_scenario"] == snap.FLAGSHIP


def test_flagship_simulation_is_playable():
    """The fallback replays this file frame by frame; an empty or one-frame run
    would render a dead map and read as a bug rather than a cascade."""
    name = f"{snap.post_slug('/api/v1/simulate', {'scenario_id': snap.FLAGSHIP})}.json"
    result = json.loads((snap.OUT_DIR / name).read_text(encoding="utf-8"))
    assert len(result["frames"]) > 10, "flagship snapshot has too few frames to animate"
    assert result["summary"]["peak_csi"] > 0, "flagship snapshot shows no cascade at all"
    weeks = [f["week"] for f in result["frames"]]
    assert weeks == sorted(weeks), "frames are not in week order — replay would jump around"


def test_validation_page_uses_the_snapshot_aware_client():
    """The validation page once called `fetch` directly for eleven endpoints.

    Those calls bypassed the fallback entirely, so the whole page stayed on
    "Loading…" against a sleeping backend while every other page recovered. The
    bug is invisible in review — a bare fetch looks perfectly normal — so it is
    asserted instead.
    """
    src = (REPO / "frontend" / "app" / "validation" / "page.tsx").read_text(encoding="utf-8")
    assert "API_BASE" not in src, (
        "validation/page.tsx builds a URL from API_BASE again — those requests skip "
        "the snapshot fallback. Use getRaw() from lib/api."
    )


@pytest.mark.slow
def test_snapshot_matches_live_api():
    """The expensive one: regenerate everything and diff against what is committed."""
    fresh = snap.build()

    problems: list[str] = []
    for name, payload in fresh.items():
        path = snap.OUT_DIR / name
        if not path.exists():
            problems.append(f"missing {name}")
        else:
            on_disk = json.loads(path.read_text(encoding="utf-8"))
            # Compared with wall-clock provenance removed — see VOLATILE_KEYS.
            # Everything else must match byte for byte.
            if snap.comparable(on_disk) != snap.comparable(payload):
                problems.append(f"stale   {name}")
    for p in snap.OUT_DIR.glob("*.json"):
        if p.name != "manifest.json" and p.name not in fresh:
            problems.append(f"orphan  {p.name}")

    assert not problems, (
        "the shipped snapshot no longer matches the API:\n  "
        + "\n  ".join(problems)
        + "\n\nregenerate: python backend/scripts/build_frontend_snapshot.py"
    )
