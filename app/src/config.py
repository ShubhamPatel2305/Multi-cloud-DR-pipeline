from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = Field(default="dr-demo-api")
    app_env: str = Field(default="local")
    app_port: int = Field(default=8080)
    log_level: str = Field(default="info")

    region_id: str = Field(default="aws-mumbai")
    region_priority: int = Field(default=1)

    mongo_uri: str = Field(default="mongodb://mongo:27017/dr_demo")
    mongo_timeout_ms: int = Field(default=2000)

    inject_failure: bool = Field(default=False)
    failure_mode: str = Field(default="none")

    @property
    def is_primary(self) -> bool:
        return self.region_priority == 1


@lru_cache
def get_settings() -> Settings:
    return Settings()
