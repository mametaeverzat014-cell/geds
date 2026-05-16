"""xAI Grok integration — narrative policy advisor.

Takes raw GEDS simulation output and translates it into a structured policy
narrative aimed at finance ministers / central-bank staff.  Replaces the
generic rule-based advisor for the high-value "what does this actually mean"
question that judges and operators ask.

Why not OpenAI/Anthropic?  Grok is requested specifically by the user, and
its endpoint is fully OpenAI-compatible — swapping providers is a 2-line
change (base_url + model name) if needed.

Environment
-----------
    GROK_API_KEY     xAI API key (required for live calls)
    GROK_MODEL       override default model (default: grok-2-1212)
    GROK_BASE_URL    override endpoint (default: https://api.x.ai/v1)
    GROK_CACHE_DIR   override on-disk cache location (default: data/grok_cache)

Caching: identical (scenario_id, sim_output_hash) prompts hit the on-disk cache
for 1 hour by default — keeps the bill down during demos and reruns.
"""

from __future__ import annotations

import hashlib
import json
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

try:
    import httpx
except ImportError as _e:
    httpx = None
    _HTTPX_IMPORT_ERROR = _e


DEFAULT_MODEL = "grok-2-1212"
DEFAULT_BASE_URL = "https://api.x.ai/v1"
DEFAULT_CACHE_TTL_SECONDS = 3600
DEFAULT_TIMEOUT_SECONDS = 30.0


_BASE_PROMPT = """You are a senior policy advisor at the Bank for International Settlements with deep expertise in global supply-chain economics, trade-network analysis, and macroeconomic policy.

You receive simulation outputs from GEDS — a SEIRS-bullwhip cascade propagation engine modeling shock transmission through the global trade graph. Your job is to translate technical numbers into actionable narrative analysis for finance ministers, central-bank staff, and supply-chain officers.

Ground rules:
- Be specific about countries (ISO3 codes welcome), sectors, and trade flows.
- Cite the actual numbers from the input where they support a claim.
- Avoid generic recommendations like "monitor the situation" or "diversify suppliers" without specifying what and how.
- Limit total output to ~450 words. Concision is a feature.

{language_directive}

Respond with valid JSON only, matching this schema:

{{
  "executive_summary":      "<1 sentence>",
  "cascade_mechanism":      "<2-3 sentences explaining WHY these specific nodes are propagating, citing trade routes>",
  "immediate_risks":        ["<risk 1>", "<risk 2>", "<risk 3>"],
  "structural_vulnerabilities": ["<weakness 1>", "<weakness 2>", "<weakness 3>"],
  "policy_recommendations": [
    {{"action": "<specific action>", "target": "<country/sector/institution>", "time_horizon_weeks": <int>}},
    {{"action": "...", "target": "...", "time_horizon_weeks": <int>}},
    {{"action": "...", "target": "...", "time_horizon_weeks": <int>}}
  ],
  "confidence": "<low | medium | high>"
}}
"""

_LANG_DIRECTIVES = {
    "en": "All natural-language string values in your JSON response MUST be in ENGLISH. Use ISO3 codes for countries.",
    "ru": "ВСЕ строковые значения в JSON-ответе ДОЛЖНЫ быть на РУССКОМ языке — executive_summary, cascade_mechanism, immediate_risks, structural_vulnerabilities, policy_recommendations.action, .target. Используйте ISO3-коды стран (TWN, USA, CHN и т.д.). Ключи JSON оставьте на английском.",
}


def _system_prompt(lang: str) -> str:
    directive = _LANG_DIRECTIVES.get(lang, _LANG_DIRECTIVES["en"])
    return _BASE_PROMPT.format(language_directive=directive)


# ─────────────────────────── data classes ───────────────────────────────────


@dataclass
class GrokNarrative:
    """Parsed Grok policy narrative."""

    executive_summary: str
    cascade_mechanism: str
    immediate_risks: list[str]
    structural_vulnerabilities: list[str]
    policy_recommendations: list[dict[str, Any]]
    confidence: str
    model: str
    cached: bool
    latency_ms: int


# ─────────────────────────── helpers ────────────────────────────────────────


