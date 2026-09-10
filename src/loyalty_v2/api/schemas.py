from datetime import date
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
