from datetime import datetime
from typing import Literal

import httpx
from fastapi import APIRouter, HTTPException
from fastapi.params import Header
from pydantic import BaseModel

from model import Tariff, StationData
from services.rental.code import ErrorCode

router = APIRouter()


class CreateOfferRq(BaseModel):
    user_id: str
    station_id: str
    tariff_id: str


class OfferRs(BaseModel):
    offer_id: str
    user_id: str
    station_id: str
    country: str
    tariff_snapshot: Tariff
    pricing_mode: Literal["normal","fallback_greedy"]
    created_at: datetime = "2025-10-29T12:34:57Z"
    expires_at: datetime = "2025-10-29T12:39:57Z"


@router.post("/offers", response_model=OfferRs, description="Создать оффер")
async def create_offer(r: CreateOfferRq):
    pricing_mode = "fallback_greedy"

    try:
        ue = "http://stubs:3629/user-profile"
        user = httpx.get(f"{ue}?id={r.user_id}").json()
        pricing_mode = "normal"
    except Exception:
        pass

    te = "http://stubs:3629/tariff"
    tariff = httpx.get(f"{te}?id={r.tariff_id}").json()

    sde = "http://stubs:3629/station-data"
    station_data = StationData(**httpx.get(f"{sde}?id={r.station_id}").json())

    if not station_data.slots:
        raise HTTPException(409, ErrorCode.STATION_EMPTY)

    return OfferRs(
        offer_id="off_789",
        user_id=r.user_id,
        station_id=r.station_id,
        country=station_data.country,
        tariff_snapshot=tariff,
        pricing_mode=pricing_mode,
    )


@router.post("/rentals", description="Старт аренды (выдача банки)")
async def rentals_start(key: str = Header(alias="Idempotency-Key")):
    return {"key": key}


@router.post(
    "/rentals/{rental_id}/return", description="Возврат банки (завершение аренды)"
)
async def rentals_return(rental_id: int):
    # TODO clear-money-for-order
    return {"rental_id": rental_id}


@router.get("/rentals/{rental_id}")
async def rentals_status(rental_id: int):
    return {"rental_id": rental_id}


@router.get("/rentals", description="Список аренд (для пользователя/админки)")
async def rentals_get():
    return {}
