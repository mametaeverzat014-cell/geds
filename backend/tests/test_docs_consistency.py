"""Documentation may not contradict the artifacts it claims to summarize.

The repository carries the paper in THREE places — `docs/PAPER.ru.md`, and two
hand-maintained inline copies inside `docs/mdpi_build.js` / `mdpi_build_en.js`
that generate the MDPI .docx files. Nothing structurally prevents them from
drifting apart, and during the 2026-08 audit they had: the markdown had been
corrected while both .docx builders still asserted a superseded ablation result.

These tests are the cheap guard. They do not attempt to diff prose; they assert
that a small set of load-bearing NUMBERS and NEGATIVE CLAIMS appear consistently
wherever they appear at all, and that no document reasserts a claim the
artifacts refute.

If a test here fails, the fix is to update whichever copy is stale — never to
relax the assertion.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
DOCS = REPO / "docs"
CALIB = REPO / "backend" / "data" / "calibration"

PAPER_RU = DOCS / "PAPER.ru.md"
BUILD_RU = DOCS / "mdpi_build.js"
BUILD_EN = DOCS / "mdpi_build_en.js"
RESULTS = DOCS / "RESULTS.md"

ALL_PAPER_SURFACES = [PAPER_RU, BUILD_RU, BUILD_EN]


def _text(p: Path) -> str:
    return p.read_text(encoding="utf-8")


@pytest.mark.parametrize("path", ALL_PAPER_SURFACES + [RESULTS])
def test_paper_surface_exists(path: Path):
    assert path.exists(), f"missing documentation surface: {path}"


@pytest.mark.parametrize("path", ALL_PAPER_SURFACES)
def test_no_surface_claims_the_dead_seis_ablation(path: Path):
    """The `no_seis` row was 0.0242 only because the flag was a no-op.

    Any surface still printing that value next to the SEIS row is stale.
    """
    body = _text(path)
    for stale in ('["−SEIS (без машины состояний)", "0,0242"',
                  '["−SEIS (no state machine)", "0.0242"'):
        assert stale not in body, (
            f"{path.name} still reports the pre-fix no_seis ablation value; the "
            "true ablation is 0.0166 (see ablation.json)")


@pytest.mark.parametrize("path", ALL_PAPER_SURFACES)
def test_no_surface_claims_a_significant_magnitude_difference(path: Path):
    """After Holm correction nothing on the magnitude axis is significant.

    The v3 one-vs-five comparison (raw p=0.037, Holm p=0.18) was previously
    advertised as the only significant model difference in the work.
    """
    body = _text(path)
    for stale in ("единственное статистически значимое различие моделей",
                  "the only statistically significant model difference anywhere in this work"):
        assert stale not in body, (
            f"{path.name} still claims a significant magnitude difference; "
            "0 of 6 pairs and 0 of 5 v3 comparisons survive Holm correction")


def _collected_test_count() -> int:
    """How many tests this suite actually has, asked of pytest itself.

    A subprocess rather than an in-process hook: collecting from inside a running
    session is fragile, and this costs about a second once.
    """
    out = subprocess.run(
        # NOT -q: the quiet format prints per-file counts and no total.
        [sys.executable, "-m", "pytest", "--collect-only", "-p", "no:cacheprovider"],
        cwd=Path(__file__).resolve().parents[1],
        capture_output=True, text=True,
    ).stdout
    m = re.search(r"(\d+) tests? collected", out)
    assert m, f"could not read a test count out of pytest's own output:\n{out[-400:]}"
    return int(m.group(1))


@pytest.mark.parametrize("path", ALL_PAPER_SURFACES)
def test_every_surface_reports_the_REAL_test_count(path: Path):
    """The published test count must equal the count, not merely avoid one wrong value.

    This used to be a blocklist of a single stale number ("157"), which is a
    check that passes for every wrong answer except one. It did exactly that: the
    paper and both MDPI builders sat at 149 while the suite had grown past it,
    and nothing failed. A claim about the repository should be verified against
    the repository.
    """
    real = _collected_test_count()
    body = _text(path)
    # Only the four phrasings that actually assert a suite total. A looser
    # pattern picks up sentences like "5 permutation tests", which are data, not
    # a claim about this repository.
    claims = re.findall(
        r"(\d+)\s*(?:автотест\w*"
        r"|automated tests?"
        r"|тест\w*,\s*все зелёные"
        r"|tests?,\s*all green)",
        body,
    )
    assert claims, f"{path.name} states no test count at all — did the phrasing change?"
    for claimed in claims:
        assert int(claimed) == real, (
            f"{path.name} claims {claimed} tests; `python -m pytest` collects {real}. "
            "Update the surface — or, if the suite shrank, say why in the commit."
        )


def test_ablation_artifact_agrees_with_its_published_claim():
    """RESULTS.md must not assert significance the artifact does not support."""
    abl = json.loads((CALIB / "ablation.json").read_text(encoding="utf-8"))
    n_sig = abl["n_significant_after_holm"]
    body = _text(RESULTS)
    if n_sig == 0:
        assert "NO ablation delta is distinguishable from zero" in body, (
            "ablation.json reports zero significant deltas but RESULTS.md does "
            "not say so — regenerate with scripts.results_onepager")
    for row in abl["rows"]:
        if row["variant"] == "full":
            continue
        assert row["significant_vs_full"] is not None, (
            f"ablation row {row['variant']} has no significance verdict")


def test_significance_artifact_agrees_with_its_published_claim():
    sig = json.loads((CALIB / "significance.json").read_text(encoding="utf-8"))
    assert sig["n_pairwise_significant_after_holm"] == 0
    body = _text(RESULTS)
    assert "0 of 6 pairwise magnitude differences are significant" in body, (
        "RESULTS.md no longer matches significance.json — regenerate it")


def test_spatial_recall_numbers_are_consistent_across_docs():
    """0.29 -> 0.79 is quoted in several places; a stale copy is a real risk.

    An earlier strategy document carried 0.32 -> 0.76 from a superseded run.
    """
    robust = json.loads(
        (CALIB / "spatial_recall_robustness.json").read_text(encoding="utf-8"))
    published = next(r for r in robust["rows"] if r["is_published_threshold"])
    v2 = f"{published['v2_recall']:.2f}"      # '0.29'
    v3 = f"{published['v3_recall']:.2f}"      # '0.79'

    strategy = DOCS / "ISEF_STRATEGY.md"
    if strategy.exists():
        body = _text(strategy)
        assert "0.32 → 0.76" not in body, (
            "ISEF_STRATEGY.md carries the superseded spatial-recall pair; "
            f"the current values are {v2} -> {v3}")

    ru = _text(PAPER_RU)
    assert v2.replace(".", ",") in ru and v3.replace(".", ",") in ru, (
        f"PAPER.ru.md no longer quotes the published spatial recall {v2} -> {v3}")
