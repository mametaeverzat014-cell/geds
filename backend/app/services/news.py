"""Live news ingestion → NER → graph-node mapping → parameter delta proposal.

Pipeline
--------
1.  fetch_all(): pull headlines from configured providers (NewsAPI, GNews)
2.  classify(): regex-tag each headline as strike/conflict/disaster/policy/logistics
3.  extract_entities(): spaCy NER → ORG, GPE, FAC entities (with keyword fallback)
4.  match_nodes(): fuzzy-match entities to GEDS graph node IDs via rapidfuzz
5.  propose_deltas(): for each match, suggest ΔVulnerability + ΔD_eff multiplier
6.  event_logger.log(): persist (event, suggested delta, predicted impact) for
    later "what we expected vs what actually happened" supervised training

API keys (environment)
----------------------
    NEWSAPI_KEY     https://newsapi.org/  (free tier: 100 req/day, 1 month history)
    GNEWS_KEY       https://gnews.io/     (free tier: 100 req/day, 1 day history)

Endpoints called
----------------
    GET https://newsapi.org/v2/everything
        ?q=...&pageSize=100&language=en
    GET https://gnews.io/api/v4/search
        ?q=...&max=100&lang=en

NER fallback: if spaCy isn't installed, we degrade to keyword-only matching.
This keeps the dev path zero-config while still passing the event metadata
through to the engine.
"""

from __future__ import annotations

import json
import logging
import os
import re
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterable

try:
    import httpx
except ImportError:
    httpx = None

try:
    import spacy
    try:
        _NLP = spacy.load("en_core_web_sm")
        _SPACY_OK = True
    except OSError:
        _NLP = None
        _SPACY_OK = False
except ImportError:
    _NLP = None
    _SPACY_OK = False

try:
    from rapidfuzz import fuzz, process as fuzz_process
    _FUZZ_OK = True
except ImportError:
    fuzz = None
    fuzz_process = None
    _FUZZ_OK = False


log = logging.getLogger("geds.news")


# ─────────────────────────── classification rules ───────────────────────────


EVENT_KEYWORDS: dict[str, list[str]] = {
    "strike":    ["strike", "walkout", "labor dispute", "union action", "work stoppage",
                  "picket", "halt shipments", "halts shipments", "production stoppage"],
    "conflict":  ["war", "invasion", "missile", "airstrike", "blockade", "sanctions",
                  "drone attack", "naval clash", "military escalation",
                  "tensions", "military exercises", "cross-strait"],
    "disaster":  ["earthquake", "tsunami", "flood", "hurricane", "typhoon",
                  "wildfire", "drought", "volcanic", "landslide"],
    "policy":    ["tariff", "export ban", "export control", "embargo", "trade restriction",
                  "retaliatory duties", "export curb"],
    "logistics": ["port closure", "canal blockage", "strait closed", "shipping disruption",
                  "container shortage", "vessel grounded", "vessel grounding",
                  "ran aground", "canal traffic", "shipping delay", "rerouted",
                  "chip shortage", "semiconductor shortage", "supply tightens"],
}

# Per event-type heuristic impact deltas
EVENT_IMPACT_RULES: dict[str, dict[str, float]] = {
    "strike":    {"vuln_delta": +0.05, "d_eff_multiplier": 0.92, "decay_weeks": 4},
    "conflict":  {"vuln_delta": +0.15, "d_eff_multiplier": 0.80, "decay_weeks": 12},
    "disaster":  {"vuln_delta": +0.20, "d_eff_multiplier": 0.70, "decay_weeks": 8},
    "policy":    {"vuln_delta": +0.10, "d_eff_multiplier": 0.85, "decay_weeks": 26},
    "logistics": {"vuln_delta": +0.10, "d_eff_multiplier": 0.85, "decay_weeks": 6},
}


# Country name → ISO3 (extend as graph grows)
COUNTRY_TO_ISO3: dict[str, str] = {
    "taiwan": "TWN", "united states": "USA", "usa": "USA", "u.s.": "USA",
    "china": "CHN", "japan": "JPN", "germany": "DEU", "south korea": "KOR",
    "korea": "KOR", "netherlands": "NLD", "vietnam": "VNM", "malaysia": "MYS",
    "thailand": "THA", "india": "IND", "mexico": "MEX",
    "brazil": "BRA", "russia": "RUS", "indonesia": "IDN",
}

