"use client";

import { useEffect, useState } from "react";
import { api, type BaselineCompare, type ForecastBand } from "@/lib/api";
import { useSimStore } from "@/lib/store";

/**
 * After a run completes, shows two honesty panels for the SAME scenario:
 *  (1) SEIRS vs the zero-parameter baselines (linear diffusion, Leontief) — so
 *      the cost/benefit of the engine's 5-parameter machinery is visible inline.
 *  (2) The leave-one-out forecast band — peak CSI re-run under all 26 LOO fold
 *      parameter sets, surfacing parametric uncertainty instead of a false-precise
 *      point estimate.
 */
export default function ModelComparisonPanel() {
  const scenarioId = useSimStore((s) => s.selectedScenarioId);
  const summary = useSimStore((s) => s.summary);
  const running = useSimStore((s) => s.running);

  const [cmp, setCmp] = useState<BaselineCompare | null>(null);
  const [band, setBand] = useState<ForecastBand | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!summary || running) return;
    let cancelled = false;
    setLoading(true);
    const req = { scenario_id: scenarioId };
    Promise.allSettled([api.baselineCompare(req), api.forecastBand(req)]).then(
      ([c, b]) => {
        if (cancelled) return;
        setCmp(c.status === "fulfilled" ? c.value : null);
        setBand(b.status === "fulfilled" ? b.value : null);
        setLoading(false);
      },
    );
    return () => {
      cancelled = true;
    };
    // Re-fetch whenever a new run finishes (summary identity changes) or scenario changes.
  }, [summary, scenarioId, running]);

  if (!summary) return null;

  const maxLoss = cmp ? Math.max(...cmp.models.map((m) => m.industry_loss), 0.0001) : 1;

  return (
    <div className="panel p-4 space-y-3">
      <div className="flex items-baseline justify-between">
        <h2 className="text-sm font-semibold uppercase tracking-wider text-text-secondary">
          Model vs baseline
        </h2>
        {loading && <span className="text-[10px] text-text-muted num">computing…</span>}
      </div>

      {/* ── SEIRS vs zero-parameter baselines ── */}
      {cmp ? (
        <div className="space-y-1.5">
          {cmp.models.map((m) => {
            const isEngine = m.parameters > 0;
            return (
              <div key={m.model} className="space-y-0.5">
                <div className="flex items-baseline justify-between text-xs">
                  <span className={isEngine ? "text-text-primary font-medium" : "text-text-secondary"}>
                    {m.model}
                    <span className="ml-1.5 text-[9px] uppercase tracking-wider text-text-muted">
                      {m.parameters === 0 ? "0-param" : `${m.parameters}-param`}
                    </span>
                  </span>
                  <span className="num text-text-secondary">
                    {(m.industry_loss * 100).toFixed(1)}% · {m.recovery_weeks.toFixed(0)}w
                  </span>
                </div>
                <div className="h-1.5 rounded-full bg-bg-base/60 overflow-hidden">
                  <div
                    className="h-full rounded-full"
                    style={{
                      width: `${(m.industry_loss / maxLoss) * 100}%`,
                      background: isEngine
                        ? "linear-gradient(90deg, rgba(124,108,251,0.9), rgba(77,208,225,0.9))"
                        : "rgba(120,130,150,0.55)",
                    }}
                  />
                </div>
              </div>
            );
          })}
          <p className="text-[10px] text-text-muted leading-snug pt-0.5">
            Peak {cmp.industry} loss · recovery weeks. Linear diffusion is the honest
            zero-free-parameter reference — when SEIRS doesn&apos;t beat it, that&apos;s worth seeing.
          </p>
        </div>
      ) : (
        !loading && <p className="text-[11px] text-text-muted">Baseline comparison unavailable.</p>
      )}

      {/* ── LOO forecast band ── */}
      {band?.available && band.median != null && (
        <div className="hairline pt-3 space-y-1.5">
          <div className="flex items-baseline justify-between">
            <span className="text-[10px] uppercase tracking-wider text-text-muted">
              LOO forecast band · peak CSI
            </span>
            <span className="num text-xs text-text-primary">{band.median.toFixed(3)}</span>
          </div>
          <ForecastBandBar band={band} />
          <p className="text-[10px] text-text-muted leading-snug">
            Median with 10–90% band across {band.n_folds} leave-one-out fold calibrations.
            Relative width {((band.rel_width ?? 0) * 100).toFixed(0)}% — parametric uncertainty
            only (structural uncertainty is larger).
          </p>
        </div>
      )}
    </div>
  );
}

function ForecastBandBar({ band }: { band: ForecastBand }) {
  const lo = band.min ?? 0;
  const hi = band.max ?? 1;
  const span = Math.max(hi - lo, 1e-6);
  const pct = (v: number) => `${((v - lo) / span) * 100}%`;
  const p10 = band.p10 ?? lo;
  const p90 = band.p90 ?? hi;
  const median = band.median ?? (lo + hi) / 2;
  return (
    <div className="relative h-3">
      {/* full min–max track */}
      <div className="absolute inset-x-0 top-1/2 -translate-y-1/2 h-1 rounded-full bg-bg-base/60" />
      {/* p10–p90 band */}
      <div
        className="absolute top-1/2 -translate-y-1/2 h-1 rounded-full"
        style={{
          left: pct(p10),
          width: `${((p90 - p10) / span) * 100}%`,
          background: "linear-gradient(90deg, rgba(124,108,251,0.7), rgba(77,208,225,0.7))",
        }}
      />
      {/* median marker */}
      <div
        className="absolute top-1/2 -translate-y-1/2 h-3 w-[2px] rounded-full bg-text-primary"
        style={{ left: pct(median) }}
      />
    </div>
  );
}
