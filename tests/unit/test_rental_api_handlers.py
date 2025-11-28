import pytest
from datetime import datetime, timedelta

from services.rental_api.v1 import public
from services.shared.db_models import (
    IdempotencyKeyDB,
    OfferDB,
    OfferStatus,
    PaymentDB,
    PaymentKind,
    PaymentStatus,
    PricingMode,
    RentalDB,
    RentalStatus,
)


class DummySession:
    def __init__(self, storage=None, exec_result=None):
        self.storage: dict[type, dict[str, object]] = storage or {}
        self.added: list[object] = []
        self.exec_result = exec_result

    async def get(self, model, key):
        bucket = self.storage.setdefault(model, {})
        return bucket.get(key)

    def add(self, obj):
        self.added.append(obj)
        key = getattr(obj, "id", None) or getattr(obj, "key", None)
        if key is not None:
            bucket = self.storage.setdefault(type(obj), {})
            bucket[key] = obj

    async def exec(self, _):
        class DummyResult:
            def __init__(self, value):
                self._value = value

            def first(self):
                return self._value

        return DummyResult(self.exec_result)
<<<<<<< HEAD
    
    async def flush(self):
        pass
=======
>>>>>>> 69f3ba3 (rental_api handlers and tests (#6))


class DummyResponse:
    def __init__(self, status_code: int, payload: dict):
        self.status_code = status_code
        self._payload = payload

    def json(self):
        return self._payload


class DummyAsyncClient:
    def __init__(self, responses: dict[tuple[str, str], DummyResponse], calls):
        self._responses = responses
        self._calls = calls

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def get(self, url: str, params: dict | None = None):
        self._calls.append(("GET", url, params))
        return self._responses[("GET", url)]

    async def post(self, url: str, json: dict | None = None):
        self._calls.append(("POST", url, json))
        return self._responses[("POST", url)]


@pytest.mark.asyncio
async def test_create_offer_happy_path(monkeypatch):
    sess = DummySession()

    async def fake_fetch_user_profile(user_id: str):
        assert user_id == "u1"
        return object()

    pricing_payload = {
        "user_id": "u1",
        "station_id": "s1",
        "tariff_id": "t1",
        "country": "RU",
        "currency": "RUB",
        "price_per_hour": 100,
        "free_period_min": 15,
        "deposit": 300,
        "pricing_mode": "normal",
        "created_at": "2025-10-29T12:34:57Z",
        "expires_at": "2025-10-29T12:39:57Z",
    }
    calls: list[tuple[str, dict]] = []
    dummy_responses: dict[tuple[str, str], DummyResponse] = {
        ("POST", "http://pricing:9000/v1/offer-quote"): DummyResponse(status_code=200, payload=pricing_payload)
    }

    monkeypatch.setattr(public, "fetch_user_profile", fake_fetch_user_profile)
    monkeypatch.setattr(
        public, "AsyncClient", lambda *args, **kwargs: DummyAsyncClient(dummy_responses, calls)
    )
    request = public.CreateOfferRq(user_id="u1", station_id="s1", tariff_id="t1")
    result = await public.create_offer(request, sess=sess)

    assert calls and calls[0][1].endswith("/v1/offer-quote")
    sent_json = calls[0][2]
    assert sent_json["user_id"] == "u1"
    assert sent_json["station_id"] == "s1"
    assert sent_json["tariff_id"] == "t1"

    assert len(sess.added) == 1
    offer_db = sess.added[0]
    assert isinstance(offer_db, OfferDB)
    assert offer_db.user_id == "u1"
    assert offer_db.station_id == "s1"
    assert offer_db.tariff_id == "t1"

    assert result.user_id == "u1"
    assert result.station_id == "s1"
    assert result.country == pricing_payload["country"]
    assert result.tariff_snapshot.price_per_hour == pricing_payload["price_per_hour"]
    assert result.tariff_snapshot.free_period_min == pricing_payload["free_period_min"]
    assert result.tariff_snapshot.default_deposit == pricing_payload["deposit"]
    assert result.pricing_mode == "normal"


@pytest.mark.asyncio
async def test_rentals_start_creates_rental_and_payment(monkeypatch):
    now = datetime.now()
    offer = OfferDB(
        id="offer-1",
        user_id="user-1",
        station_id="station-1",
        tariff_id="tariff-1",
        country="RU",
        currency="RUB",
        price_per_hour=150,
        free_period_min=10,
        deposit=500,
        pricing_mode=PricingMode.NORMAL,
        status=OfferStatus.ACTIVE,
        expires_at=now + timedelta(minutes=5),
        created_at=now,
        updated_at=now,
    )
    storage = {OfferDB: {"offer-1": offer}, IdempotencyKeyDB: {}}
    session = DummySession(storage=storage)

    calls = []
    responses = {
        ("GET", "http://stubs:3629/eject-powerbank"): DummyResponse(
            200, {"success": True, "powerbank_id": "pb-1"}
        ),
        ("POST", "http://stubs:3629/hold-money-for-order"): DummyResponse(
            200, {"status": "success"}
        ),
    }

    uuid_values = iter(["rent-123", "pay-456"])
    monkeypatch.setattr(public, "uuid4", lambda: next(uuid_values))
    monkeypatch.setattr(
        public, "AsyncClient", lambda *args, **kwargs: DummyAsyncClient(responses, calls)
    )

    req = public.CreateRentalRq(offer_id="offer-1")
    result = await public.rentals_start(
        req, sess=session, key="idem-1"
    )

    assert result.rental_id == "rent-123"
    rental = session.storage[RentalDB][result.rental_id]
    assert rental.powerbank_id == "pb-1"
    assert rental.status == RentalStatus.ACTIVE

    payment = session.storage[PaymentDB]["pay-456"]
    assert payment.kind == PaymentKind.AUTHORIZE
    assert payment.amount == 500
    assert payment.status == PaymentStatus.SUCCEEDED

    idem_record = session.storage[IdempotencyKeyDB]["idem-1"]
    assert idem_record.scope == public.IdempotencyKeyScope.RENTAL_START

    assert offer.status == OfferStatus.USED
    assert ("GET", "http://stubs:3629/eject-powerbank", {"station_id": "station-1"}) in calls
    assert (
        "POST",
        "http://stubs:3629/hold-money-for-order",
        {"user_id": "user-1", "order_id": "rent-123", "amount": 500},
    ) in calls


@pytest.mark.asyncio
async def test_rentals_return_completes_and_creates_refund(monkeypatch):
    start_time = datetime(2025, 1, 1, 10, 0, 0)
    rental = RentalDB(
        id="rent-1",
        offer_id="offer-1",
        user_id="user-1",
        start_station_id="station-1",
        finish_station_id=None,
        country="RU",
        currency="RUB",
        price_per_hour=150,
        free_period_min=10,
        deposit=500,
        total_amount=0,
        powerbank_id="pb-1",
        start_time=start_time,
        finish_time=None,
        status=RentalStatus.ACTIVE,
        created_at=start_time,
        updated_at=start_time,
    )
    payment = PaymentDB(
        id="pay-1",
        order_id="rent-1",
        kind=PaymentKind.AUTHORIZE,
        amount=500,
        currency="RUB",
        status=PaymentStatus.PENDING,
    )

    storage = {RentalDB: {"rent-1": rental}, IdempotencyKeyDB: {}}
    session = DummySession(storage=storage, exec_result=payment)

    calls = []
    responses = {
        ("POST", "http://pricing:9000/v1/calc-accrued"): DummyResponse(
            200, {"accrued_amount": 100}
        ),
        ("POST", "http://stubs:3629/clear-money-for-order"): DummyResponse(
            200, {"status": "success"}
        ),
    }

    uuid_values = iter(["refund-1"])
    monkeypatch.setattr(public, "uuid4", lambda: next(uuid_values))
    monkeypatch.setattr(
        public, "AsyncClient", lambda *args, **kwargs: DummyAsyncClient(responses, calls)
    )

    resp = await public.rentals_return(
        rental_id="rent-1", sess=session, key="idem-return"
    )

    assert resp == {"rental_id": "rent-1"}
    assert rental.status == RentalStatus.CLOSED
    assert rental.finish_time is not None
    assert rental.total_amount == 100

    assert payment.status == PaymentStatus.SUCCEEDED

    refund_payment = session.storage[PaymentDB]["refund-1"]
    assert refund_payment.kind == PaymentKind.REFUND
    assert refund_payment.amount == 400

    idem_record = session.storage[IdempotencyKeyDB]["idem-return"]
    assert idem_record.scope == public.IdempotencyKeyScope.RENTAL_RETURN

    assert (
        "POST",
        "http://pricing:9000/v1/calc-accrued",
        {
            "price_per_hour": 150,
            "free_period_min": 10,
            "started_at": rental.start_time.isoformat(),
            "ended_at": rental.finish_time.isoformat(),
        },
    ) in calls
    assert (
        "POST",
        "http://stubs:3629/clear-money-for-order",
        {"user_id": "user-1", "order_id": "rent-1", "amount": 100},
    ) in calls


@pytest.mark.asyncio
async def test_rentals_status_returns_full_snapshot():
    now = datetime(2025, 1, 1, 11, 0, 0)
    rental = RentalDB(
        id="rent-9",
        offer_id="offer-9",
        user_id="user-9",
        start_station_id="station-A",
        finish_station_id="station-B",
        country="RU",
        currency="RUB",
        price_per_hour=200,
        free_period_min=5,
        deposit=0,
        total_amount=300,
        powerbank_id="pb-9",
        start_time=now - timedelta(hours=2),
        finish_time=now - timedelta(hours=1),
        status=RentalStatus.CLOSED,
        created_at=now - timedelta(hours=3),
        updated_at=now - timedelta(minutes=30),
    )
    session = DummySession(storage={RentalDB: {"rent-9": rental}})

    resp = await public.rentals_status("rent-9", sess=session)

    assert resp.rental_id == "rent-9"
    assert resp.offer_id == "offer-9"
    assert resp.powerbank_id == "pb-9"
    assert resp.total_amount == 300
    assert resp.status == RentalStatus.CLOSED.value
