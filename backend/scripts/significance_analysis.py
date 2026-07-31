"""Runner for the benchmark significance layer (app.core.significance).

Produces data/calibration/significance.json — bootstrap CIs for every
leaderboard metric, paired-bootstrap deltas and sign-flip permutation
p-values for every model pair, and CIs for the Track B cascade-shape
Spearman dimensions — all deterministic under the recorded seed.

Run:  python -m scripts.significance_analysis          (~1-2 min)
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from app.core.significance import run_significance

OUT_PATH = (Path(__file__).resolve().parents[1]
            / "data" / "calibration" / "significance.json")


def _fmt_ci(block: dict | None) -> str:
    if not block or block.get("point") is None:
        return "        —        "
    return f"{block['point']:+.4f} [{block['p2_5']:+.4f},{block['p97_5']:+.4f}]"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--n-boot", type=int, default=10_000)
    ap.add_argument("--n-perm", type=int, default=20_000)
    ap.add_argument("--seed", type=int, default=20260718)
    ap.add_argument("--out", type=Path, default=OUT_PATH)
    args = ap.parse_args(argv)

    payload = run_significance(n_boot=args.n_boot, n_perm=args.n_perm,
                               seed=args.seed)

    print(f"N={payload['n_events']} events, {args.n_boot} bootstrap resamples, "
          f"{args.n_perm} permutations, seed={args.seed}\n")

    print("Per-model 95% bootstrap CIs:")
    for name, m in payload["models"].items():
        sp = m["spearman"]
        sp_txt = _fmt_ci(sp) if sp else "constant predictor"
        print(f"  {name:18s} MAE {_fmt_ci(m['mae'])}   "
              f"RMSE {_fmt_ci(m['rmse'])}   Spearman {sp_txt}")

    print("\nPairwise (delta = first minus second; negative MAE delta = first is better):")
    for pair, d in payload["pairwise"].items():
        dm = d["delta_mae_a_minus_b"]
        sig = ("SIGNIFICANT" if dm["p2_5"] is not None
               and (dm["p2_5"] > 0 or dm["p97_5"] < 0)
               and d["p_perm_mae_two_sided"] < 0.05 else "n.s.")
        print(f"  {pair:42s} dMAE {_fmt_ci(dm)}  "
              f"p_perm={d['p_perm_mae_two_sided']:.4f}  "
              f"frac_first_better={d['frac_a_better_mae']:.3f}  [{sig}]")

    print("\nTrack B cascade-shape Spearman (bootstrap CI):")
    for dim, block in payload["cascade_shape_spearman"].items():
        print(f"  {dim:16s} n={block['n']:2d}  {_fmt_ci(block)}")

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(f"\nwrote {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
