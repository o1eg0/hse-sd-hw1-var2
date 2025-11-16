from fastapi import HTTPException
from httpx import AsyncClient

from services.shared.model import Slot, StationData, UserProfile
from services.shared.settings import pricing_settings


async def fetch_station(station_id: str) -> StationData:
    async with AsyncClient() as client:
        resp = await client.get(
            f"{pricing_settings.base_url}/station-data",
            params={"id": station_id},
            timeout=1.0,
        )
    try:
        resp.raise_for_status()
    except Exception:
        raise HTTPException(502, "Station service unavailable")

    raw = resp.json()
    slots = [Slot(**s) for s in raw.get("slots", [])]
    return StationData(
        id=raw["id"],
        tariff_id=raw["tariff_id"],
        location=raw["location"],
        slots=slots,
        country=raw.get("country", "RU"),
    )


async def fetch_user_profile(user_id: str) -> UserProfile:
    async with AsyncClient() as client:
        resp = await client.get(
            f"{pricing_settings.base_url}/user-profile",
            params={"id": user_id},
            timeout=1.0,
        )
        resp.raise_for_status()
    return UserProfile(**resp.json())