def _summarize_for_prompt(sim_summary: dict, top_n: int = 5) -> dict:
    """Reduce a SimulationResult.summary down to the bullets the model needs.

    We intentionally keep this small (a few KB) — sending raw frames burns
    tokens and rarely helps the narrative.
    """
    country_risk = (sim_summary.get("country_risk") or [])[:top_n]
    sector_fragility = (sim_summary.get("sector_fragility") or [])[:top_n]
    top_mcap = (sim_summary.get("top_market_cap_impacts") or [])[:top_n]
    return {
        "peak_csi": sim_summary.get("peak_csi"),
        "final_csi": sim_summary.get("final_csi"),
        "total_output_loss_usd": sim_summary.get("total_output_loss_usd"),
        "total_market_cap_loss_usd": sim_summary.get("total_market_cap_loss_usd"),
        "high_default_risk_count": sim_summary.get("high_default_risk_count"),
        "global_recovery_weeks": sim_summary.get("global_recovery_weeks"),
        "max_inflation_country": sim_summary.get("max_inflation_country"),
        "max_gdp_impact_country": sim_summary.get("max_gdp_impact_country"),
        "affected_country_count": sim_summary.get("affected_country_count"),
        "top_country_risks": [
            {
                "iso3": r["iso3"],
                "risk_score": r["risk_score"],
                "peak_shock": r["peak_shock"],
                "expected_recovery_weeks": r["expected_recovery_weeks"],
            }
            for r in country_risk
        ],
        "top_sector_fragility": [
            {
                "industry": r["industry"],
                "fragility_score": r["fragility_score"],
                "most_exposed_country": r["most_exposed_country"],
            }
            for r in sector_fragility
        ],
        "top_market_cap_impacts": top_mcap,
    }


def _cache_key(scenario_id: str, summary_blob: dict, model: str, lang: str) -> str:
    """Stable hash for caching identical (scenario, summary, model, lang) calls."""
    payload = json.dumps(
        {"scenario": scenario_id, "summary": summary_blob, "model": model, "lang": lang},
        sort_keys=True, default=str,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()[:24]


def _cache_dir() -> Path:
    p = Path(os.environ.get("GROK_CACHE_DIR") or
             Path(__file__).parent.parent.parent / "data" / "grok_cache")
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
    f.write_text(json.dumps(payload, indent=2), encoding="utf-8")


# ─────────────────────────── client ─────────────────────────────────────────


class GrokPolicyAdvisor:
    """xAI Grok client with prompt template, caching, and graceful fallback."""

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        base_url: str | None = None,
        cache_ttl: int = DEFAULT_CACHE_TTL_SECONDS,
        timeout: float = DEFAULT_TIMEOUT_SECONDS,
    ) -> None:
        self.api_key = api_key or os.environ.get("GROK_API_KEY")
        self.model = model or os.environ.get("GROK_MODEL") or DEFAULT_MODEL
        self.base_url = (base_url or os.environ.get("GROK_BASE_URL") or DEFAULT_BASE_URL).rstrip("/")
        self.cache_ttl = cache_ttl
        self.timeout = timeout

    def is_configured(self) -> bool:
        return bool(self.api_key) and httpx is not None

    def analyze(
        self,
        scenario_id: str,
        sim_summary: dict,
        force_refresh: bool = False,
        lang: str = "en",
    ) -> GrokNarrative:
        """Produce a narrative for a given simulation summary in the requested language.

        Falls back to a deterministic stub if no API key is configured.  The stub
        also respects the `lang` parameter so the UI stays consistent.
        """
        lang = lang if lang in {"en", "ru"} else "en"
        compact = _summarize_for_prompt(sim_summary)
        key = _cache_key(scenario_id, compact, self.model, lang)

        if not force_refresh:
            cached = _load_cached(key, self.cache_ttl)
            if cached is not None:
                return _parse_response(cached, cached=True, latency_ms=0, model=self.model)

        if not self.is_configured():
            stub = _stub_narrative(scenario_id, compact, lang=lang)
            _store_cached(key, stub)
            return _parse_response(stub, cached=False, latency_ms=0, model=f"{self.model}-stub")

        user_prompt = (
            f"Scenario: {scenario_id}\n\n"
            f"Simulation summary (JSON):\n{json.dumps(compact, indent=2, default=str)}\n\n"
            "Respond with the JSON object only — no preamble, no markdown fences."
        )

        body = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": _system_prompt(lang)},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0.4,
            "response_format": {"type": "json_object"},
        }

        t0 = time.perf_counter()
        with httpx.Client(
            base_url=self.base_url,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            timeout=self.timeout,
        ) as client:
            resp = client.post("/chat/completions", json=body)
            resp.raise_for_status()
            data = resp.json()
        latency_ms = int((time.perf_counter() - t0) * 1000)

        content = data["choices"][0]["message"]["content"]
        parsed = _try_parse_json(content)

        _store_cached(key, parsed)
        return _parse_response(parsed, cached=False, latency_ms=latency_ms, model=self.model)


# ─────────────────────────── parsing & fallback ─────────────────────────────


def _try_parse_json(content: str) -> dict:
    """Tolerant JSON extraction — strips markdown fences if the model wrapped output."""
    txt = content.strip()
    if txt.startswith("```"):
        # Remove ```json ... ``` fencing if model ignored response_format
        lines = txt.splitlines()
        lines = [ln for ln in lines if not ln.strip().startswith("```")]
        txt = "\n".join(lines).strip()
    try:
        return json.loads(txt)
    except json.JSONDecodeError:
        # Last-resort regex extraction of the outer {…} block
        start = txt.find("{")
        end = txt.rfind("}")
        if start >= 0 and end > start:
            try:
                return json.loads(txt[start : end + 1])
            except json.JSONDecodeError:
                pass
        return {
            "executive_summary": "Model returned unparseable output.",
            "cascade_mechanism": txt[:300],
            "immediate_risks": [],
            "structural_vulnerabilities": [],
            "policy_recommendations": [],
            "confidence": "low",
        }


