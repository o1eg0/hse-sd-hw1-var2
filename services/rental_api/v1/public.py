import hashlib
import json
from datetime import datetime
import logging
from typing import Literal
from uuid import uuid4

import httpx
from fastapi import APIRouter, Depends, HTTPException
from fastapi.params import Header
from httpx import AsyncClient
from pydantic import BaseModel
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from services.pricing.utils import fetch_user_profile
from services.rental_api.code import ErrorCode
from services.rental_api.v1.deps import get_idempotency_key, get_db_session
from services.shared.db_models import (
    IdempotencyKeyDB,
    IdempotencyKeyScope,
    OfferDB,
    OfferStatus,
    PaymentDB,
    PaymentKind,
    PaymentStatus,
    PricingMode,
    RentalDB,
    RentalStatus,
)
from services.shared.model import Tariff
from services.shared.settings import rental_api_settings

router = APIRouter(tags=["rental_api"])


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
    created_at: datetime
    expires_at: datetime


class CreateRentalRq(BaseModel):
    offer_id: str


class RentalRs(BaseModel):
    rental_id: str


class RentalStatusRs(BaseModel):
    rental_id: str
    offer_id: str
    user_id: str
    start_station_id: str
    finish_station_id: str | None
    country: str
    currency: str
    price_per_hour: int
    free_period_min: int
    deposit: int
    total_amount: int
    powerbank_id: str | None
    start_time: datetime
    finish_time: datetime | None
    status: str
    created_at: datetime
    updated_at: datetime


@router.post("/offers", response_model=OfferRs, description="Создать оффер")
async def create_offer(
    r: CreateOfferRq,
    sess: AsyncSession = Depends(get_db_session),
):
    try:
        await fetch_user_profile(r.user_id)
    except httpx.HTTPError:
        raise HTTPException(502, "User service unavailable")

    async with AsyncClient() as client:
        resp = await client.post(
            f"{rental_api_settings.pricing_url}/v1/offer-quote",
            json={
                "user_id": r.user_id,
                "station_id": r.station_id,
                "tariff_id": r.tariff_id,
            },
        )

    if resp.status_code != 200:
        raise HTTPException(502, "Pricing service unavailable")

    payload = resp.json()

    offer_id = str(uuid4())

    pricing_mode = PricingMode(payload.get("pricing_mode", "normal"))
    created_at_raw = payload["created_at"]
    expires_at_raw = payload["expires_at"]

    if isinstance(created_at_raw, str) and created_at_raw.endswith("Z"):
        created_at_raw = created_at_raw.replace("Z", "+00:00")
    if isinstance(expires_at_raw, str) and expires_at_raw.endswith("Z"):
        expires_at_raw = expires_at_raw.replace("Z", "+00:00")

    created_at = (
        datetime.fromisoformat(created_at_raw)
        if isinstance(created_at_raw, str)
        else created_at_raw
    )
    expires_at = (
        datetime.fromisoformat(expires_at_raw)
        if isinstance(expires_at_raw, str)
        else expires_at_raw
    )

    offer = OfferDB(
        id=offer_id,
        user_id=payload["user_id"],
        station_id=payload["station_id"],
        tariff_id=payload["tariff_id"],
        country=payload["country"],
        currency=payload["currency"],
        price_per_hour=payload["price_per_hour"],
        free_period_min=payload["free_period_min"],
        deposit=payload["deposit"],
        pricing_mode=pricing_mode,
        expires_at=expires_at,
        created_at=created_at,
        updated_at=created_at,
    )
    sess.add(offer)

    tariff_snapshot = Tariff(
        id=offer.tariff_id,
        price_per_hour=offer.price_per_hour,
        free_period_min=offer.free_period_min,
        default_deposit=offer.deposit,
        currency=offer.currency,
    )

    return OfferRs(
        offer_id=offer.id,
        user_id=offer.user_id,
        station_id=offer.station_id,
        country=offer.country,
        tariff_snapshot=tariff_snapshot,
        pricing_mode=offer.pricing_mode.value,
        created_at=created_at,
        expires_at=expires_at,
    )


def _compute_request_hash(data: dict) -> str:
    """Compute SHA256 hash of request data for idempotency checking."""
    json_str = json.dumps(data, sort_keys=True)
    return hashlib.sha256(json_str.encode()).hexdigest()


