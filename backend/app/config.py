"""Application configuration from environment variables."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Station connection
    marstek_ip: str = "192.168.1.100"
    marstek_port: int = 30000
    demo_mode: bool = True

    # Battery / estimator
    battery_capacity_wh: float = 5120.0
    min_soc_reserve_pct: float = 12.0
    inverter_efficiency: float = 0.95
    avg_window_seconds: int = 12

    # Polling
    poll_interval_seconds: float = 2.0
    udp_timeout_seconds: float = 2.0

    # Server
    host: str = "0.0.0.0"
    port: int = 8000
    cors_origins: str = "*"


@lru_cache
def get_settings() -> Settings:
    return Settings()
