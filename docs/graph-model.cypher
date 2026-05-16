// GEDS Neo4j graph model.
//
// Conventions:
//   * Node labels: PascalCase singular (Country, Commodity, Sector, Port, Chokepoint).
//   * Relationship types: SCREAMING_SNAKE verbs (EXPORTS, ROUTES_THROUGH, USES).
//   * Every node has a stable natural id (iso3, hs_code) — easy to round-trip to Postgres.
//   * Trade-flow edges carry value, quantity, and year. We model temporal trade as a yearly
//     property snapshot rather than a separate "TradeFlow" node, because path-finding queries
//     are simpler and our temporal granularity is yearly outside the simulation.
//   * For ongoing simulation state, do NOT mutate the graph. Keep state in Redis/Postgres.
//     The graph is structural; state is dynamic.

// ─────────────────────────────────────────────────────────────────────────────
// Constraints & indexes
// ─────────────────────────────────────────────────────────────────────────────

CREATE CONSTRAINT country_iso3       IF NOT EXISTS FOR (c:Country)    REQUIRE c.iso3   IS UNIQUE;
CREATE CONSTRAINT commodity_hs       IF NOT EXISTS FOR (k:Commodity)  REQUIRE k.hs     IS UNIQUE;
CREATE CONSTRAINT sector_code        IF NOT EXISTS FOR (s:Sector)     REQUIRE s.code   IS UNIQUE;
CREATE CONSTRAINT chokepoint_id      IF NOT EXISTS FOR (cp:Chokepoint) REQUIRE cp.id   IS UNIQUE;
CREATE CONSTRAINT port_id            IF NOT EXISTS FOR (p:Port)       REQUIRE p.id     IS UNIQUE;
CREATE INDEX country_name            IF NOT EXISTS FOR (c:Country)    ON (c.name);
CREATE INDEX commodity_criticality   IF NOT EXISTS FOR (k:Commodity)  ON (k.criticality);

// ─────────────────────────────────────────────────────────────────────────────
// Node creation patterns (driven by ingest from Postgres)
// ─────────────────────────────────────────────────────────────────────────────

// Country
MERGE (c:Country {iso3: $iso3})
ON CREATE SET c.name = $name, c.region = $region, c.created_at = datetime()
ON MATCH  SET c.gdp_usd = $gdp_usd, c.population = $population, c.updated_at = datetime();

// Sector
MERGE (s:Sector {code: $code})
ON CREATE SET s.name = $name, s.created_at = datetime();

// Commodity
MERGE (k:Commodity {hs: $hs})
ON CREATE SET k.name = $name, k.created_at = datetime()
ON MATCH  SET k.criticality = $criticality, k.substitutability = $substitutability;

// Chokepoint
MERGE (cp:Chokepoint {id: $id})
ON CREATE SET cp.name = $name, cp.kind = $kind, cp.lat = $lat, cp.lon = $lon,
              cp.daily_capacity_usd = $daily_capacity_usd, cp.created_at = datetime();

// ─────────────────────────────────────────────────────────────────────────────
// Relationship patterns
// ─────────────────────────────────────────────────────────────────────────────

// Country EXPORTS commodity to Country — yearly snapshot.
// We MERGE on (exporter, importer, hs, year) so updates are idempotent.
MATCH (a:Country {iso3: $exporter}), (b:Country {iso3: $importer}), (k:Commodity {hs: $hs})
MERGE (a)-[r:EXPORTS {hs: $hs, year: $year}]->(b)
SET r.value_usd = $value_usd,
    r.quantity_kg = $quantity_kg,
    r.dataset_version = $dataset_version,
    r.updated_at = datetime();

// Country DEPENDS_ON a commodity, with HHI and top partner.
MATCH (c:Country {iso3: $iso3}), (k:Commodity {hs: $hs})
MERGE (c)-[r:DEPENDS_ON {year: $year}]->(k)
SET r.import_share = $import_share,
    r.hhi_partners = $hhi_partners,
    r.top_partner_iso3 = $top_partner,
    r.stockpile_ratio = $stockpile_ratio,
    r.alt_capacity_idx = $alt_capacity_idx;

// Country PRODUCES via Sector.
MATCH (c:Country {iso3: $iso3}), (s:Sector {code: $sector})
MERGE (c)-[r:PRODUCES {year: $year}]->(s)
SET r.output_usd = $output, r.employment = $employment, r.gva_usd = $gva;

// Sector USES a commodity (input-output linkage).
MATCH (s:Sector {code: $sector}), (k:Commodity {hs: $hs})
MERGE (s)-[r:USES]->(k)
SET r.intensity = $intensity;

// Sector FEEDS another Sector (intersectoral coupling).
MATCH (s1:Sector {code: $from}), (s2:Sector {code: $to})
MERGE (s1)-[r:FEEDS]->(s2)
SET r.intensity = $intensity;

// Country ROUTES_THROUGH a Chokepoint for trade with another country.
// We store the fraction of bilateral flow that uses this chokepoint.
MATCH (a:Country {iso3: $exporter}), (b:Country {iso3: $importer}), (cp:Chokepoint {id: $chokepoint_id})
MERGE (a)-[r:ROUTES_THROUGH {to: $importer, chokepoint: $chokepoint_id}]->(cp)
SET r.flow_share = $flow_share;

// Port LOCATED_IN country.
MATCH (p:Port {id: $port_id}), (c:Country {iso3: $iso3})
MERGE (p)-[:LOCATED_IN]->(c);

// ─────────────────────────────────────────────────────────────────────────────
// Query patterns used by the platform
// ─────────────────────────────────────────────────────────────────────────────