# Industry/sector keyword → GEDS Industry value
INDUSTRY_KEYWORDS: dict[str, str] = {
    "semiconductor": "semiconductors", "chip": "semiconductors", "tsmc": "semiconductors",
    "wafer": "semiconductors", "foundry": "semiconductors",
    "auto": "automotive", "automotive": "automotive", "car maker": "automotive",
    "ev ": "automotive", "vehicle": "automotive",
    "electronic": "electronics", "smartphone": "electronics", "laptop": "electronics",
    "aerospace": "aerospace", "aircraft": "aerospace", "boeing": "aerospace",
    "airbus": "aerospace",
    "shipping": "shipping", "vessel": "shipping", "container": "shipping",
    "freight": "shipping", "port": "shipping", "maritime": "shipping",
    "oil": "energy", "gas": "energy", "lng": "energy", "crude": "energy", "energy": "energy",
    "consumer goods": "consumer_goods", "retail": "consumer_goods",
    "fmcg": "consumer_goods",
}

# Chokepoint name → node ID
CHOKEPOINT_KEYWORDS: dict[str, str] = {
    "taiwan strait": "CP:TaiwanStrait",
    "malacca": "CP:Malacca",
    "suez": "CP:Suez",
    "hormuz": "CP:Hormuz",
}


# ─────────────────────────── data classes ───────────────────────────────────


@dataclass
class NewsHeadline:
    title: str
    description: str
    source: str
    url: str
    published_at: str         # ISO 8601


@dataclass
class ParameterDelta:
    """Proposed engine adjustment derived from a news event."""
    node_id: str
    vulnerability_delta: float
    d_eff_multiplier: float
    decay_weeks: int
    confidence: float          # 0..1


@dataclass
class ParsedEvent:
    headline: NewsHeadline
    event_type: str            # strike | conflict | disaster | policy | logistics | unknown
    matched_nodes: list[str]
    entities: list[str]        # raw NER outputs (for audit)
    deltas: list[ParameterDelta] = field(default_factory=list)


# ─────────────────────────── providers ──────────────────────────────────────


def _fetch_newsapi(query: str, key: str, page_size: int = 100,
                   hours_back: int = 24) -> list[NewsHeadline]:
    if not httpx:
        log.warning("httpx not installed; skipping NewsAPI")
        return []
    since = (datetime.now(timezone.utc) - timedelta(hours=hours_back)).strftime("%Y-%m-%dT%H:%M:%S")
    params = {"q": query, "pageSize": page_size, "language": "en",
              "from": since, "sortBy": "publishedAt", "apiKey": key}
    try:
        with httpx.Client(timeout=15.0) as client:
            resp = client.get("https://newsapi.org/v2/everything", params=params)
            resp.raise_for_status()
            data = resp.json()
    except Exception as exc:
        log.warning("NewsAPI fetch failed: %s", exc)
        return []
    return [
        NewsHeadline(
            title=a.get("title") or "",
            description=a.get("description") or "",
            source=(a.get("source") or {}).get("name") or "NewsAPI",
            url=a.get("url") or "",
            published_at=a.get("publishedAt") or "",
        )
        for a in data.get("articles", [])
        if a.get("title")
    ]


def _fetch_gnews(query: str, key: str, max_results: int = 100) -> list[NewsHeadline]:
    if not httpx:
        log.warning("httpx not installed; skipping GNews")
        return []
    params = {"q": query, "max": max_results, "lang": "en", "apikey": key}
    try:
        with httpx.Client(timeout=15.0) as client:
            resp = client.get("https://gnews.io/api/v4/search", params=params)
            resp.raise_for_status()
            data = resp.json()
    except Exception as exc:
        log.warning("GNews fetch failed: %s", exc)
        return []
    return [
        NewsHeadline(
            title=a.get("title") or "",
            description=a.get("description") or "",
            source=(a.get("source") or {}).get("name") or "GNews",
            url=a.get("url") or "",
            published_at=a.get("publishedAt") or "",
        )
        for a in data.get("articles", [])
        if a.get("title")
    ]


