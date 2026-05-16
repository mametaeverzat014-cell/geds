-- GEDS PostgreSQL schema (with TimescaleDB extension).
--
-- Style:
--   * Surrogate UUID PKs for everything user-facing; natural keys for reference data.
--   * Foreign keys ON DELETE RESTRICT by default. ON DELETE CASCADE only for "owned" rows
--     (e.g., simulation_frames belong to simulation_runs).
--   * No soft deletes. Deletions are rare; if needed, archive table.
--   * Timestamps are TIMESTAMPTZ, stored UTC.
--   * Money: NUMERIC(20, 4) USD. No FLOAT for money. Ever.
--   * Indices: btree by default; GIN for JSONB; BRIN for big time-series.

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS timescaledb;
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- ──────────────────────────────────────────────────────────────────────────────
-- Reference data: countries, sectors, commodities, chokepoints
-- ──────────────────────────────────────────────────────────────────────────────

CREATE TABLE countries (
    iso3            CHAR(3)       PRIMARY KEY,        -- 'DEU', 'USA', 'CHN'
    iso2            CHAR(2)       NOT NULL UNIQUE,
    name            TEXT          NOT NULL,
    region          TEXT,
    sub_region      TEXT,
    centroid_lat    DOUBLE PRECISION,
    centroid_lon    DOUBLE PRECISION,
    population      BIGINT,
    gdp_usd         NUMERIC(20, 2),
    gdp_per_capita  NUMERIC(14, 2),
    gini            NUMERIC(5, 2),
    inflation_yoy   NUMERIC(6, 3),
    created_at      TIMESTAMPTZ   NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ   NOT NULL DEFAULT now()
);

CREATE TABLE sectors (
    code            TEXT          PRIMARY KEY,        -- ISIC rev.4 code or our own taxonomy
    name            TEXT          NOT NULL,
    parent_code     TEXT          REFERENCES sectors(code),
    description     TEXT
);

CREATE TABLE commodities (
    hs_code         TEXT          PRIMARY KEY,        -- HS6 or HS4 depending on granularity
    name            TEXT          NOT NULL,
    sector_code     TEXT          REFERENCES sectors(code),
    criticality     NUMERIC(4, 3) CHECK (criticality BETWEEN 0 AND 1),  -- 0..1, learned
    substitutability NUMERIC(4, 3) CHECK (substitutability BETWEEN 0 AND 1)
);
CREATE INDEX idx_commodities_sector ON commodities(sector_code);

CREATE TABLE chokepoints (
    id              UUID          PRIMARY KEY DEFAULT uuid_generate_v4(),
    name            TEXT          NOT NULL UNIQUE,
    kind            TEXT          NOT NULL CHECK (kind IN ('canal','strait','port','overland','airspace')),
    lat             DOUBLE PRECISION NOT NULL,
    lon             DOUBLE PRECISION NOT NULL,
    daily_capacity_usd NUMERIC(20, 2),                 -- estimated daily throughput in USD
    annual_share_global_trade NUMERIC(6, 4)            -- fraction of global trade routed through it
);

CREATE TABLE ports (
    id              UUID          PRIMARY KEY DEFAULT uuid_generate_v4(),
    name            TEXT          NOT NULL,
    iso3            CHAR(3)       NOT NULL REFERENCES countries(iso3),
    lat             DOUBLE PRECISION NOT NULL,
    lon             DOUBLE PRECISION NOT NULL,
    annual_throughput_teu BIGINT,
    UNIQUE (name, iso3)
);

-- ──────────────────────────────────────────────────────────────────────────────
-- Trade flows and dependencies
-- ──────────────────────────────────────────────────────────────────────────────

