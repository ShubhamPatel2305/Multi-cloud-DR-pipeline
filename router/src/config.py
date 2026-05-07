from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    router_port: int = Field(default=8000)
    poll_interval_seconds: float = Field(default=3.0)
    deep_probe_interval_seconds: float = Field(default=15.0)

    unhealthy_threshold: int = Field(default=2)
    healthy_threshold: int = Field(default=2)

    origin_primary_url: str = Field(default="http://aws-mumbai:8080")
    origin_standby_url: str = Field(default="http://aws-singapore:8080")
    origin_dr_url: str = Field(default="http://azure-secondary:8080")


@lru_cache
def get_settings() -> Settings:
    return Settings()