async def _check_idempotency(
    sess: AsyncSession,
    key: str,
    scope: IdempotencyKeyScope,
    request_data: dict,
) -> dict | None:
    """Check if idempotency key exists. Returns cached response if same request, raises 409 if different."""
    request_hash = _compute_request_hash(request_data)
    
    existing = await sess.get(IdempotencyKeyDB, key)
    
    if existing:
        if existing.scope != scope:
            raise HTTPException(
                409,
                detail={
                    "error_code": ErrorCode.IDEMPOTENCY_CONFLICT,
                    "message": "Idempotency key already used with different scope",
                },
            )
        if existing.request_hash != request_hash:
            raise HTTPException(
                409,
                detail={
                    "error_code": ErrorCode.IDEMPOTENCY_CONFLICT,
                    "message": "Idempotency key already used with different parameters",
                },
            )
        return json.loads(existing.response_body)
    
    return None


async def _store_idempotency(
    sess: AsyncSession,
    key: str,
    scope: IdempotencyKeyScope,
    request_data: dict,
    response_data: dict,
):
    """Store idempotency key with request hash and response."""
    request_hash = _compute_request_hash(request_data)
    response_body = json.dumps(response_data)
    
    idempotency_record = IdempotencyKeyDB(
        key=key,
        scope=scope,
        request_hash=request_hash,
        response_body=response_body,
    )
    sess.add(idempotency_record)


@router.post("/rentals", response_model=RentalRs, description="Старт аренды (выдача банки)")
async def rentals_start(
    r: CreateRentalRq,
    sess: AsyncSession = Depends(get_db_session),
    key: str = Depends(get_idempotency_key),
):
    request_data = {"offer_id": r.offer_id}
    cached_response = await _check_idempotency(
        sess, key, IdempotencyKeyScope.RENTAL_START, request_data
    )
    if cached_response:
        return RentalRs(**cached_response)
    
    offer = await sess.get(OfferDB, r.offer_id)
    if not offer:
        raise HTTPException(404, "Offer not found")
    
    if offer.status != OfferStatus.ACTIVE:
        raise HTTPException(400, f"Offer is not active (status: {offer.status.value})")
    
    if datetime.now() > offer.expires_at:
        raise HTTPException(400, "Offer has expired")
    
    rental_id = str(uuid4())
    start_time = datetime.now()
    
    rental = RentalDB(
        id=rental_id,
        offer_id=offer.id,
        user_id=offer.user_id,
        start_station_id=offer.station_id,
        finish_station_id=None,
        country=offer.country,
        currency=offer.currency,
        price_per_hour=offer.price_per_hour,
        free_period_min=offer.free_period_min,
        deposit=offer.deposit,
        total_amount=0,
        powerbank_id=None,
        start_time=start_time,
        finish_time=None,
        status=RentalStatus.CREATED,
    )
    sess.add(rental)
    await sess.flush() # Need to ensure that payment is committed
    
    async with AsyncClient() as client:
        try:
            eject_resp = await client.get(
                f"{rental_api_settings.stubs_url}/eject-powerbank",
                params={"station_id": offer.station_id},
            )
            if eject_resp.status_code != 200:
                raise HTTPException(502, "Station service unavailable")
            
            eject_data = eject_resp.json()
            if not eject_data.get("success"):
                raise HTTPException(400, "No powerbank available at station")
            
            rental.powerbank_id = eject_data["powerbank_id"]
            rental.status = RentalStatus.ACTIVE
        except httpx.HTTPError:
            raise HTTPException(502, "Station service unavailable")
    
    payment_id = str(uuid4())
    payment = PaymentDB(
        id=payment_id,
        order_id=rental_id,
        kind=PaymentKind.AUTHORIZE,
        amount=offer.deposit,
        currency=offer.currency,
        status=PaymentStatus.PENDING,
    )
    sess.add(payment)
    
    async with AsyncClient() as client:
        try:
            hold_resp = await client.post(
                f"{rental_api_settings.stubs_url}/hold-money-for-order",
                json={
                    "user_id": offer.user_id,
                    "order_id": rental_id,
                    "amount": offer.deposit,
                },
            )
            if hold_resp.status_code != 200:
                raise HTTPException(502, "Payment service unavailable")
            
            payment.status = PaymentStatus.SUCCEEDED
        except httpx.HTTPError:
            raise HTTPException(502, "Payment service unavailable")
    
    offer.status = OfferStatus.USED
    offer.updated_at = datetime.now()
    
    response_data = {"rental_id": rental_id}
    await _store_idempotency(
        sess, key, IdempotencyKeyScope.RENTAL_START, request_data, response_data
    )
    
    return RentalRs(rental_id=rental_id)