CREATE TABLE trade_flows (
    id              BIGSERIAL     PRIMARY KEY,
    exporter_iso3   CHAR(3)       NOT NULL REFERENCES countries(iso3),
    importer_iso3   CHAR(3)       NOT NULL REFERENCES countries(iso3),
    hs_code         TEXT          NOT NULL REFERENCES commodities(hs_code),
    year            SMALLINT      NOT NULL,
    value_usd       NUMERIC(20, 2) NOT NULL,
    quantity_kg     NUMERIC(20, 2),
    source          TEXT          NOT NULL,           -- 'comtrade', 'wto', 'oecd'
    dataset_version TEXT          NOT NULL,           -- version pointer; see ingest doc
    CONSTRAINT trade_flows_unique UNIQUE (exporter_iso3, importer_iso3, hs_code, year, dataset_version),
    CHECK (exporter_iso3 <> importer_iso3),
    CHECK (year BETWEEN 1990 AND 2100)
);
CREATE INDEX idx_trade_exporter   ON trade_flows (exporter_iso3, year, hs_code);
CREATE INDEX idx_trade_importer   ON trade_flows (importer_iso3, year, hs_code);
CREATE INDEX idx_trade_commodity  ON trade_flows (hs_code, year);

CREATE TABLE production (
    iso3            CHAR(3)       NOT NULL REFERENCES countries(iso3),
    sector_code     TEXT          NOT NULL REFERENCES sectors(code),
    year            SMALLINT      NOT NULL,
    output_usd      NUMERIC(20, 2),
    employment      BIGINT,
    gva_usd         NUMERIC(20, 2),
    PRIMARY KEY (iso3, sector_code, year)
);

CREATE TABLE dependencies (
    iso3            CHAR(3)       NOT NULL REFERENCES countries(iso3),
    hs_code         TEXT          NOT NULL REFERENCES commodities(hs_code),
    year            SMALLINT      NOT NULL,
    import_share    NUMERIC(5, 4) NOT NULL CHECK (import_share BETWEEN 0 AND 1),
    hhi_partners    NUMERIC(5, 4) NOT NULL CHECK (hhi_partners BETWEEN 0 AND 1),
    top_partner_iso3 CHAR(3)      REFERENCES countries(iso3),
    top_partner_share NUMERIC(5, 4) CHECK (top_partner_share BETWEEN 0 AND 1),
    stockpile_ratio NUMERIC(6, 3),                    -- reserves / annual consumption
    alt_capacity_idx NUMERIC(5, 4),                   -- 0..1, alternative-supplier capacity index
    PRIMARY KEY (iso3, hs_code, year)
);

-- Input-output coefficients: how much of commodity k is used in producing commodity k' in country c
CREATE TABLE input_output_coefficients (
    iso3            CHAR(3)       NOT NULL REFERENCES countries(iso3),
    input_hs        TEXT          NOT NULL REFERENCES commodities(hs_code),
    output_hs       TEXT          NOT NULL REFERENCES commodities(hs_code),
    coefficient     NUMERIC(6, 5) NOT NULL CHECK (coefficient BETWEEN 0 AND 1),
    year            SMALLINT      NOT NULL,
    PRIMARY KEY (iso3, input_hs, output_hs, year)
);

-- Which chokepoints does a trade-flow route through, and what share?
CREATE TABLE route_chokepoints (
    exporter_iso3   CHAR(3)       NOT NULL REFERENCES countries(iso3),
    importer_iso3   CHAR(3)       NOT NULL REFERENCES countries(iso3),
    chokepoint_id   UUID          NOT NULL REFERENCES chokepoints(id),
    flow_share      NUMERIC(5, 4) NOT NULL CHECK (flow_share BETWEEN 0 AND 1),
    PRIMARY KEY (exporter_iso3, importer_iso3, chokepoint_id)
);

-- ──────────────────────────────────────────────────────────────────────────────
-- Time-series: prices, indices, AIS, inflation, etc. (TimescaleDB hypertables)
-- ──────────────────────────────────────────────────────────────────────────────

CREATE TABLE commodity_prices (
    hs_code         TEXT          NOT NULL REFERENCES commodities(hs_code),
    ts              TIMESTAMPTZ   NOT NULL,
    price_usd       NUMERIC(20, 6) NOT NULL,
    source          TEXT          NOT NULL,
    PRIMARY KEY (hs_code, ts, source)
);
SELECT create_hypertable('commodity_prices', 'ts', chunk_time_interval => INTERVAL '30 days');

CREATE TABLE country_inflation (
    iso3            CHAR(3)       NOT NULL REFERENCES countries(iso3),
    ts              TIMESTAMPTZ   NOT NULL,
    cpi             NUMERIC(12, 4),
    cpi_yoy         NUMERIC(6, 3),
    core_cpi_yoy    NUMERIC(6, 3),
    source          TEXT          NOT NULL,
    PRIMARY KEY (iso3, ts, source)
);
SELECT create_hypertable('country_inflation', 'ts', chunk_time_interval => INTERVAL '90 days');