// Q1: Top 10 most concentrated dependencies for a country (HHI close to 1).
MATCH (c:Country {iso3: $iso3})-[d:DEPENDS_ON {year: $year}]->(k:Commodity)
RETURN k.hs, k.name, d.hhi_partners, d.top_partner_iso3, d.top_partner_share
ORDER BY d.hhi_partners DESC
LIMIT 10;

// Q2: For a disrupted exporter+commodity, list importers affected and their dependency.
MATCH (exp:Country {iso3: $exporter})-[e:EXPORTS {hs: $hs, year: $year}]->(imp:Country)
WITH imp, e.value_usd AS flow
MATCH (imp)-[d:DEPENDS_ON {year: $year}]->(k:Commodity {hs: $hs})
RETURN imp.iso3 AS importer, flow, d.import_share, d.hhi_partners, d.top_partner_iso3
ORDER BY d.import_share DESC;

// Q3: K-shortest alternative export paths for a commodity from origin to destination,
//     excluding a disrupted chokepoint. (NetworkX in the simulator does this faster; this
//     query is for ad-hoc analysis and validation.)
MATCH path = (o:Country {iso3: $origin})-[:EXPORTS*1..4 {hs: $hs}]->(d:Country {iso3: $destination})
WHERE NONE (r IN relationships(path)
            WHERE EXISTS {
              MATCH (a:Country)-[r2:ROUTES_THROUGH]->(cp:Chokepoint {id: $disrupted_cp_id})
              WHERE startNode(r2) = startNode(r) AND r2.to = endNode(r).iso3
            })
RETURN path,
       reduce(s = 0.0, rr IN relationships(path) | s + rr.value_usd) AS path_volume
ORDER BY path_volume DESC
LIMIT 5;

// Q4: Chokepoint criticality — total flow value routed through each chokepoint.
MATCH (a:Country)-[r:ROUTES_THROUGH]->(cp:Chokepoint)
MATCH (a)-[e:EXPORTS]->(b:Country {iso3: r.to})
WHERE e.year = $year
WITH cp, sum(r.flow_share * e.value_usd) AS routed_value
RETURN cp.name, cp.kind, routed_value
ORDER BY routed_value DESC;

// Q5: Betweenness-like centrality on the export network (approximate, using path sampling).
//     For the precise GDS betweenness, see the GDS algorithm calls below.
CALL gds.graph.project.cypher(
  'trade_graph',
  'MATCH (c:Country) RETURN id(c) AS id',
  'MATCH (a:Country)-[e:EXPORTS {year: $year}]->(b:Country)
   RETURN id(a) AS source, id(b) AS target, e.value_usd AS weight',
  { parameters: { year: $year } }
);
CALL gds.betweenness.stream('trade_graph')
YIELD nodeId, score
RETURN gds.util.asNode(nodeId).iso3 AS iso3, score
ORDER BY score DESC LIMIT 25;

// Q6: For a country, surface the "Top 5 single-point-of-failure" commodities,
//     defined as: high import_share × high HHI × low alt_capacity_idx × high criticality.
MATCH (c:Country {iso3: $iso3})-[d:DEPENDS_ON {year: $year}]->(k:Commodity)
WITH c, k, d,
     d.import_share * d.hhi_partners * (1.0 - coalesce(d.alt_capacity_idx, 0.0)) * coalesce(k.criticality, 0.5) AS fragility
RETURN k.hs, k.name, fragility, d.top_partner_iso3, d.top_partner_share
ORDER BY fragility DESC LIMIT 5;

// Q7: 2-hop contagion — who is exposed to a shock at origin O via at-most one intermediary?
MATCH (o:Country {iso3: $origin})-[e1:EXPORTS {hs: $hs, year: $year}]->(mid:Country)
MATCH (mid)-[e2:EXPORTS {hs: $hs, year: $year}]->(target:Country)
WHERE target.iso3 <> $origin
WITH target, sum(e1.value_usd * e2.value_usd) AS exposure
RETURN target.iso3, exposure
ORDER BY exposure DESC LIMIT 25;

// ─────────────────────────────────────────────────────────────────────────────
// GDS projections used by the analytics service
// ─────────────────────────────────────────────────────────────────────────────

// Native projection of the country-commodity bipartite-ish graph for embeddings.
CALL gds.graph.project.cypher(
  'country_commodity',
  '
    MATCH (c:Country)    RETURN id(c) AS id, "Country"   AS label, c.iso3 AS key
    UNION
    MATCH (k:Commodity)  RETURN id(k) AS id, "Commodity" AS label, k.hs   AS key
  ',
  '
    MATCH (c:Country)-[d:DEPENDS_ON]->(k:Commodity)
    RETURN id(c) AS source, id(k) AS target, d.import_share AS weight, "DEPENDS_ON" AS type
  '
);

// FastRP embeddings — fed into the GNN as initialization, and into the XGBoost feature set.
CALL gds.fastRP.write('country_commodity', {
  embeddingDimension: 128,
  writeProperty: 'frp_emb',
  relationshipWeightProperty: 'weight'
});

// Louvain communities — useful for "trade bloc" detection visualizations.
CALL gds.louvain.write('country_commodity', { writeProperty: 'community' });

// ─────────────────────────────────────────────────────────────────────────────
// Maintenance
// ─────────────────────────────────────────────────────────────────────────────

// Drop a stale dataset version's edges (used when rolling back a bad ingest).
MATCH ()-[e:EXPORTS {dataset_version: $stale_version}]->()
DELETE e;
