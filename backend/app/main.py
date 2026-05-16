"""FastAPI entry point for the GEDS MVP."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api.routes import router as api_router
from .api.websocket import router as ws_router
from .config import settings
from .core.graph import compile_graph
from .data.seed import load_graph


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Warm the graph cache so the first request is fast.
    snapshot = load_graph()
    app.state.graph_snapshot = snapshot
    app.state.compiled_graph = compile_graph(
        snapshot, rerouting_efficiency=settings.rerouting_efficiency
    )
    yield


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


@app.get("/", tags=["meta"])
def root() -> dict:
    return {
        "name": "GEDS Cascade Propagation Engine",
        "version": "0.1.0",
        "docs": "/docs",
        "endpoints": {
            "graph":     "/api/v1/graph",
            "scenarios": "/api/v1/scenarios",
            "simulate":  "/api/v1/simulate",
            "validate":  "/api/v1/validate",
            "stream":    "/ws/simulate",
        },
    }
