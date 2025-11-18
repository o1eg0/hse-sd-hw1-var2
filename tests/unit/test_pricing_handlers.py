from datetime import datetime, timedelta

import httpx
import pytest

from services.pricing.v1 import public
from services.shared.model import Config, Slot, StationData, Tariff, UserProfile


class DummyRedis:
    """Minimal Redis stub for handler signature compatibility."""


def make_config(
    *,
    last_banks_increase: float = 1.5,
    tariff_cache_ttl_sec: int = 600,
    offer_ttl_sec: int = 300,
    fallback_greedy_coeff: float = 1.2,
) -> Config:
    return Config(
        price_coeff_settings={"last_banks_increase": last_banks_increase},
        tariff_cache_ttl_sec=tariff_cache_ttl_sec,
        offer_ttl_sec=offer_ttl_sec,
        fallback_greedy_coeff=fallback_greedy_coeff,
    )


def make_station(tariff_id: str = "tariff-1", country: str = "RU") -> StationData:
    return StationData(
        id="station-1",
        tariff_id=tariff_id,
        location="loc",
        country=country,
        slots=[Slot(index=1, empty=False, charge=80)],
    )


def make_tariff(
    *, tariff_id: str = "tariff-1", price_per_hour: int = 100, free_period_min: int = 5
) -> Tariff:
    return Tariff(
        id=tariff_id,
        price_per_hour=price_per_hour,
        free_period_min=free_period_min,
        default_deposit=300,
        currency="RUB",
    )


@pytest.mark.asyncio
async def test_get_offer_quote_with_user_profile(monkeypatch):
    cfg = make_config(offer_ttl_sec=120)
    station = make_station()
    tariff = make_tariff(price_per_hour=80, free_period_min=10)

    async def fake_get_configs_cached(_):
        return cfg

    async def fake_get_tariff_cached(_, tariff_id, ttl_sec):
        assert tariff_id == tariff.id
        assert ttl_sec == cfg.tariff_cache_ttl_sec
        return tariff

    async def fake_fetch_station(station_id: str):
        assert station_id == station.id
        return station

    async def fake_fetch_user_profile(user_id: str):
        assert user_id == "user-1"
        return UserProfile(id=user_id, has_subscribtion=True, trusted=True)

    monkeypatch.setattr(public, "get_configs_cached", fake_get_configs_cached)
    monkeypatch.setattr(public, "get_tariff_cached", fake_get_tariff_cached)
    monkeypatch.setattr(public, "fetch_station", fake_fetch_station)
    monkeypatch.setattr(public, "fetch_user_profile", fake_fetch_user_profile)

    request = public.OfferQuoteRq(
        user_id="user-1", station_id=station.id, tariff_id=tariff.id
    )
    response = await public.get_offer_quote(request, rds=DummyRedis())

    last_banks_increase = cfg.price_coeff_settings["last_banks_increase"]
    assert response.user_id == request.user_id
    assert response.station_id == request.station_id
    assert response.tariff_id == tariff.id
    assert response.deposit == 0  # trusted user
    assert response.free_period_min == 30  # extended for subscribers
    assert response.price_per_hour == 80 * last_banks_increase
    assert response.pricing_mode == "normal"
    assert response.currency == tariff.currency
    assert response.country == station.country
    assert response.expires_at - response.created_at == timedelta(
        seconds=cfg.offer_ttl_sec
    )


@pytest.mark.asyncio
async def test_get_offer_quote_when_profile_unavailable(monkeypatch):
    cfg = make_config(offer_ttl_sec=60, fallback_greedy_coeff=2.0)
    station = make_station(tariff_id="tariff-station")
    tariff = make_tariff(tariff_id="tariff-station", price_per_hour=50, free_period_min=3)

    async def fake_get_configs_cached(_):
        return cfg

    async def fake_get_tariff_cached(*_, **__):
        return tariff

    async def fake_fetch_station(*_):
        return station

    async def fake_fetch_user_profile(*_):
        raise httpx.HTTPError("boom")

    monkeypatch.setattr(public, "get_configs_cached", fake_get_configs_cached)
    monkeypatch.setattr(public, "get_tariff_cached", fake_get_tariff_cached)
    monkeypatch.setattr(public, "fetch_station", fake_fetch_station)
    monkeypatch.setattr(public, "fetch_user_profile", fake_fetch_user_profile)

    request = public.OfferQuoteRq(
        user_id="user-1", station_id=station.id, tariff_id=""
    )
    response = await public.get_offer_quote(request, rds=DummyRedis())

    last_banks_increase = cfg.price_coeff_settings["last_banks_increase"]
    assert response.price_per_hour == int(50 * cfg.fallback_greedy_coeff * last_banks_increase)
    assert response.pricing_mode == "fallback_greedy"
    assert response.tariff_id == tariff.id
    assert response.free_period_min == tariff.free_period_min
    assert response.deposit == tariff.default_deposit


@pytest.mark.asyncio
async def test_calc_accrued_handles_edge_cases():
    start = datetime(2025, 1, 1, 10, 0, 0)
    before_start = datetime(2025, 1, 1, 9, 0, 0)
    within_free = datetime(2025, 1, 1, 10, 10, 0)
    after_hours = datetime(2025, 1, 1, 12, 30, 0)

    zero_req = public.CalcAccruedRq(
        price_per_hour=100,
        free_period_min=15,
        started_at=start,
        ended_at=before_start,
    )
    zero_resp = await public.calc_accrued(zero_req)
    assert zero_resp.accrued_amount == 0

    free_req = public.CalcAccruedRq(
        price_per_hour=100,
        free_period_min=15,
        started_at=start,
        ended_at=within_free,
    )
    free_resp = await public.calc_accrued(free_req)
    assert free_resp.accrued_amount == 0

    paid_req = public.CalcAccruedRq(
        price_per_hour=120,
        free_period_min=15,
        started_at=start,
        ended_at=after_hours,
    )
    paid_resp = await public.calc_accrued(paid_req)
    assert paid_resp.accrued_amount == 120 * 2

