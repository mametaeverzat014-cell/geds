"""Pin the onset-driver numbers shown in the UI to the artifact that produced them.

The four correlations covered here previously existed only as a source comment in
two React components. There was no artifact and no script, so nothing could be
checked — and when the quantity was finally measured, dependency share came out
at +0.20 where the comment said -0.45. Opposite sign, displayed to readers, for
as long as the comment stood.

These tests exist so that cannot recur: the numbers are transcribed into the
components (they are static panel text, not worth a network round trip), and this
file fails if the transcription and the artifact ever disagree.

Regenerate with:  python -m scripts.onset_drivers
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
ARTIFACT = REPO / "backend" / "data" / "calibration" / "onset_drivers.json"
INSPECTOR = REPO / "frontend" / "components" / "NodeInspector.tsx"
NARRATIVE = REPO / "frontend" / "components" / "ForecastNarrative.tsx"


@pytest.fixture(scope="module")
def art() -> dict:
    assert ARTIFACT.exists(), f"{ARTIFACT} missing — run: python -m scripts.onset_drivers"
    return json.loads(ARTIFACT.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def block() -> str:
    """The ONSET constant literal from NodeInspector.tsx."""
    src = INSPECTOR.read_text(encoding="utf-8")
    m = re.search(r"const ONSET = \{(.+?)\n\} as const;", src, re.S)
    assert m, "ONSET constant not found in NodeInspector.tsx"
    return m.group(1)


def test_funnel_matches(art: dict, block: str):
    f = art["funnel"]
    assert re.search(rf"\bn: {f['nodes_scored']}\b", block), (
        f"panel states a different n; the artifact scored {f['nodes_scored']} nodes"
    )
    assert re.search(rf"neverReached: {f['never_reached_excluded']}\b", block), (
        f"never-reached count drifted; artifact says {f['never_reached_excluded']}"
    )
    assert re.search(rf"horizon: {art['horizon_weeks']}\b", block)


def test_every_correlation_matches(art: dict, block: str):
    """Every rho and interval endpoint on the panel, to 2 dp, against the artifact."""
    rows = re.findall(
        r'\{ en: "([^"]+)".*?rho: "([+-][\d.]+)", lo: "([+-][\d.]+)", hi: "([+-][\d.]+)" \}',
        block,
    )
    assert len(rows) == len(art["correlations"]), (
        f"panel shows {len(rows)} drivers, artifact has {len(art['correlations'])}"
    )
    for name, rho, lo, hi in rows:
        key = name.replace(" ", "_")
        assert key in art["correlations"], f"unknown driver on the panel: {name}"
        a = art["correlations"][key]
        for label, shown, actual in (
            ("rho", rho, a["rho"]),
            ("ci lo", lo, a["ci95_lo"]),
            ("ci hi", hi, a["ci95_hi"]),
        ):
            assert float(shown) == pytest.approx(round(actual, 2), abs=5e-3), (
                f"{name} {label}: panel shows {shown}, artifact has {actual:.4f}"
            )


def test_panel_reports_the_real_holm_minimum(art: dict, block: str):
    """The panel leans on 'no pair separates'; the p it cites must be the real one."""
    m = re.search(r'minHolm: "([\d.]+)"', block)
    assert m, "minHolm not found in the ONSET constant"
    lowest = min(v["p_holm"] for v in art["pairwise_paired_bootstrap"].values())
    assert float(m.group(1)) == pytest.approx(lowest, abs=5e-4)
    assert art["n_pairs_significant_after_holm"] == 0, (
        "a pair now separates after Holm — the panel's 'no pair is distinguishable' "
        "text is no longer true and must be REWRITTEN, not just renumbered"
    )


def test_collinearity_figure_matches(art: dict, block: str):
    m = re.search(r'collinear: "([+-]?[\d.]+)"', block)
    assert m, "collinear not found in the ONSET constant"
    actual = art["collinearity_spearman"]["dependency_share__vulnerability"]
    assert float(m.group(1)) == pytest.approx(round(actual, 2), abs=5e-3)


def test_narrative_quotes_the_same_dependency_share(art: dict):
    """ForecastNarrative repeats this one figure in prose, in both languages."""
    src = NARRATIVE.read_text(encoding="utf-8")
    rho = art["correlations"]["dependency_share"]["rho"]
    assert f"rho {rho:+.2f}" in src, f"English prose does not quote rho {rho:+.2f}"
    assert f"ρ={rho:+.2f}".replace(".", ",") in src, (
        "Russian prose does not quote the same coefficient"
    )


def test_no_retired_driver_value_pairs_remain():
    """No driver may still be displayed with the figure it used to carry.

    Checked as PAIRS, not as bare numbers: -0.46 was the old centrality figure
    and is now the measured inventory-depth figure, so a naive substring scan
    flags a correct value. What must not survive is a driver still showing the
    unsourced number that used to sit beside it — dependency share at -0.45
    above all, since that one had the wrong sign.

    Comments are stripped first: the explanation of what those numbers were and
    why they went is worth keeping next to the code that used to show them.
    """
    retired = {
        "dependency share": "-0.45",
        "vulnerability": "-0.53",
        "centrality": "-0.46",
        "inventory depth": "-0.44",
    }
    for path in (INSPECTOR, NARRATIVE):
        src = path.read_text(encoding="utf-8")
        body = re.sub(r"/\*.*?\*/", "", src, flags=re.S)
        body = re.sub(r"^\s*//.*$", "", body, flags=re.M)
        # Line-scoped: each driver row and each prose sentence is one line in
        # these files, and a wider window just spans into the next row — where
        # the neighbouring driver's correct value can look like a retired one.
        for line in body.splitlines():
            for driver, value in retired.items():
                assert not (driver in line and value in line), (
                    f"{path.name} still shows {driver} at the retired figure "
                    f"{value}:\n  {line.strip()}"
                )


def test_dependency_share_sign_is_the_measured_one(art: dict, block: str):
    """The regression that motivated all of this, stated as its own assertion."""
    measured = art["correlations"]["dependency_share"]["rho"]
    assert measured > 0, (
        "dependency share is no longer positive — the panel copy explains the "
        "sign flip from the retired -0.45 and must be rewritten if it moves again"
    )
    m = re.search(r'\{ en: "dependency share".*?rho: "([+-][\d.]+)"', block)
    assert m and float(m.group(1)) > 0, "panel shows a negative dependency share again"