# ─────────────────────────── classification + NER ───────────────────────────


def classify_event_type(text: str) -> str:
    t = text.lower()
    for evt, kws in EVENT_KEYWORDS.items():
        if any(kw in t for kw in kws):
            return evt
    return "unknown"


def extract_entities(text: str) -> list[str]:
    if _SPACY_OK and _NLP is not None:
        doc = _NLP(text)
        # Keep org, location, facility entities — those are the ones that map to nodes.
        return [ent.text for ent in doc.ents if ent.label_ in {"ORG", "GPE", "LOC", "FAC", "NORP"}]
    # Fallback: extract Capitalized Words (very crude)
    return re.findall(r"\b[A-Z][a-zA-Z]{2,}(?:\s+[A-Z][a-zA-Z]+)*", text)


# ─────────────────────────── node matching ──────────────────────────────────


class NodeMatcher:
    """Fuzzy-match named entities and keywords to GEDS graph node IDs."""

    def __init__(self, node_ids: Iterable[str], node_names: Iterable[str] | None = None):
        self.node_ids = list(node_ids)
        self.node_names = list(node_names) if node_names is not None else list(node_ids)
        # Lowercase searchable corpus aligned with node_ids
        self._corpus = [n.lower() for n in self.node_names]
        self._corpus_id = [n.lower() for n in self.node_ids]

    def match(self, text: str, threshold: int = 75) -> list[tuple[str, float]]:
        """Return list of (node_id, confidence_0_to_1) ranked by score."""
        out: list[tuple[str, float]] = []
        text_l = text.lower()

        # 1. Chokepoint phrase match (highest priority — strong literal signal).
        for kw, node_id in CHOKEPOINT_KEYWORDS.items():
            if kw in text_l and node_id in self.node_ids:
                out.append((node_id, 0.95))

        # 2. (country, industry) co-occurrence: a Taiwan + chips headline maps to TWN:semi.
        countries = [iso for name, iso in COUNTRY_TO_ISO3.items() if name in text_l]
        industries = [ind for kw, ind in INDUSTRY_KEYWORDS.items() if kw in text_l]
        for c in countries:
            for ind in industries:
                node_id = f"{c}:{ind}"
                if node_id in self.node_ids:
                    out.append((node_id, 0.90))
            # Country-only mention → all that country's nodes at medium confidence
            if not industries:
                for nid in self.node_ids:
                    if nid.startswith(f"{c}:"):
                        out.append((nid, 0.55))

        # 3. Fuzzy match of NER entities against node names.
        if _FUZZ_OK:
            for ent in extract_entities(text):
                hits = fuzz_process.extract(
                    ent.lower(), self._corpus, scorer=fuzz.WRatio, limit=3,
                )
                for matched_str, score, idx in hits:
                    if score >= threshold:
                        out.append((self.node_ids[idx], score / 100.0))

        # Dedup keeping highest confidence per node
        best: dict[str, float] = {}
        for nid, conf in out:
            if conf > best.get(nid, 0.0):
                best[nid] = conf
        return sorted(best.items(), key=lambda kv: kv[1], reverse=True)


# ─────────────────────────── high-level pipeline ────────────────────────────


def live_keys_present() -> bool:
    """True if at least one live-news provider API key is configured.

    Used by the API to decide whether `use_stub=false` can actually fetch real
    headlines, or must transparently fall back to labelled demo data.
    """
    return bool(os.environ.get("NEWSAPI_KEY") or os.environ.get("GNEWS_KEY"))


def fetch_all(query: str | None = None, hours_back: int = 24) -> list[NewsHeadline]:
    """Pull from every configured provider; dedup by URL."""
    query = query or (
        "(supply chain OR shipping OR semiconductor OR tariff OR sanctions "
        "OR port closure OR canal OR strait OR strike OR earthquake) "
        "AND (disruption OR shortage OR closure OR delay OR crisis)"
    )
    out: list[NewsHeadline] = []
    if (k := os.environ.get("NEWSAPI_KEY")):
        out.extend(_fetch_newsapi(query, k, hours_back=hours_back))
    if (k := os.environ.get("GNEWS_KEY")):
        out.extend(_fetch_gnews(query, k))
    # Dedup by URL
    seen: set[str] = set()
    deduped: list[NewsHeadline] = []
    for h in out:
        if h.url and h.url not in seen:
            seen.add(h.url)
            deduped.append(h)
    return deduped


