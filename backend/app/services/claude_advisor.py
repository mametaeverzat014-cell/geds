"""Anthropic Claude integration — bilingual economic-crisis "radar".

Layered ON TOP OF the GEDS quantitative engine. GEDS computes the risk signals
(most-fragile nodes, cascading-criticality rankings, the live-news overlay);
Claude's only job is to turn those *real* signals into a readable, bilingual
(EN/RU) set of plausible danger scenarios. It does NOT invent crises or numbers.

Why this design (honesty mandate):
- An LLM asked "what crises might happen?" will happily fabricate confident,
  precise-sounding disasters. That is exactly what GEDS must never do. So the
  prompt forces every scenario to be GROUNDED in a provided GEDS signal, bans
  fabricated statistics/probabilities/dates, and labels output as *scenarios,
  not forecasts*. Any quantitative magnitude comes from the GEDS engine — never
  from Claude.

Environment
-----------
    ANTHROPIC_API_KEY       Anthropic API key (required for live calls)
    GEDS_CLAUDE_MODEL       override model (default: claude-opus-4-8)
    GEDS_CLAUDE_CACHE_DIR   override cache dir (default: data/claude_cache)

Caching: identical (signals, model) inputs hit the on-disk cache for 1 hour —
keeps the bill down during demos and repeated views. When no API key is set the
service returns a clearly-labelled bilingual stub so the panel still renders.
"""

from __future__ import annotations

import hashlib
import json
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

try:
    import anthropic
except ImportError as _e:  # pragma: no cover - import guard
    anthropic = None
    _ANTHROPIC_IMPORT_ERROR = _e


DEFAULT_MODEL = "claude-opus-4-8"
DEFAULT_CACHE_TTL_SECONDS = 3600
DEFAULT_TIMEOUT_SECONDS = 60.0
DEFAULT_MAX_TOKENS = 4000


_SYSTEM_PROMPT = """You are a senior global-risk analyst specializing in supply-chain and macro-financial contagion. You work strictly ON TOP OF GEDS, a quantitative cascade-simulation engine. You are given GEDS's own computed risk signals plus the current live-news disruption overlay.

Your job: surface 3-4 PLAUSIBLE dangerous economic situations ("what could go wrong") and explain each clearly, in BOTH English and Russian.

NON-NEGOTIABLE honesty rules:
1. GROUND every scenario in the provided signals. Each scenario's "basis" field MUST name the exact GEDS signal it derives from — a specific fragile node id, a high cascading-criticality node id, or an active news disruption from the input. Do NOT invent dangers unrelated to the provided data.
2. Do NOT fabricate statistics, probabilities, percentages, dollar figures, or dates. You have no quantitative forecast of your own — GEDS produces those separately. Keep any reference to magnitude qualitative.
3. "severity" is a QUALITATIVE label (low | medium | high) reflecting how strong the underlying signal is — it is NOT a probability and NOT a prediction.
4. These are scenarios to consider, not forecasts. Reflect that humility in the overview and the disclaimer.
5. Node ids look like "TWN:semiconductors" (country:industry) or "CP:Suez" (chokepoint). Use them precisely; do not invent node ids.

Respond with VALID JSON ONLY — no markdown fences, no preamble — matching exactly this schema:

{
  "overview_en": "<2-3 sentence honest read of the current risk picture, grounded in the signals>",
  "overview_ru": "<the same, in Russian>",
  "scenarios": [
    {
      "title_en": "<short scenario title>",
      "title_ru": "<Russian>",
      "trigger_en": "<what could set this off>",
      "trigger_ru": "<Russian>",
      "mechanism_en": "<how it would cascade through the trade network, naming the relevant nodes>",
      "mechanism_ru": "<Russian>",
      "watch_en": "<concrete indicators a policymaker should watch>",
      "watch_ru": "<Russian>",
      "basis": "<the exact GEDS signal this scenario is grounded in>",
      "severity": "<low | medium | high>"
    }
  ],
  "disclaimer_en": "AI interpretation of GEDS model signals and current news — plausible scenarios, not forecasts. Quantitative figures come from the GEDS engine, not from this analysis.",
  "disclaimer_ru": "<Russian translation of the disclaimer>"
}
"""


# ─────────────────────────── data class ──────────────────────────────────────


@dataclass
class CrisisRadar:
    """Parsed bilingual crisis-radar analysis."""

    overview_en: str
    overview_ru: str
    scenarios: list[dict[str, Any]]
    disclaimer_en: str
    disclaimer_ru: str
    model: str
    cached: bool
    latency_ms: int
    mode: str  # "live" | "stub"
    n_signals: int = 0
    _meta: dict = field(default_factory=dict)


