from datetime import datetime
from enum import Enum

from sqlmodel import Field, SQLModel


class OfferStatus(str, Enum):
    ACTIVE = "active"
    USED = "used"
    EXPIRED = "expired"
    CANCELLED = "cancelled"


class RentalStatus(str, Enum):
    CREATED = "created"
    ACTIVE = "active"
    RETURNED = "returned"
    CLOSED = "closed"


class PricingMode(str, Enum):
    NORMAL = "normal"
    FALLBACK_GREEDY = "fallback_greedy"


class OfferDB(SQLModel, table=True):
    __tablename__ = "offers"

    id: str = Field(primary_key=True, index=True)
    user_id: str = Field(index=True)
    station_id: str = Field(index=True)

    tariff_id: str
    country: str = Field(index=True, max_length=5)
    currency: str = Field(max_length=5)

    price_per_hour: int
    free_period_min: int
    deposit: int

    pricing_mode: PricingMode = Field(default=PricingMode.NORMAL)
    status: OfferStatus = Field(default=OfferStatus.ACTIVE)

    expires_at: datetime
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class RentalDB(SQLModel, table=True):
    __tablename__ = "rentals"

    id: str = Field(primary_key=True, index=True)
    offer_id: str = Field(foreign_key="offers.id", index=True)

    user_id: str = Field(index=True)
    start_station_id: str
    finish_station_id: str | None = None

    country: str = Field(index=True, max_length=2)
    currency: str = Field(max_length=3)

    price_per_hour: int
    free_period_min: int
    deposit: int

    total_amount: int = 0
    powerbank_id: str | None = Field(default=None, index=True)

    start_time: datetime
    finish_time: datetime | None = None

    status: RentalStatus = Field(default=RentalStatus.CREATED)

    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class PaymentKind(str, Enum):
    AUTHORIZE = "authorize"
    CAPTURE = "capture"
    REFUND = "refund"


class PaymentStatus(str, Enum):
    PENDING = "pending"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class PaymentDB(SQLModel, table=True):
    __tablename__ = "payments"

    id: str = Field(primary_key=True)
    order_id: str = Field(foreign_key="rentals.id", index=True)

    kind: PaymentKind
    amount: int
    currency: str = Field(max_length=3)
    status: PaymentStatus = Field(default=PaymentStatus.PENDING)
    provider_ref: str | None = None

    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class CountryRetentionConfigDB(SQLModel, table=True):
    """
    Настройка срока хранения заказов по странам.
    По умолчанию – 365 дней, но можно переопределить.
    """

    __tablename__ = "country_retention_config"

    country: str = Field(primary_key=True, max_length=2)
    retention_days: int = Field(default=365)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class IdempotencyKeyScope(str, Enum):
    OFFERS = "OFFERS"
    RENTAL_START = "RENTAL_START"
    RENTAL_RETURN = "RENTAL_RETURN"


class IdempotencyKeyDB(SQLModel, table=True):
    __tablename__ = "idempotency_keys"

    key: str = Field(primary_key=True)
    scope: IdempotencyKeyScope
    request_hash: str
    response_body: str

    created_at: datetime = Field(default_factory=datetime.utcnow)
