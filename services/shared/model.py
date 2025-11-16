from dataclasses import dataclass
from datetime import datetime
from typing import Any

from pydantic import BaseModel

# Содержит в себе DTO (data transfer objects) / данные, получаемые из внешних источников


@dataclass
class Slot:
    index: int
    empty: bool
    charge: int


@dataclass
class StationData:
    id: str
    tariff_id: str
    location: str
    slots: list[Slot]
    country: str = "RU"


@dataclass
class Tariff:
    id: str
    price_per_hour: float
    free_period_min: int
    default_deposit: int
    currency: str = "RUB"


@dataclass
class UserProfile:
    id: str
    has_subscribtion: bool
    trusted: bool


@dataclass
class OfferData:
    id: str
    user_id: str
    station_id: str
    price_per_hour: float
    free_period_min: int
    deposit: int
    expires_at: datetime
    currency: str = "RUB"
    country: str = "RU"


@dataclass
class Config:
    price_coeff_settings: dict[str, Any]
    tariff_cache_ttl_sec: int
    offer_ttl_sec: int
    fallback_greedy_coeff: float


@dataclass
class OrderData:
    id: str
    user_id: str
    start_station_id: str
    finish_station_id: str
    price_per_hour: float
    free_period_min: int
    deposit: int
    total_amount: int
    start_time: datetime
    finish_time: datetime
    offer_id: str
    powerbank_id: str
    status: str  # "created" | "active" | "returned" | "closed"
    currency: str = "RUB"


@dataclass
class PaymentData:
    id: str
    order_id: str
    kind: str  # "authorize" | "capture" | "refund"
    amount: int
    currency: str
    status: str  # "pending" | "succeeded" | "failed"
    provider_ref: str | None = None


class RentInfo(BaseModel):
    order_id: str
    status: str
    country: str
    currency: str
    started_at: datetime
    ended_at: datetime | None = None
    accrued_amount: int


class ConfigMap:
    def __init__(self, data: dict):
        self._data = data
        for k, v in data.items():
            self.__setattr__(k, v)

    def __getattr__(self, item):
        return self._data.get(item, None)


@dataclass
class EjectResponse:
    success: bool
    powerbank_id: str
