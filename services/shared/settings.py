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


class Settings(AppSettings):
    database_url: str = "postgresql+psycopg://rental:rental@postgres:5432/rental"

    model_config = Config(env_prefix="RENTAL_")


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


class DefaultTariffSettings(AppSettings):
    base_url: str = "http://stubs:3629"
    config_key: str = "pricing:config"
    key_template: str = "pricing:tariff:{id}"

    config_ttl_sec: int = 60
    ttl_sec: int = 600
    offer_ttl_sec: int = 5 * 60
    fallback_greedy_coeff: float = 1.2

    model_config = Config(env_prefix="DEFAULT_TARIFF_")


settings = Settings()
pricing_settings = PricingSettings()
default_tariff_settings = DefaultTariffSettings()
