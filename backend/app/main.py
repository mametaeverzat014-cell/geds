"""FastAPI entry point for the GEDS MVP.

Boot sequence (in order):
    1. Configure structured JSON logging
    2. Validate environment / config (warns on missing optional keys, fails on bad CORS regex)
    3. Lifespan: warm graph cache, run a self-check sim, stamp startup time
    4. Register CORS, routes, websocket
    5. Expose /health (deep) + /healthz (liveness) + / (meta)
"""

from __future__ import annotations

import logging
import os
import re
import sys
import time
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api.routes import router as api_router
from .api.websocket import router as ws_router
from .config import settings
from .core.graph import compile_graph
from .core.propagation import PropagationEngine
from .core.types import Scenario, ShockSpec
from .data.seed import load_graph


# ─────────────────────────── logging ────────────────────────────────────────


def _configure_logging() -> None:
    """Single-line key=value structured logs. Easy to grep, easy to ship to
    Loki/Datadog/CloudWatch without a JSON parser hop."""
    fmt = "ts=%(asctime)s level=%(levelname)s logger=%(name)s msg=%(message)s"
    logging.basicConfig(level=logging.INFO, format=fmt, datefmt="%Y-%m-%dT%H:%M:%S%z",
                        stream=sys.stdout, force=True)


# ─────────────────────────── env validation ────────────────────────────────


_OPTIONAL_KEYS = ["GROK_API_KEY", "NEWSAPI_KEY", "GNEWS_KEY", "COMTRADE_KEY"]


def _validate_environment() -> dict:
    """Validate config at boot. Returns a report dict for /health."""
    log = logging.getLogger("geds.boot")
    report: dict[str, object] = {"ok": True, "errors": [], "warnings": []}

    # Hard validation: CORS regex must compile if set.
    if settings.cors_allow_origin_regex:
        try:
            re.compile(settings.cors_allow_origin_regex)
            log.info("env_check cors_regex=ok pattern=%r", settings.cors_allow_origin_regex)
        except re.error as e:
            msg = f"GEDS_CORS_ALLOW_ORIGIN_REGEX is not a valid regex: {e}"
            report["errors"].append(msg)
            report["ok"] = False
            log.error("env_check cors_regex=FAIL error=%s", e)

    # Soft validation: optional service keys.
    keys_present: dict[str, bool] = {}
    for key in _OPTIONAL_KEYS:
        present = bool(os.environ.get(key))
        keys_present[key] = present
        if not present:
            report["warnings"].append(f"{key} not set — feature falls back to stub mode")
    report["optional_keys"] = keys_present
    log.info("env_check optional_keys=%s", keys_present)

    return report


# ─────────────────────────── lifespan ──────────────────────────────────────


@asynccontextmanager
async def lifespan(app: FastAPI):
    log = logging.getLogger("geds.boot")
    t0 = time.perf_counter()

    env_report = _validate_environment()
    app.state.env_report = env_report
    app.state.startup_at = datetime.now(timezone.utc).isoformat()

    snapshot = load_graph()
    app.state.graph_snapshot = snapshot
    app.state.compiled_graph = compile_graph(
        snapshot, rerouting_efficiency=settings.rerouting_efficiency
    )
    log.info("graph_loaded nodes=%d edges=%d",
             len(snapshot.nodes), len(snapshot.edges))

    # Self-check sim: tiny scenario, verifies the engine actually runs.
    try:
        engine = PropagationEngine(app.state.compiled_graph)
        chk = engine.run(Scenario(
            id="boot-selfcheck", name="boot",
            horizon_weeks=4,
            shocks=[ShockSpec(target_node_id=snapshot.nodes[0].id,
                              magnitude=0.5, start_week=0, duration_weeks=2)],
        ))
        app.state.selfcheck = {"ok": True, "peak_csi": chk.summary.peak_csi,
                               "frames": len(chk.frames)}
        log.info("self_check ok=True peak_csi=%.4f frames=%d",
                 chk.summary.peak_csi, len(chk.frames))
    except Exception as e:
        app.state.selfcheck = {"ok": False, "error": str(e)}
        log.exception("self_check ok=False error=%s", e)

    boot_ms = int((time.perf_counter() - t0) * 1000)
    app.state.boot_ms = boot_ms
    log.info("boot_complete elapsed_ms=%d env_ok=%s", boot_ms, env_report["ok"])

    yield

    log.info("shutdown")


# ─────────────────────────── app ───────────────────────────────────────────


_configure_logging()

app = FastAPI(
    title="GEDS — Cascade Propagation Engine",
    description=(
        "A research-grade computational framework for modeling cascading "
        "international economic disruptions over the global trade and supply-chain network."
    ),
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_allow_origins,
    allow_origin_regex=settings.cors_allow_origin_regex,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix="/api/v1")
app.include_router(ws_router)


# ─────────────────────────── meta endpoints ────────────────────────────────


@app.get("/", tags=["meta"])
def root() -> dict:
    return {
        "name": "GEDS Cascade Propagation Engine",
        "version": "0.1.0",
        "docs": "/docs",
        "health": "/health",
        "endpoints": {
            "graph":     "/api/v1/graph",
            "scenarios": "/api/v1/scenarios",
            "simulate":  "/api/v1/simulate",
            "validate":  "/api/v1/validate",
            "benchmark": "/api/v1/benchmark",
            "cv_report": "/api/v1/cv-report",
            "stream":    "/ws/simulate",
        },
    }


@app.get("/healthz", tags=["meta"])
def healthz() -> dict:
    """Liveness — no dependencies, never fails unless process is dead."""
    return {"status": "ok"}


@app.get("/health", tags=["meta"])
def health() -> dict:
    """Deep health — engine self-check + env validation report.

    Returns HTTP 200 even if degraded (so load balancers don't kill the
    pod over an optional missing key); the JSON body reports the truth.
    """
    snap = getattr(app.state, "graph_snapshot", None)
    return {
        "status": "ok" if getattr(app.state, "selfcheck", {}).get("ok") else "degraded",
        "startup_at": getattr(app.state, "startup_at", None),
        "boot_ms": getattr(app.state, "boot_ms", None),
        "graph": {
            "nodes": len(snap.nodes) if snap else 0,
            "edges": len(snap.edges) if snap else 0,
            "version": snap.version if snap else None,
        },
        "self_check": getattr(app.state, "selfcheck", {}),
        "env": getattr(app.state, "env_report", {}),
    }
