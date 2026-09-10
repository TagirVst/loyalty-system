from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, Field


class RegisterCustomerRequest(BaseModel):
    organization_id: UUID
    telegram_id: int = Field(gt=0)
    first_name: str = Field(min_length=1, max_length=160)
    phone: str = Field(min_length=7, max_length=32)
    birth_date: date


class CustomerResponse(BaseModel):
    id: UUID
    first_name: str
    phone: str
    balance: int
    tier_id: UUID
    qualification_spend_minor: int


class AdjustPointsRequest(BaseModel):
    organization_id: UUID
    delta: int
    reason: str = Field(min_length=1, max_length=500)
    idempotency_key: str = Field(min_length=1, max_length=128)


class PointsEntryResponse(BaseModel):
    entry_id: UUID
    customer_id: UUID
    delta: int
    balance_after: int
    entry_type: str


class GenerateCodeRequest(BaseModel):
    organization_id: UUID
    customer_id: UUID


class IdentificationCodeResponse(BaseModel):
    identification_id: UUID
    code: str
    expires_at: datetime


class CreateDraftRequest(BaseModel):
    organization_id: UUID
    location_id: UUID
    gross_amount_minor: int = Field(gt=0)
    requested_points: int = Field(default=0, ge=0)
    currency_code: str = Field(default="RUB", min_length=3, max_length=3)


class DraftResponse(BaseModel):
    draft_id: UUID
    version: int
    customer_id: UUID | None
    gross_amount_minor: int
    requested_points: int


class IdentifyDraftRequest(BaseModel):
    organization_id: UUID
    code: str = Field(pattern=r"^\d{5}$")


class QuoteRequest(BaseModel):
    organization_id: UUID


class QuoteResponse(BaseModel):
    quote_id: UUID
    draft_id: UUID
    tier_id: UUID
    potential_tier_id: UUID
    gross_amount_minor: int
    amount_after_rewards_minor: int
    points_balance: int
    max_redeemable_points: int
    redeemed_points: int
    paid_amount_minor: int
    points_to_earn: int
    qualification_amount_minor: int
    expires_at: datetime


class ConfirmOrderRequest(BaseModel):
    organization_id: UUID
    quote_id: UUID
    idempotency_key: str = Field(min_length=1, max_length=128)


class OrderResponse(BaseModel):
    order_id: UUID
    customer_id: UUID
    gross_amount_minor: int
    redeemed_points: int
    paid_amount_minor: int
    points_earned: int
    tier_before_id: UUID
    tier_after_id: UUID
    status: str
