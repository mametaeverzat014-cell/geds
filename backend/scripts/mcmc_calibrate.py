"""Run MCMC Bayesian calibration and write posterior.json.

Usage
-----
    python -m scripts.mcmc_calibrate              # defaults (32×600, ~90 s)
    python -m scripts.mcmc_calibrate --n-steps 2000 --n-walkers 64    # publication-grade
    python -m scripts.mcmc_calibrate --n-steps 50 --quiet             # smoke test (~5 s)

Output: data/calibration/posterior.json (consumed by /api/v1/posterior endpoint)
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

THIS = Path(__file__).resolve()
sys.path.insert(0, str(THIS.parent.parent))

from app.core.mcmc import run_mcmc, save_result


def main() -> int:
    ap = argparse.ArgumentParser(description="GEDS MCMC Bayesian calibration")
    ap.add_argument("--n-walkers", type=int, default=32)
    ap.add_argument("--n-steps", type=int, default=600)
    ap.add_argument("--n-burnin", type=int, default=200)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args()

    print(f"Running MCMC: {args.n_walkers} walkers × {args.n_steps} steps "
          f"({args.n_walkers * args.n_steps:,} samples, "
          f"{args.n_walkers * (args.n_steps - args.n_burnin):,} effective)")

    result = run_mcmc(
        n_walkers=args.n_walkers,
        n_steps=args.n_steps,
        n_burnin=args.n_burnin,
        seed=args.seed,
        progress=not args.quiet,
    )
    path = save_result(result)

    print()
    print(f"Runtime:               {result.runtime_seconds:.1f} s")
    print(f"Acceptance fraction:   {result.acceptance_fraction_mean:.3f}")
    print(f"Max autocorr time:     {result.autocorr_time_max:.1f}")
    print(f"Max split-R̂:           {result.r_hat_max:.4f}")
    print(f"Converged:             {result.converged}")
    print(f"Log-evidence (max):    {result.log_evidence_proxy:.2f}")
    print()
    print(f"{'parameter':<22s}  {'mean':>10s}  {'std':>10s}  {'p05':>10s}  {'p95':>10s}  {'sens':>6s}")
    print("-" * 78)
    for p in result.parameters:
        print(f"{p.name:<22s}  {p.mean:10.4f}  {p.std:10.4f}  {p.p05:10.4f}  {p.p95:10.4f}  {p.sensitivity:6.3f}")
    print()
    print(f"Wrote {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
