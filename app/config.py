from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[1]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    woocommerce_store_url: str = ""
    woocommerce_consumer_key: str = ""
    woocommerce_consumer_secret: str = ""
    woocommerce_api_version: str = "wc/v3"
    woocommerce_timeout_seconds: float = 15.0

    @field_validator(
        "woocommerce_store_url",
        "woocommerce_consumer_key",
        "woocommerce_consumer_secret",
        "woocommerce_api_version",
        mode="before",
    )
    @classmethod
    def strip_text(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip()
        return value

    @field_validator("woocommerce_api_version", mode="before")
    @classmethod
    def default_api_version(cls, value: object) -> object:
        if value is None or (isinstance(value, str) and not value.strip()):
            return "wc/v3"
        return value

    @field_validator("woocommerce_timeout_seconds", mode="before")
    @classmethod
    def default_timeout(cls, value: object) -> object:
        if value is None or (isinstance(value, str) and not value.strip()):
            return 15.0
        return value


def get_settings() -> Settings:
    return Settings()
