import pytest
from fastapi import HTTPException

from services.rental_api.v1 import public


@pytest.mark.asyncio
async def test_create_offer_not_implemented():
    #TODO
    request = public.CreateOfferRq(user_id="u1", station_id="s1", tariff_id="t1")
    with pytest.raises(HTTPException) as exc:
        await public.create_offer(request)
    assert exc.value.status_code == 501
    assert "Not implemented" in exc.value.detail


@pytest.mark.asyncio
async def test_rentals_start_returns_idempotency_key():
    #TODO
    response = await public.rentals_start(key="abc-123")
    assert response == {"key": "abc-123"}


@pytest.mark.asyncio
async def test_rentals_return_echoes_rental_id():
    #TODO
    response = await public.rentals_return(rental_id=42)
    assert response == {"rental_id": 42}


@pytest.mark.asyncio
async def test_rentals_status_returns_payload():
    #TODO
    response = await public.rentals_status(rental_id=99)
    assert response == {"rental_id": 99}


@pytest.mark.asyncio
async def test_rentals_get_returns_empty_payload():
    #TODO
    assert await public.rentals_get() == {}

