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
from ..services.news import apply_overlay_to_graph, overlay_to_shocks

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
    graph_version = (payload.get("graph_version") or "v2").lower()
    overlay = None

    if graph_version == "v3":
        # ICIO 81×5 graph: remap the scenario's shocks onto v3 node ids; the
        # news overlay (v2 node ids) does not apply here.
        from ..data.expanded_graph import to_v3_node
        from ..data.seed import compiled_graph_for

        g = compiled_graph_for("v3")
        remapped, dropped = [], []
        for sh in scenario.shocks:
            t3 = to_v3_node(sh.target_node_id)
            if t3 and t3 in g.index:
                remapped.append(sh.model_copy(update={"target_node_id": t3}))
            else:
                dropped.append(sh.target_node_id)
        if not remapped:
            await ws.send_json({"event": "error", "message":
                "This scenario has no equivalent on the ICIO 81×5 graph "
                "(chokepoint-only shocks have no node there). Try a production shock."})
            await ws.close()
            return
        scenario = scenario.model_copy(update={"shocks": remapped})
    else:
        base_graph: CompiledGraph = ws.app.state.compiled_graph
        overlay = getattr(ws.app.state, "news_overlay", None)
        g = apply_overlay_to_graph(base_graph, overlay) if overlay else base_graph

        # Inject active-news disruptions as real shocks on the matched nodes, so the
        # streamed forecast (this is the path the Run button uses) reflects them.
        extra_shocks = overlay_to_shocks(overlay) if overlay else []
        if extra_shocks:
            scenario = scenario.model_copy(
                update={"shocks": list(scenario.shocks) + [ShockSpec(**d) for d in extra_shocks]}
            )

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
