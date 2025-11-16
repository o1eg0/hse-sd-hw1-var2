from datetime import datetime
from typing import Literal

from fastapi import APIRouter, HTTPException
from fastapi.params import Header
from pydantic import BaseModel

from services.shared.model import Tariff

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
    pricing_mode: Literal["normal", "fallback_greedy"]
    created_at: datetime = "2025-10-29T12:34:57Z"
    expires_at: datetime = "2025-10-29T12:39:57Z"


@router.post("/offers", response_model=OfferRs, description="Создать оффер")
async def create_offer(r: CreateOfferRq):
    # TODO: call pricing service
    # TODO: persist OfferDB
    raise HTTPException(501, "Not implemented yet")


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