def parse_headline(headline: NewsHeadline, matcher: NodeMatcher) -> ParsedEvent:
    text = f"{headline.title}. {headline.description}"
    event_type = classify_event_type(text)
    entities = extract_entities(text)
    matched = matcher.match(text)

    deltas: list[ParameterDelta] = []
    rule = EVENT_IMPACT_RULES.get(event_type)
    if rule:
        for node_id, conf in matched:
            deltas.append(ParameterDelta(
                node_id=node_id,
                vulnerability_delta=rule["vuln_delta"] * conf,
                d_eff_multiplier=1.0 - (1.0 - rule["d_eff_multiplier"]) * conf,
                decay_weeks=int(rule["decay_weeks"]),
                confidence=conf,
            ))

    return ParsedEvent(
        headline=headline,
        event_type=event_type,
        matched_nodes=[nid for nid, _ in matched],
        entities=entities,
        deltas=deltas,
    )


def run_pipeline(
    node_ids: Iterable[str],
    node_names: Iterable[str] | None = None,
    query: str | None = None,
    hours_back: int = 24,
    persist: bool = True,
) -> list[ParsedEvent]:
    """End-to-end: fetch → parse → optionally persist to news_cache/."""
    matcher = NodeMatcher(node_ids, node_names)
    headlines = fetch_all(query=query, hours_back=hours_back)
    parsed = [parse_headline(h, matcher) for h in headlines]

    if persist:
        _persist_events(parsed)
    return parsed


def _persist_events(parsed: list[ParsedEvent]) -> None:
    out_dir = Path(__file__).parent.parent.parent / "data" / "news_cache"
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    f = out_dir / f"events-{stamp}.json"
    f.write_text(
        json.dumps(
            [
                {
                    "headline": asdict(e.headline),
                    "event_type": e.event_type,
                    "matched_nodes": e.matched_nodes,
                    "entities": e.entities,
                    "deltas": [asdict(d) for d in e.deltas],
                }
                for e in parsed
            ],
            indent=2,
        ),
        encoding="utf-8",
    )


# ─────────────────────────── stub mode for dev ──────────────────────────────


def stub_headlines(lang: str = "en") -> list[NewsHeadline]:
    """Synthetic headlines used when no API keys are configured."""
    now = datetime.now(timezone.utc).isoformat()
    if lang == "ru":
        return [
            NewsHeadline(
                title="TSMC приостанавливает поставки на фоне напряжённости вокруг Тайваньского пролива",
                description="Компания TSMC сообщила о временной приостановке экспорта пластин передовых техпроцессов "
                            "в связи с эскалацией военных учений в проливе.",
                source="stub-Reuters", url="https://example.com/tsmc-strait", published_at=now,
            ),
            NewsHeadline(
                title="Движение по Суэцкому каналу задержано из-за посадки судна на мель",
                description="400-метровый контейнеровоз сел на мель в Суэцком канале, перекрыв северное направление "
                            "и заставив суда перенаправляться вокруг мыса Доброй Надежды.",
                source="stub-FT", url="https://example.com/suez-block", published_at=now,
            ),
            NewsHeadline(
                title="Автопром Германии страдает от расширяющегося дефицита чипов",
                description="Немецкие автопроизводители сообщают об остановках производства на фоне сокращения поставок полупроводников.",
                source="stub-Bloomberg", url="https://example.com/de-auto", published_at=now,
            ),
        ]
    return [
        NewsHeadline(
            title="TSMC Taiwan facility halts shipments amid strait tensions",
            description="Taiwan Semiconductor Manufacturing Company reported temporary suspension of "
                        "advanced-node wafer exports as cross-strait military exercises escalate.",
            source="stub-Reuters", url="https://example.com/tsmc-strait", published_at=now,
        ),
        NewsHeadline(
            title="Suez Canal traffic delayed after vessel grounding",
            description="A 400-meter container ship ran aground in the Suez Canal, blocking northbound "
                        "traffic and forcing reroutes around the Cape of Good Hope.",
            source="stub-FT", url="https://example.com/suez-block", published_at=now,
        ),
        NewsHeadline(
            title="Germany auto sector hit by widening chip shortage",
            description="German automakers including major manufacturers report production stoppages "
                        "as semiconductor supply tightens.",
            source="stub-Bloomberg", url="https://example.com/de-auto", published_at=now,
        ),
    ]