# ─────────────────────────── cache helpers ──────────────────────────────────


def _cache_key(signals: dict, model: str) -> str:
    payload = json.dumps(
        {"signals": signals, "model": model}, sort_keys=True, default=str
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()[:24]


def _cache_dir() -> Path:
    p = Path(
        os.environ.get("GEDS_CLAUDE_CACHE_DIR")
        or Path(__file__).parent.parent.parent / "data" / "claude_cache"
    )
    p.mkdir(parents=True, exist_ok=True)
    return p


def _load_cached(key: str, ttl: int) -> dict | None:
    f = _cache_dir() / f"{key}.json"
    if not f.exists():
        return None
    if time.time() - f.stat().st_mtime > ttl:
        return None
    try:
        return json.loads(f.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


def _store_cached(key: str, payload: dict) -> None:
    f = _cache_dir() / f"{key}.json"
    f.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


# ─────────────────────────── client ─────────────────────────────────────────


class ClaudeCrisisAdvisor:
    """Anthropic Claude client for the bilingual crisis radar.

    Grounds entirely on GEDS-provided signals; falls back to a labelled stub
    when ANTHROPIC_API_KEY is not configured.
    """

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        cache_ttl: int = DEFAULT_CACHE_TTL_SECONDS,
        timeout: float = DEFAULT_TIMEOUT_SECONDS,
        max_tokens: int = DEFAULT_MAX_TOKENS,
    ) -> None:
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        self.model = model or os.environ.get("GEDS_CLAUDE_MODEL") or DEFAULT_MODEL
        self.cache_ttl = cache_ttl
        self.timeout = timeout
        self.max_tokens = max_tokens

    def is_configured(self) -> bool:
        return bool(self.api_key) and anthropic is not None

    def analyze(self, signals: dict, force_refresh: bool = False) -> CrisisRadar:
        key = _cache_key(signals, self.model)

        if not force_refresh:
            cached = _load_cached(key, self.cache_ttl)
            if cached is not None:
                return _parse(cached, cached=True, latency_ms=0,
                              model=cached.get("_model", self.model),
                              mode=cached.get("_mode", "live"), signals=signals)

        if not self.is_configured():
            stub = _stub(signals)
            stub["_model"] = f"{self.model}-stub"
            stub["_mode"] = "stub"
            _store_cached(key, stub)
            return _parse(stub, cached=False, latency_ms=0,
                          model=f"{self.model}-stub", mode="stub", signals=signals)

        user_prompt = (
            "Current GEDS risk signals (JSON):\n"
            + json.dumps(signals, indent=2, ensure_ascii=False, default=str)
            + "\n\nProduce the bilingual crisis-radar JSON now. Output the JSON object only."
        )

        t0 = time.perf_counter()
        try:
            client = anthropic.Anthropic(
                api_key=self.api_key, timeout=self.timeout, max_retries=1
            )
            resp = client.messages.create(
                model=self.model,
                max_tokens=self.max_tokens,
                system=_SYSTEM_PROMPT,
                messages=[{"role": "user", "content": user_prompt}],
            )
            text = "".join(
                getattr(b, "text", "") for b in resp.content if getattr(b, "type", "") == "text"
            )
        except Exception:
            # Network / auth / model error → labelled stub, never crash the panel.
            stub = _stub(signals)
            stub["_model"] = f"{self.model}-error"
            stub["_mode"] = "stub"
            _store_cached(key, stub)
            return _parse(stub, cached=False, latency_ms=0,
                          model=f"{self.model}-error", mode="stub", signals=signals)
        latency_ms = int((time.perf_counter() - t0) * 1000)

        parsed = _try_parse_json(text)
        parsed["_model"] = self.model
        parsed["_mode"] = "live"
        _store_cached(key, parsed)
        return _parse(parsed, cached=False, latency_ms=latency_ms,
                      model=self.model, mode="live", signals=signals)


# ─────────────────────────── parsing & stub ─────────────────────────────────


def _try_parse_json(content: str) -> dict:
    """Tolerant JSON extraction — strips fences / prose the model may prepend."""
    txt = (content or "").strip()
    if txt.startswith("```"):
        lines = [ln for ln in txt.splitlines() if not ln.strip().startswith("```")]
        txt = "\n".join(lines).strip()
    try:
        return json.loads(txt)
    except json.JSONDecodeError:
        start, end = txt.find("{"), txt.rfind("}")
        if start >= 0 and end > start:
            try:
                return json.loads(txt[start : end + 1])
            except json.JSONDecodeError:
                pass
        return {
            "overview_en": "Model returned unparseable output.",
            "overview_ru": "Модель вернула неразборчивый ответ.",
            "scenarios": [],
            "disclaimer_en": "AI interpretation of GEDS signals — scenarios, not forecasts.",
            "disclaimer_ru": "Интерпретация сигналов GEDS искусственным интеллектом — сценарии, а не прогнозы.",
        }


def _parse(payload: dict, cached: bool, latency_ms: int, model: str, mode: str,
           signals: dict) -> CrisisRadar:
    n_signals = (
        len(signals.get("most_fragile_nodes") or [])
        + len(signals.get("top_cascading_criticality_nodes") or [])
        + len(signals.get("active_news_disruptions") or [])
    )
    return CrisisRadar(
        overview_en=str(payload.get("overview_en", "")),
        overview_ru=str(payload.get("overview_ru", "")),
        scenarios=list(payload.get("scenarios") or []),
        disclaimer_en=str(payload.get("disclaimer_en", "")),
        disclaimer_ru=str(payload.get("disclaimer_ru", "")),
        model=model,
        cached=cached,
        latency_ms=latency_ms,
        mode=mode,
        n_signals=n_signals,
    )


def _stub(signals: dict) -> dict:
    """Honest placeholder when no API key is set — grounded in the real signals."""
    fragile = (signals.get("most_fragile_nodes") or [{}])
    top_fragile = fragile[0].get("node_id", "—") if fragile else "—"
    news = signals.get("active_news_disruptions") or []
    news_node = news[0].get("node_id") if news else None

    scenarios = [
        {
            "title_en": f"Acute stress at {top_fragile}",
            "title_ru": f"Острый стресс в узле {top_fragile}",
            "trigger_en": f"A disruption hitting {top_fragile}, GEDS's most shock-absorption-limited node.",
            "trigger_ru": f"Нарушение в узле {top_fragile} — наименее устойчивом по данным GEDS.",
            "mechanism_en": "Low shock-absorption capacity means a hit here propagates outward through trade dependencies before inventories adjust.",
            "mechanism_ru": "Низкая способность поглощать шок означает, что удар распространяется по торговым зависимостям до того, как скорректируются запасы.",
            "watch_en": "Inventory levels and order backlogs at downstream importers of this node.",
            "watch_ru": "Уровни запасов и невыполненные заказы у downstream-импортёров этого узла.",
            "basis": f"most_fragile_nodes[0] = {top_fragile} (low SAC)",
            "severity": "high",
        }
    ]
    if news_node:
        scenarios.append({
            "title_en": f"Live disruption escalates at {news_node}",
            "title_ru": f"Эскалация текущего нарушения в узле {news_node}",
            "trigger_en": f"The active news event already affecting {news_node} worsens or persists.",
            "trigger_ru": f"Текущее новостное событие, затрагивающее {news_node}, усугубляется или затягивается.",
            "mechanism_en": "An in-progress real-world disruption is already raising this node's vulnerability in the live overlay.",
            "mechanism_ru": "Текущее реальное нарушение уже повышает уязвимость этого узла в live-наложении.",
            "watch_en": "Follow-on headlines and whether the disruption spreads to connected nodes.",
            "watch_ru": "Последующие новости и распространение нарушения на связанные узлы.",
            "basis": f"active_news_disruptions includes {news_node}",
            "severity": "medium",
        })

    return {
        "overview_en": (
            "Demo output — set ANTHROPIC_API_KEY on the backend for live Claude analysis. "
            "The scenarios below are grounded in GEDS's current real signals but are placeholders."
        ),
        "overview_ru": (
            "Демо-вывод — задайте ANTHROPIC_API_KEY на backend для live-анализа Claude. "
            "Сценарии ниже основаны на реальных текущих сигналах GEDS, но являются заглушками."
        ),
        "scenarios": scenarios,
        "disclaimer_en": "AI interpretation of GEDS model signals and current news — plausible scenarios, not forecasts.",
        "disclaimer_ru": "Интерпретация сигналов модели GEDS и текущих новостей искусственным интеллектом — вероятные сценарии, а не прогнозы.",
    }


__all__ = ["ClaudeCrisisAdvisor", "CrisisRadar"]
