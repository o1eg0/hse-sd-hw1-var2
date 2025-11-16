import typing
from pathlib import Path

from pydantic_settings import BaseSettings
from pydantic_settings import SettingsConfigDict as Config

ROOT = Path(__file__).parent.parent.parent


class AppSettings(BaseSettings):
    model_config: typing.ClassVar[Config] = Config(
        extra="ignore",
        env_file=ROOT / ".env",
    )


class PricingSettings(BaseSettings):
    base_url: str = "http://stubs:3629"

    config_ttl_sec: int = 60
    tariff_ttl_sec: int = 10 * 60
    offer_ttl_sec: int = 5 * 60
    fallback_greedy_coeff: float = 1.2

    redis_url: str = "redis://localhost:6379/0"
    redis_config_key: str = "pricing:config"
    redis_template_key: str = "pricing:tariff:{}"

    model_config = Config(env_prefix="PRICING_")


class RentalApiSettings(BaseSettings):
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/postgres"

    model_config = Config(env_prefix="RENTAL_API_")


class RentalQuerySettings(BaseSettings):
    pricing_url: str = "http://localhost:9000"
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/postgres" # Разделены для реплики

    model_config = Config(env_prefix="RENTAL_QUERY_")


pricing_settings = PricingSettings()
rental_api_settings = RentalApiSettings()
rental_query_settings = RentalQuerySettings()