# ─────────────────────────── overlay / engine integration ──────────────────


@dataclass
class NewsOverlay:
    """Per-node parameter deltas accumulated from accepted news events.

    Applied to the CompiledGraph at the start of each /simulate call so that
    a current "war footing" / "Suez blockage in progress" actually changes
    forecasts, not just the news panel.
    """
    applied_at: str
    active_until: str          # ISO 8601 — overlay is ignored after this
    deltas: dict[str, dict]    # {node_id: {vuln_delta, d_eff_multiplier, confidence, source}}

    def is_active(self) -> bool:
        try:
            until = datetime.fromisoformat(self.active_until.replace("Z", "+00:00"))
            return datetime.now(timezone.utc) < until
        except (ValueError, AttributeError):
            return False


def overlay_from_events(
    parsed: list[ParsedEvent],
    decay_hours: int = 168,        # 7-day default lifetime
    confidence_floor: float = 0.5,
) -> NewsOverlay:
    """Aggregate parsed events into a single overlay by node.

    When multiple events touch the same node, take the *strongest* delta
    (largest vulnerability bump) — this is the conservative choice for risk
    analysis.  Events below `confidence_floor` are ignored.
    """
    by_node: dict[str, dict] = {}
    for ev in parsed:
        for d in ev.deltas:
            if d.confidence < confidence_floor:
                continue
            existing = by_node.get(d.node_id)
            if existing is None or d.vulnerability_delta > existing["vuln_delta"]:
                by_node[d.node_id] = {
                    "vuln_delta": float(d.vulnerability_delta),
                    "d_eff_multiplier": float(d.d_eff_multiplier),
                    "confidence": float(d.confidence),
                    "source": ev.headline.title[:200],
                    "event_type": ev.event_type,
                }
    now = datetime.now(timezone.utc)
    return NewsOverlay(
        applied_at=now.isoformat(),
        active_until=(now + timedelta(hours=decay_hours)).isoformat(),
        deltas=by_node,
    )


def apply_overlay_to_graph(graph, overlay: NewsOverlay):
    """Return a shallow copy of `graph` with overlay deltas applied.

    - vulnerability[i] += vuln_delta   (clipped to [0.05, 0.99])
    - D_eff row i      *= d_eff_multiplier  (lower → less import dependence)
    - D_eff_dense kept in sync

    `graph` is the engine's CompiledGraph — we keep this dynamic typing rather
    than import the class to avoid a cycle (news is a service, graph is core).
    """
    import copy
    try:
        import numpy as np
        from scipy import sparse
    except ImportError:
        return graph

    if not overlay or not overlay.deltas or not overlay.is_active():
        return graph

    new = copy.copy(graph)
    new.vulnerability = graph.vulnerability.copy()
    D = graph.D_eff.toarray().copy()    # small (40×40); cheap enough

    for node_id, d in overlay.deltas.items():
        idx = graph.index.get(node_id)
        if idx is None:
            continue
        new.vulnerability[idx] = float(np.clip(
            graph.vulnerability[idx] + d["vuln_delta"], 0.05, 0.99
        ))
        # d_eff_multiplier < 1.0 means trade is harder/less reliable (route degraded);
        # > 1.0 means stockpiling. Apply to incoming row (target = idx).
        D[idx, :] *= float(d["d_eff_multiplier"])

    new.D_eff = sparse.csr_matrix(D, dtype=np.float64)
    new.D_eff_dense = D
    return new


__all__ = [
    "NewsHeadline", "ParameterDelta", "ParsedEvent", "NewsOverlay",
    "NodeMatcher",
    "fetch_all", "parse_headline", "run_pipeline", "stub_headlines", "live_keys_present",
    "classify_event_type", "extract_entities",
    "overlay_from_events", "apply_overlay_to_graph",
    "EVENT_KEYWORDS", "EVENT_IMPACT_RULES",
]
