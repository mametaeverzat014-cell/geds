"""Runtime configuration."""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="GEDS_", env_file=".env", extra="ignore")

    # CORS — supports either an exact list or a regex pattern (or both).
    # In production, set GEDS_CORS_ALLOW_ORIGIN_REGEX="https://geds-.*\.vercel\.app"
    # so every Vercel preview deploy works without a config change.
    cors_allow_origins: list[str] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "https://geds1.vercel.app",
    ]
    cors_allow_origin_regex: str | None = None

    propagation_decay: float = 0.85
    rerouting_efficiency: float = 0.55
    amplification_mu: float = 2.2
    amplification_eps: float = 0.06
    default_threshold: float = 0.45
    recovery_rate: float = 0.07
    stochastic_sigma: float = 0.0

    max_horizon_weeks: int = 156
    stream_throttle_ms: int = 20


settings = Settings()