CREATE TABLE ais_movements (
    id              BIGSERIAL,
    ts              TIMESTAMPTZ   NOT NULL,
    chokepoint_id   UUID          REFERENCES chokepoints(id),
    vessel_count    INT,
    avg_speed_kn    NUMERIC(6, 2),
    cargo_tons_est  NUMERIC(20, 2),
    PRIMARY KEY (id, ts)
);
SELECT create_hypertable('ais_movements', 'ts', chunk_time_interval => INTERVAL '7 days');

-- ──────────────────────────────────────────────────────────────────────────────
-- Historical events: COVID, Suez, Ukraine, oil shocks, chip shortage…
-- Used both as user-visible scenarios and as ML training labels.
-- ──────────────────────────────────────────────────────────────────────────────

CREATE TABLE historical_events (
    id              UUID          PRIMARY KEY DEFAULT uuid_generate_v4(),
    slug            TEXT          NOT NULL UNIQUE,    -- 'covid-supply-2020', 'suez-2021'
    name            TEXT          NOT NULL,
    start_ts        TIMESTAMPTZ   NOT NULL,
    end_ts          TIMESTAMPTZ,
    kind            TEXT          NOT NULL CHECK (kind IN
                        ('pandemic','geopolitical','logistical','commodity','financial','climate','other')),
    affected_iso3   TEXT[]        NOT NULL,
    affected_hs     TEXT[],
    affected_chokepoints UUID[],
    summary         TEXT,
    metadata        JSONB         NOT NULL DEFAULT '{}'
);
CREATE INDEX idx_events_kind ON historical_events(kind);
CREATE INDEX idx_events_metadata_gin ON historical_events USING GIN (metadata);

-- ──────────────────────────────────────────────────────────────────────────────
-- Scenarios: user-defined or AI-generated shock configurations
-- ──────────────────────────────────────────────────────────────────────────────

CREATE TABLE scenarios (
    id              UUID          PRIMARY KEY DEFAULT uuid_generate_v4(),
    name            TEXT          NOT NULL,
    description     TEXT,
    owner_user_id   UUID,                              -- nullable for system-built
    based_on_event  UUID          REFERENCES historical_events(id),
    horizon_weeks   INT           NOT NULL CHECK (horizon_weeks BETWEEN 1 AND 520),
    shocks          JSONB         NOT NULL,            -- array of shock definitions, see schema below
    config          JSONB         NOT NULL DEFAULT '{}', -- noise, ensemble size, rerouting strategy
    is_template     BOOLEAN       NOT NULL DEFAULT false,
    created_at      TIMESTAMPTZ   NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ   NOT NULL DEFAULT now()
);
CREATE INDEX idx_scenarios_owner    ON scenarios(owner_user_id);
CREATE INDEX idx_scenarios_template ON scenarios(is_template) WHERE is_template;
CREATE INDEX idx_scenarios_shocks_gin ON scenarios USING GIN (shocks jsonb_path_ops);

-- Shock object schema (stored in scenarios.shocks JSONB):
--   {
--     "target_kind": "node" | "edge" | "chokepoint" | "commodity",
--     "target":      "DEU" | { "from": "TWN", "to": "USA" } | "<chokepoint_id>" | "8542",
--     "kind":        "multiplicative" | "additive" | "capacity_cap",
--     "magnitude":   0.3,
--     "start_week":  4,
--     "duration_weeks": 12,
--     "decay_curve": "step" | "linear" | "exp",
--     "note":        "Suez throughput capped at 30% for 12w"
--   }

-- ──────────────────────────────────────────────────────────────────────────────
-- Simulation runs and frames (the workhorse tables)
-- ──────────────────────────────────────────────────────────────────────────────

