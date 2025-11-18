from datetime import datetime, timedelta

import pytest
from fastapi import HTTPException

from services.rental_query import app
from services.shared.db_models import RentalDB, RentalStatus


class DummySession:
    def __init__(self, rental: RentalDB | None, exc: Exception | None = None):
        self._rental = rental
        self._exc = exc

    async def get(self, model, key):
        if self._exc:
            raise self._exc
        return self._rental


class DummyResponse:
    def __init__(self, status_code: int, payload: dict):
        self.status_code = status_code
        self._payload = payload

    def json(self):
        return self._payload


class DummyAsyncClient:
    def __init__(self, response: DummyResponse, calls: list[tuple[str, dict]]):
        self._response = response
        self._calls = calls

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def post(self, url: str, json: dict):
        self._calls.append((url, json))
        return self._response


def make_rental(**overrides) -> RentalDB:
    data = dict(
        id="rent-1",
        offer_id="offer-1",
        user_id="user-1",
        start_station_id="station-1",
        finish_station_id="station-1",
        country="RU",
        currency="RUB",
        price_per_hour=120,
        free_period_min=15,
        deposit=300,
        total_amount=240,
        powerbank_id=None,
        start_time=datetime(2025, 1, 1, 10, 0, 0),
        finish_time=datetime(2025, 1, 1, 12, 0, 0),
        status=RentalStatus.RETURNED,
    )
    data.update(overrides)
    return RentalDB(**data)


@pytest.mark.asyncio
async def test_rental_info_basic(monkeypatch):
    rental = make_rental()
    sess = DummySession(rental)
    result = await app.rental_info(rental_id=rental.id, sess=sess)
    assert result.order_id == rental.id
    assert result.accrued_amount == rental.total_amount
    assert result.ended_at == rental.finish_time


@pytest.mark.asyncio
async def test_rental_info_fetches_accrued_amount_for_active_rental(monkeypatch):
    rental = make_rental(
        finish_time=None,
        status=RentalStatus.ACTIVE,
        total_amount=0,
    )
    sess = DummySession(rental)
    calls: list[tuple[str, dict]] = []
    dummy_response = DummyResponse(status_code=200, payload={"accrued_amount": 555})
    monkeypatch.setattr(
        app, "AsyncClient", lambda *args, **kwargs: DummyAsyncClient(dummy_response, calls)
    )

    result = await app.rental_info(rental_id=rental.id, sess=sess)

    assert result.accrued_amount == 555
    assert result.ended_at is None
    assert calls and calls[0][0].endswith("/v1/calc-accrued")
    payload = calls[0][1]
    assert payload["price_per_hour"] == rental.price_per_hour
    assert payload["free_period_min"] == rental.free_period_min


@pytest.mark.asyncio
async def test_rental_info_raises_when_pricing_unavailable(monkeypatch):
    rental = make_rental(finish_time=None, status=RentalStatus.ACTIVE)
    sess = DummySession(rental)
    response = DummyResponse(status_code=500, payload={})
    monkeypatch.setattr(
        app, "AsyncClient", lambda *args, **kwargs: DummyAsyncClient(response, [])
    )

    with pytest.raises(HTTPException) as exc:
        await app.rental_info(rental_id=rental.id, sess=sess)
    assert exc.value.status_code == 502


@pytest.mark.asyncio
async def test_rental_info_handles_missing_rental():
    sess = DummySession(None)
    with pytest.raises(HTTPException) as exc:
        await app.rental_info(rental_id="missing", sess=sess)
    assert exc.value.status_code == 404
