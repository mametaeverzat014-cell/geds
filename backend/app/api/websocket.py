"""WebSocket streaming endpoint.

The client opens `/ws/simulate`, sends a JSON message with a scenario, and receives
one msgpack-encoded `Frame` per simulated week. Backpressure: the server awaits
each send, so a slow client throttles the producer.
"""

from __future__ import annotations

import asyncio

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from ..config import settings
from ..core import scenarios as scenario_registry
from ..core.graph import CompiledGraph
from ..core.propagation import PropagationEngine
from ..core.types import Scenario, ShockSpec
from ..services.news import apply_overlay_to_graph

router = APIRouter()


@router.websocket("/ws/simulate")
async def simulate_stream(ws: WebSocket) -> None:
    await ws.accept()

    try:
        payload = await ws.receive_json()
    except Exception as e:
        await ws.send_json({"event": "error", "message": f"invalid handshake: {e}"})
        await ws.close()
        return

    scenario = _resolve(payload)
    if scenario is None:
        await ws.send_json({"event": "error", "message": "unknown scenario or invalid payload"})
        await ws.close()
        return

    # Apply the live-news overlay (set via POST /news/apply) so a current
    # "Suez blockage in progress" / "war footing" actually changes the streamed
    # forecast — the WS path is what the Run button uses, so without this the
    # overlay would silently do nothing here.
    base_graph: CompiledGraph = ws.app.state.compiled_graph
    overlay = getattr(ws.app.state, "news_overlay", None)
    g: CompiledGraph = apply_overlay_to_graph(base_graph, overlay) if overlay else base_graph
    engine = PropagationEngine(g, scenario.config)

    overlay_active = bool(overlay and overlay.is_active())
    await ws.send_json(
        {
            "event": "start",
            "scenario": scenario.model_dump(mode="json"),
            "graph_version": g.snapshot.version,
            "node_count": g.n,
            "overlay_active": overlay_active,
            "overlay_node_count": len(overlay.deltas) if overlay_active else 0,
        }
    )

    try:
        # The engine produces a full result then we stream the frames. We could re-implement
        # for true coroutine-step streaming if simulations get large; for MVP this is plenty fast.
        result = engine.run(scenario)

        throttle = max(0.0, settings.stream_throttle_ms / 1000.0)
        for frame in result.frames:
            await ws.send_json({"event": "frame", "frame": frame.model_dump(mode="json")})
            if throttle:
                await asyncio.sleep(throttle)

        await ws.send_json(
            {"event": "complete", "summary": result.summary.model_dump(mode="json")}
        )
    except WebSocketDisconnect:
        return
    except Exception as e:
        await ws.send_json({"event": "error", "message": str(e)})
    finally:
        try:
            await ws.close()
        except RuntimeError:
            pass


def _resolve(payload: dict) -> Scenario | None:
    scenario_id = payload.get("scenario_id")
    if scenario_id:
        try:
            return scenario_registry.by_id(scenario_id)
        except KeyError:
            return None

    custom = payload.get("custom")
    if not custom:
        return None
    try:
        shocks = [ShockSpec(**s) for s in custom.get("shocks", [])]
        return Scenario(
            id="custom",
            name=custom.get("name", "Custom scenario"),
            horizon_weeks=int(custom.get("horizon_weeks", 52)),
            shocks=shocks,
        )
    except Exception:
        return None
