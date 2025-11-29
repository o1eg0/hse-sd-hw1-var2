import uvicorn
from fastapi import Depends, FastAPI, HTTPException, Query
from pydantic import BaseModel
from starlette.responses import RedirectResponse

from prometheus_fastapi_instrumentator import Instrumentator, metrics

from services.shared.model import EjectResponse, Slot, StationData, Tariff, UserProfile

app = FastAPI()


instrumentator = Instrumentator().instrument(app).expose(app)
instrumentator.add(metrics.requests())
instrumentator.add(metrics.latency())


def get_country_currency(id: str):
    if id.startswith("de-"):
        return "DE", "EUR"
    return "RU", "RUB"


async def get_id(
    id: str | None = Query(None, description="An optional ID parameter"),
) -> str:
    if id is None:
        raise HTTPException(400, "ID parameter is required and cannot be empty.")
    return id


@app.get("/station-data", response_model=StationData)
async def get_station_data(id: str = Depends(get_id)):
    country, _ = get_country_currency(id)

    slots = [] if id == "empty-station-id" else [Slot(1, True, 0), Slot(2, False, 100)]
    return StationData(
        id=id,
        tariff_id="tariff18",
        location="Королев, универмаг Детский мир",
        slots=slots,
        country=country,
    )


@app.get("/tariff", response_model=Tariff)
async def get_tariff(id: str = Depends(get_id)):
    _, currency = get_country_currency(id)

    return Tariff(
        id=id,
        price_per_hour=50,
        free_period_min=5,
        default_deposit=300,
        currency=currency,
    )


@app.get("/user-profile", response_model=UserProfile)
async def get_user_profile(id: str = Depends(get_id)):
    return UserProfile(id=id, has_subscribtion=False, trusted=False)


@app.get("/configs")
async def get_configs():
    return {
        "price_coeff_settings": {"last_banks_increase": 1.5},
        "tariff_cache_ttl_sec": 600,
    }


@app.get("/eject-powerbank", response_model=EjectResponse)
async def eject_powerbank(station_id: str = Query(description="Station ID parameter")):
    if station_id == "empty-station-id":
        return EjectResponse(success=False, powerbank_id="")

    return EjectResponse(success=True, powerbank_id="powerbank_638")


class MoneyRequest(BaseModel):
    user_id: str
    order_id: str
    amount: int


@app.post("/hold-money-for-order")
async def hold_money_for_order(request: MoneyRequest):
    if request.user_id is None:
        raise HTTPException(400, "user_id parameter is required and cannot be empty.")
    return {"status": "success"}


@app.post("/clear-money-for-order")
async def clear_money_for_order(request: MoneyRequest):
    if request.user_id is None:
        raise HTTPException(400, "user_id parameter is required and cannot be empty.")
    return {"status": "success"}


@app.get("/", include_in_schema=False)
async def root():
    return RedirectResponse(url="/docs")


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=3629, log_level="info")