@router.post(
    "/rentals/{rental_id}/return", description="Возврат банки (завершение аренды)"
)
async def rentals_return(
    rental_id: str,
    sess: AsyncSession = Depends(get_db_session),
    key: str = Depends(get_idempotency_key),
):
    request_data = {"offer_id": rental_id}
    cached_response = await _check_idempotency(
        sess, key, IdempotencyKeyScope.RENTAL_RETURN, request_data
    )
    if cached_response:
        return RentalRs(**cached_response)

    rental = await sess.get(RentalDB, rental_id)
    if not rental:
        raise HTTPException(404, "Rental not found")
    
    if rental.status not in (RentalStatus.CREATED, RentalStatus.ACTIVE):
        raise HTTPException(400, f"Rental cannot be returned (status: {rental.status.value})")
    
    finish_time = datetime.now()
    
    async with AsyncClient() as client:
        try:
            calc_resp = await client.post(
                f"{rental_api_settings.pricing_url}/v1/calc-accrued",
                json={
                    "price_per_hour": rental.price_per_hour,
                    "free_period_min": rental.free_period_min,
                    "started_at": rental.start_time.isoformat(),
                    "ended_at": finish_time.isoformat(),
                },
            )
            if calc_resp.status_code != 200:
                raise HTTPException(502, "Pricing service unavailable")
            
            accrued_amount = calc_resp.json()["accrued_amount"]
        except httpx.HTTPError:
            raise HTTPException(502, "Pricing service unavailable")
    
    rental.finish_time = finish_time
    rental.total_amount = accrued_amount
    rental.updated_at = finish_time
    
    stmt = select(PaymentDB).where(
        PaymentDB.order_id == rental_id,
        PaymentDB.kind == PaymentKind.AUTHORIZE,
    )
    result = await sess.exec(stmt)
    payment = result.first()
    
    if payment:
        final_amount = accrued_amount
        
        if final_amount <= rental.deposit:
            refund_amount = rental.deposit - final_amount
            if refund_amount > 0:
                refund_payment = PaymentDB(
                    id=str(uuid4()),
                    order_id=rental_id,
                    kind=PaymentKind.REFUND,
                    amount=refund_amount,
                    currency=rental.currency,
                    status=PaymentStatus.PENDING,
                )
                sess.add(refund_payment)
        else:
            capture_payment = PaymentDB(
                id=str(uuid4()),
                order_id=rental_id,
                kind=PaymentKind.CAPTURE,
                amount=final_amount - rental.deposit,
                currency=rental.currency,
                status=PaymentStatus.PENDING,
            )
            sess.add(capture_payment)
    
    async with AsyncClient() as client:
        try:
            clear_resp = await client.post(
                f"{rental_api_settings.stubs_url}/clear-money-for-order",
                json={
                    "user_id": rental.user_id,
                    "order_id": rental_id,
                    "amount": accrued_amount,
                },
            )
            if clear_resp.status_code != 200:
                raise HTTPException(502, "Payment service unavailable")
            
            # Update payment statuses
            if payment:
                payment.status = PaymentStatus.SUCCEEDED
                payment.updated_at = finish_time
        except httpx.HTTPError:
            raise HTTPException(502, "Payment service unavailable")
    
    rental.status = RentalStatus.CLOSED
    rental.updated_at = finish_time
    
    response_data = {"rental_id": rental_id}
    await _store_idempotency(
        sess, key, IdempotencyKeyScope.RENTAL_RETURN, request_data=request_data, response_data=response_data
    )

    return response_data


@router.get("/rentals/{rental_id}", response_model=RentalStatusRs)
async def rentals_status(
    rental_id: str,
    sess: AsyncSession = Depends(get_db_session),
):
    rental = await sess.get(RentalDB, rental_id)
    if not rental:
        raise HTTPException(404, "Rental not found")
    
    return RentalStatusRs(
        rental_id=rental.id,
        offer_id=rental.offer_id,
        user_id=rental.user_id,
        start_station_id=rental.start_station_id,
        finish_station_id=rental.finish_station_id,
        country=rental.country,
        currency=rental.currency,
        price_per_hour=rental.price_per_hour,
        free_period_min=rental.free_period_min,
        deposit=rental.deposit,
        total_amount=rental.total_amount,
        powerbank_id=rental.powerbank_id,
        start_time=rental.start_time,
        finish_time=rental.finish_time,
        status=rental.status.value,
        created_at=rental.created_at,
        updated_at=rental.updated_at,
    )


@router.get("/rentals", description="Список аренд (для пользователя/админки)")
async def rentals_get():
    return {}