CREATE TABLE simulation_runs (
    id              UUID          PRIMARY KEY DEFAULT uuid_generate_v4(),
    scenario_id     UUID          NOT NULL REFERENCES scenarios(id),
    status          TEXT          NOT NULL CHECK (status IN ('queued','running','succeeded','failed','cancelled')),
    started_at      TIMESTAMPTZ,
    finished_at     TIMESTAMPTZ,
    horizon_weeks   INT           NOT NULL,
    ensemble_size   INT           NOT NULL DEFAULT 1,
    deterministic   BOOLEAN       NOT NULL DEFAULT true,
    config_snapshot JSONB         NOT NULL,            -- the config that was actually used
    graph_version   TEXT          NOT NULL,           -- which graph snapshot was used
    model_versions  JSONB         NOT NULL DEFAULT '{}',
    metrics_summary JSONB,                            -- top-line outputs (peak inflation, etc.)
    error           TEXT,
    requested_by    UUID,
    created_at      TIMESTAMPTZ   NOT NULL DEFAULT now()
);
CREATE INDEX idx_runs_scenario ON simulation_runs(scenario_id, created_at DESC);
CREATE INDEX idx_runs_status   ON simulation_runs(status);

CREATE TABLE simulation_frames (
    run_id          UUID          NOT NULL REFERENCES simulation_runs(id) ON DELETE CASCADE,
    week            INT           NOT NULL,
    iso3            CHAR(3)       NOT NULL REFERENCES countries(iso3),
    hs_code         TEXT          REFERENCES commodities(hs_code),
    shock_state     NUMERIC(6, 5) NOT NULL CHECK (shock_state BETWEEN 0 AND 1),
    inflation_dev   NUMERIC(7, 4),
    gdp_dev         NUMERIC(7, 4),
    shortage_prob   NUMERIC(5, 4) CHECK (shortage_prob BETWEEN 0 AND 1),
    unemp_risk      NUMERIC(6, 4),
    rerouted_share  NUMERIC(5, 4),
    PRIMARY KEY (run_id, week, iso3, hs_code)
);
SELECT create_hypertable('simulation_frames', 'week', chunk_time_interval => 26);
CREATE INDEX idx_frames_run_week ON simulation_frames(run_id, week);
CREATE INDEX idx_frames_country  ON simulation_frames(iso3, week);

-- ──────────────────────────────────────────────────────────────────────────────
-- Forecasts and explanations (from ML models)
-- ──────────────────────────────────────────────────────────────────────────────

CREATE TABLE forecasts (
    id              UUID          PRIMARY KEY DEFAULT uuid_generate_v4(),
    run_id          UUID          REFERENCES simulation_runs(id) ON DELETE CASCADE,
    model_name      TEXT          NOT NULL,
    model_version   TEXT          NOT NULL,
    target          TEXT          NOT NULL,           -- 'inflation', 'gdp', 'shortage', 'unemployment'
    iso3            CHAR(3)       REFERENCES countries(iso3),
    hs_code         TEXT          REFERENCES commodities(hs_code),
    horizon_week    INT           NOT NULL,
    point_estimate  NUMERIC(20, 6),
    p10             NUMERIC(20, 6),
    p50             NUMERIC(20, 6),
    p90             NUMERIC(20, 6),
    attributions    JSONB,                            -- SHAP values or GNN node importances
    created_at      TIMESTAMPTZ   NOT NULL DEFAULT now()
);
CREATE INDEX idx_forecasts_run    ON forecasts(run_id);
CREATE INDEX idx_forecasts_target ON forecasts(target, iso3, horizon_week);

-- ──────────────────────────────────────────────────────────────────────────────
-- Policy recommendations (from the AI policy advisor)
-- ──────────────────────────────────────────────────────────────────────────────

CREATE TABLE policy_recommendations (
    id              UUID          PRIMARY KEY DEFAULT uuid_generate_v4(),
    scenario_id     UUID          NOT NULL REFERENCES scenarios(id),
    run_id          UUID          REFERENCES simulation_runs(id),
    iso3            CHAR(3)       NOT NULL REFERENCES countries(iso3),
    action_kind     TEXT          NOT NULL CHECK (action_kind IN
                        ('diversify_imports','increase_production','stockpile',
                         'reroute_trade','reduce_dependency','sectoral_subsidy','other')),
    action_detail   JSONB         NOT NULL,
    expected_impact NUMERIC(20, 6),                   -- e.g., GDP saved in USD
    confidence      NUMERIC(4, 3) CHECK (confidence BETWEEN 0 AND 1),
    explanation     TEXT,                             -- human-readable rationale
    priority        INT           NOT NULL,
    created_at      TIMESTAMPTZ   NOT NULL DEFAULT now()
);
CREATE INDEX idx_policy_scenario ON policy_recommendations(scenario_id, priority);

