from __future__ import annotations

import json
from functools import lru_cache
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = Field("Unity Provider Binance Trades", alias="APP_NAME")
    database_url: str = Field(..., alias="DATABASE_URL")

    binance_spot_base_url: str = Field("https://api.binance.com", alias="BINANCE_SPOT_BASE_URL")
    binance_futures_base_url: str = Field("https://fapi.binance.com", alias="BINANCE_FUTURES_BASE_URL")

    binance_master_api_key: str = Field(..., alias="BINANCE_MASTER_API_KEY")
    binance_master_api_secret: str = Field(..., alias="BINANCE_MASTER_API_SECRET")

    binance_subaccount_keys_json: str = Field("{}", alias="BINANCE_SUBACCOUNT_KEYS_JSON")
    binance_recv_window: int = Field(5000, alias="BINANCE_RECV_WINDOW")

    cors_origins_raw: str = Field(
        "http://localhost:5173,http://127.0.0.1:5173",
        alias="CORS_ORIGINS",
    )

    @property
    def subaccount_keys(self) -> dict[str, dict[str, str]]:
        try:
            data = json.loads(self.binance_subaccount_keys_json)
            return data if isinstance(data, dict) else {}
        except json.JSONDecodeError:
            return {}

    @property
    def cors_origins(self) -> list[str]:
        return [x.strip() for x in self.cors_origins_raw.split(",") if x.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()