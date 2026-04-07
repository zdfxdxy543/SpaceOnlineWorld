from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DATABASE_URL = f"sqlite:///{(BACKEND_ROOT / 'onlineworld.db').as_posix()}"
DEFAULT_NETDISK_STORAGE_DIR = str((BACKEND_ROOT / "storage" / "netdisk").resolve())


def _parse_origins(value: str | None) -> tuple[str, ...]:
    if not value:
        return (
            "http://localhost:5173",
            "http://127.0.0.1:5173",
        )

    return tuple(origin.strip() for origin in value.split(",") if origin.strip())


def _parse_probability(value: str | None, *, default: float) -> float:
    if value is None:
        return default
    try:
        parsed = float(value)
    except ValueError:
        return default
    return max(0.0, min(1.0, parsed))


def _parse_non_negative_float(value: str | None, *, default: float) -> float:
    if value is None:
        return default
    try:
        parsed = float(value)
    except ValueError:
        return default
    return max(0.0, parsed)


def _parse_positive_int(value: str | None, *, default: int) -> int:
    if value is None:
        return default
    try:
        parsed = int(value)
    except ValueError:
        return default
    return max(1, parsed)


@dataclass(frozen=True)
class Settings:
    app_name: str = "OnlineWorld Backend"
    environment: str = os.getenv("ENVIRONMENT", "development")
    debug: bool = os.getenv("DEBUG", "false").lower() == "true"
    api_prefix: str = "/api/v1"
    database_url: str = os.getenv("DATABASE_URL", DEFAULT_DATABASE_URL)
    llm_provider: str = os.getenv("LLM_PROVIDER", "siliconflow")
    llm_model: str = os.getenv("LLM_MODEL", os.getenv("SILICONFLOW_CONTENT_MODEL", "Pro/deepseek-ai/DeepSeek-V3.2"))
    siliconflow_api_key: str = os.getenv("SILICONFLOW_API_KEY", "sk-vxnqqulpbrduxkhpxmsfebvhyvwdxjebofqcjtdsjrggebvv")
    siliconflow_base_url: str = os.getenv("SILICONFLOW_BASE_URL", "https://api.siliconflow.cn/v1")
    siliconflow_planner_model: str = os.getenv("SILICONFLOW_PLANNER_MODEL", "Pro/deepseek-ai/DeepSeek-V3.2")
    siliconflow_content_timeout_seconds: float = _parse_non_negative_float(
        os.getenv("SILICONFLOW_CONTENT_TIMEOUT_SECONDS"), default=90.0
    )
    siliconflow_content_retry_backoff_seconds: float = _parse_non_negative_float(
        os.getenv("SILICONFLOW_CONTENT_RETRY_BACKOFF_SECONDS"), default=1.5
    )
    netdisk_storage_dir: str = os.getenv("NETDISK_STORAGE_DIR", DEFAULT_NETDISK_STORAGE_DIR)
    scheduler_new_actor_probability: float = _parse_probability(
        os.getenv("SCHEDULER_NEW_ACTOR_PROBABILITY"), default=0.30
    )
    scheduler_target_actor_count: int = _parse_positive_int(
        os.getenv("SCHEDULER_TARGET_ACTOR_COUNT"), default=3
    )
    scheduler_publication_delay_probability: float = _parse_probability(
        os.getenv("SCHEDULER_PUBLICATION_DELAY_PROBABILITY"), default=0.60
    )
    scheduler_publication_delay_min_seconds: float = _parse_non_negative_float(
        os.getenv("SCHEDULER_PUBLICATION_DELAY_MIN_SECONDS"), default=1.0
    )
    scheduler_publication_delay_max_seconds: float = _parse_non_negative_float(
        os.getenv("SCHEDULER_PUBLICATION_DELAY_MAX_SECONDS"), default=5.0
    )
    scheduler_life_netdisk_probability: float = _parse_probability(
        os.getenv("SCHEDULER_LIFE_NETDISK_PROBABILITY"), default=0.15
    )
    scheduler_life_news_probability: float = _parse_probability(
        os.getenv("SCHEDULER_LIFE_NEWS_PROBABILITY"), default=0.08
    )
    scheduler_life_arc_reveal_after_hours: float = _parse_non_negative_float(
        os.getenv("SCHEDULER_LIFE_ARC_REVEAL_AFTER_HOURS"), default=1.0
    )
    scheduler_life_arc_news_resolution_probability: float = _parse_probability(
        os.getenv("SCHEDULER_LIFE_ARC_NEWS_RESOLUTION_PROBABILITY"), default=0.35
    )
    scheduler_detective_arc_reveal_after_hours: float = _parse_non_negative_float(
        os.getenv("SCHEDULER_DETECTIVE_ARC_REVEAL_AFTER_HOURS"), default=1.0
    )
    scheduler_detective_arc_news_resolution_probability: float = _parse_probability(
        os.getenv("SCHEDULER_DETECTIVE_ARC_NEWS_RESOLUTION_PROBABILITY"), default=0.55
    )
    scheduler_detective_arc_netdisk_probability: float = _parse_probability(
        os.getenv("SCHEDULER_DETECTIVE_ARC_NETDISK_PROBABILITY"), default=0.65
    )
    cors_origins: tuple[str, ...] = _parse_origins(os.getenv("CORS_ORIGINS"))


def get_settings() -> Settings:
    return Settings()