def _parse_response(payload: dict, cached: bool, latency_ms: int, model: str) -> GrokNarrative:
    return GrokNarrative(
        executive_summary=str(payload.get("executive_summary", "")),
        cascade_mechanism=str(payload.get("cascade_mechanism", "")),
        immediate_risks=list(payload.get("immediate_risks") or []),
        structural_vulnerabilities=list(payload.get("structural_vulnerabilities") or []),
        policy_recommendations=list(payload.get("policy_recommendations") or []),
        confidence=str(payload.get("confidence", "medium")),
        model=model,
        cached=cached,
        latency_ms=latency_ms,
    )


def _stub_narrative(scenario_id: str, compact: dict, lang: str = "en") -> dict:
    """Deterministic placeholder when no API key is set."""
    top_country = (compact.get("top_country_risks") or [{}])[0]
    top_sector  = (compact.get("top_sector_fragility") or [{}])[0]
    iso3 = top_country.get("iso3", "—")
    sector = top_sector.get("industry", "—")
    loss_b = (compact.get("total_output_loss_usd") or 0) / 1e9
    peak_csi = compact.get("peak_csi", 0)

    if lang == "ru":
        return {
            "executive_summary": (
                f"GEDS прогнозирует совокупные потери выпуска ${loss_b:,.0f} млрд для сценария "
                f"«{scenario_id}», пик CSI {peak_csi:.2f}, концентрация ущерба — {iso3} и сектор «{sector}»."
            ),
            "cascade_mechanism": (
                f"Шок распространяется от первоначально нарушенных узлов по графу торговых зависимостей. "
                f"{iso3} наиболее уязвим из-за высоких коэффициентов импортного проникновения в секторе "
                f"«{sector}»; SEIRS-буферы запасов исчерпываются примерно через 8–12 недель после "
                "первоначального шока, после чего цепочка передаёт нарушение дальше по сети."
            ),
            "immediate_risks": [
                "Истощение запасов у downstream-производителей в течение 6 недель.",
                "Волатильность спот-цен на рынках полупроводников и фрахта.",
                "Давление на валютные резервы импорто-зависимых развивающихся экономик.",
            ],
            "structural_vulnerabilities": [
                "Концентрация рисков в моно-страновом источнике передовых полупроводников.",
                "Ограниченная способность перенаправления через основные морские проливы.",
                "Недостаточные стратегические резервы критических промышленных ресурсов.",
            ],
            "policy_recommendations": [
                {"action": "Активировать использование стратегических резервов",
                 "target": iso3 if iso3 != "—" else "Правительства G7", "time_horizon_weeks": 2},
                {"action": "Согласовать своп-линии центробанков для снятия валютного давления",
                 "target": "BIS / Федеральная резервная система", "time_horizon_weeks": 4},
                {"action": "Ускорить запуск внутренних мощностей в наиболее затронутом секторе",
                 "target": sector if sector != "—" else "полупроводники", "time_horizon_weeks": 26},
            ],
            "confidence": "low",
        }

    # English (default)
    return {
        "executive_summary": (
            f"GEDS projects ${loss_b:,.0f}B in cumulative output loss for {scenario_id}, "
            f"with peak CSI {peak_csi:.2f} concentrated in {iso3} and the {sector} sector."
        ),
        "cascade_mechanism": (
            f"The shock propagates outward from the original disrupted nodes via the "
            f"trade-dependency graph. {iso3} is most exposed because of "
            f"high import-penetration ratios in {sector}, and SEIRS inventory "
            "buffers run out roughly 8-12 weeks after the initial disruption."
        ),
        "immediate_risks": [
            "Inventory drawdowns at downstream manufacturers within 6 weeks.",
            "Spot-price volatility in semiconductor and shipping markets.",
            "Pressure on currency reserves in import-dependent emerging economies.",
        ],
        "structural_vulnerabilities": [
            "Concentration risk in single-country sourcing for advanced semiconductors.",
            "Limited rerouting capacity around primary maritime chokepoints.",
            "Inadequate strategic reserves for critical industrial inputs.",
        ],
        "policy_recommendations": [
            {"action": "Activate emergency strategic-reserve drawdowns",
             "target": iso3 if iso3 != "—" else "G7 governments", "time_horizon_weeks": 2},
            {"action": "Coordinate central-bank swap lines to absorb FX pressure",
             "target": "BIS / Federal Reserve", "time_horizon_weeks": 4},
            {"action": "Fast-track domestic capacity for the most exposed sector",
             "target": sector if sector != "—" else "semiconductors", "time_horizon_weeks": 26},
        ],
        "confidence": "low",
    }


__all__ = ["GrokPolicyAdvisor", "GrokNarrative"]