-- ──────────────────────────────────────────────────────────────────────────────
-- Model registry (mirrors what's in object storage for fast queries)
-- ──────────────────────────────────────────────────────────────────────────────

CREATE TABLE model_registry (
    id              UUID          PRIMARY KEY DEFAULT uuid_generate_v4(),
    name            TEXT          NOT NULL,           -- 'gnn_propagation', 'xgb_inflation', 'tft_prices'
    version         TEXT          NOT NULL,           -- semver-ish or git sha
    family          TEXT          NOT NULL CHECK (family IN ('gnn','xgboost','tft','rl','anomaly','ensemble')),
    artifact_uri    TEXT          NOT NULL,           -- s3://… or gs://…
    training_dataset_version TEXT NOT NULL,
    metrics         JSONB         NOT NULL DEFAULT '{}',
    is_active       BOOLEAN       NOT NULL DEFAULT false,
    created_at      TIMESTAMPTZ   NOT NULL DEFAULT now(),
    UNIQUE (name, version)
);
CREATE INDEX idx_models_active ON model_registry(name, is_active) WHERE is_active;

-- ──────────────────────────────────────────────────────────────────────────────
-- Dataset versions (for reproducibility of training and replay)
-- ──────────────────────────────────────────────────────────────────────────────

CREATE TABLE dataset_versions (
    version         TEXT          PRIMARY KEY,        -- '2026-05-01-comtrade-v3'
    source          TEXT          NOT NULL,
    snapshot_at     TIMESTAMPTZ   NOT NULL,
    rowcount        BIGINT,
    sha256          CHAR(64),
    is_active       BOOLEAN       NOT NULL DEFAULT false,
    notes           TEXT
);

-- ──────────────────────────────────────────────────────────────────────────────
-- Users (minimal — auth lives elsewhere in prod)
-- ──────────────────────────────────────────────────────────────────────────────

CREATE TABLE users (
    id              UUID          PRIMARY KEY DEFAULT uuid_generate_v4(),
    email           TEXT          NOT NULL UNIQUE,
    display_name    TEXT,
    role            TEXT          NOT NULL DEFAULT 'analyst' CHECK (role IN ('analyst','researcher','admin','viewer')),
    created_at      TIMESTAMPTZ   NOT NULL DEFAULT now()
);

-- ──────────────────────────────────────────────────────────────────────────────
-- Materialized views for hot dashboard reads
-- ──────────────────────────────────────────────────────────────────────────────

CREATE MATERIALIZED VIEW mv_country_fragility AS
SELECT
    c.iso3,
    c.name,
    AVG(d.hhi_partners)                   AS avg_concentration,
    SUM(d.import_share * com.criticality) AS weighted_criticality,
    -- placeholder formula; real one computed by the analytics service
    (1.0 - AVG(d.alt_capacity_idx)) * AVG(d.hhi_partners) AS fragility_index
FROM countries c
LEFT JOIN dependencies d ON d.iso3 = c.iso3
LEFT JOIN commodities  com ON com.hs_code = d.hs_code
WHERE d.year = (SELECT MAX(year) FROM dependencies)
GROUP BY c.iso3, c.name;
CREATE UNIQUE INDEX idx_mv_country_fragility_iso3 ON mv_country_fragility(iso3);

-- Refresh strategy: nightly, plus on-demand after ingest. Concurrent refresh so reads don't block.

-- ──────────────────────────────────────────────────────────────────────────────
-- Triggers: keep updated_at fresh
-- ──────────────────────────────────────────────────────────────────────────────

CREATE OR REPLACE FUNCTION touch_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_countries_updated  BEFORE UPDATE ON countries  FOR EACH ROW EXECUTE FUNCTION touch_updated_at();
CREATE TRIGGER trg_scenarios_updated  BEFORE UPDATE ON scenarios  FOR EACH ROW EXECUTE FUNCTION touch_updated_at();
