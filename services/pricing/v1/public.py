from datetime import datetime, timedelta
from typing import Literal

import httpx
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from redis.asyncio import Redis

from services.pricing.cache import get_configs_cached, get_tariff_cached
from services.pricing.utils import fetch_station, fetch_user_profile
from services.pricing.v1.deps import get_redis
from services.shared.model import UserProfile

router = APIRouter(tags=["pricing"])


class OfferQuoteRq(BaseModel):
    """
    Запрос на расчёт оффера.
    Сюда приходит rental-api.
    """

    user_id: str
    station_id: str
    tariff_id: str


class OfferPricingRs(BaseModel):
    """
    Ответ от pricing-сервиса при расчёте оффера
    """

    user_id: str
    station_id: str
    tariff_id: str
    country: str
    currency: str
    price_per_hour: int
    free_period_min: int
    deposit: int
    pricing_mode: Literal["normal", "fallback_greedy"] | str
    created_at: datetime
    expires_at: datetime


@router.post(
    "/offer-quote",
    response_model=OfferPricingRs,
    summary="Рассчитать параметры оффера",
)
async def get_offer_quote(
    r: OfferQuoteRq, rds: Redis = Depends(get_redis)
) -> OfferPricingRs:
    config = await get_configs_cached(rds)
    station = await fetch_station(r.station_id)

    tariff_id = r.tariff_id or station.tariff_id
    tariff = await get_tariff_cached(
        rds, tariff_id=tariff_id, ttl_sec=config.tariff_cache_ttl_sec
    )

    pricing_mode = "normal"
    user_profile: UserProfile | None = None
    try:
        user_profile = await fetch_user_profile(r.user_id)
    except httpx.HTTPError:
        pricing_mode = "fallback_greedy"

    actual_price_per_hour = int(tariff.price_per_hour)
    actual_free_period_min = int(tariff.free_period_min)
    deposit = int(tariff.default_deposit)

    if user_profile:
        if user_profile.has_subscribtion:
            actual_free_period_min = max(actual_free_period_min, 30)
        if user_profile.trusted:
            deposit = 0
    else:  # фоллбэк: greedy pricing
        actual_price_per_hour = int(
            actual_price_per_hour * config.fallback_greedy_coeff
        )

    # Коэффициент на "последние банки"
    available_powerbanks = 2  # count_available_powerbanks(station)
    if available_powerbanks <= 2:
        actual_price_per_hour = int(
            actual_price_per_hour * config.price_coeff_settings["last_banks_increase"]
        )

    now = datetime.utcnow()
    expires_at = now + timedelta(seconds=config.offer_ttl_sec)

    return OfferPricingRs(
        user_id=r.user_id,
        station_id=r.station_id,
        tariff_id=tariff.id,
        country=station.country,
        currency=tariff.currency,
        price_per_hour=actual_price_per_hour,
        free_period_min=actual_free_period_min,
        deposit=deposit,
        pricing_mode=pricing_mode,
        created_at=now,
        expires_at=expires_at,
    )


class CalcAccruedRq(BaseModel):
    price_per_hour: int
    free_period_min: int
    started_at: datetime
    ended_at: datetime | None = None


class CalcAccruedRs(BaseModel):
    accrued_amount: int = Field(..., ge=0)


@router.post(
    "/calc-accrued",
    response_model=CalcAccruedRs,
    summary="Посчитать накопленную стоимость аренды",
)
async def calc_accrued(r: CalcAccruedRq):
    end_time = r.ended_at or datetime.utcnow()
    if end_time <= r.started_at:
        return CalcAccruedRs(accrued_amount=0)

    total_seconds = (end_time - r.started_at).total_seconds()
    if total_seconds <= r.free_period_min * 60:
        return CalcAccruedRs(accrued_amount=0)

    hours = int(total_seconds // 3600)
    amount = hours * int(r.price_per_hour)
    return CalcAccruedRs(accrued_amount=amount)
