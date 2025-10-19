import typing
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).parent.parent.parent


class AppSettings(BaseSettings):
    model_config: typing.ClassVar[SettingsConfigDict] = SettingsConfigDict(
        extra="ignore",
        env_file=ROOT / ".env",
    )


class HTTPBackendSettings(AppSettings):
    workers: int = 4
    loop: str = "asyncio"
    host: str = "0.0.0.0"
    port: int = 3629
    timeout_keep_alive: int = 70
    backlog: int = 2048
    reload: bool = False

    model_config = SettingsConfigDict(env_prefix="HTTP_BACKEND_")
