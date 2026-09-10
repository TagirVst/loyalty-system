from uuid import UUID

from pydantic import BaseModel, Field


class StaffScopedRequest(BaseModel):
    staff_session_id: UUID


class StaffLoginRequest(BaseModel):
    organization_id: UUID
    terminal_id: UUID
    pin: str = Field(pattern=r"^\d{6}$")


class StaffSessionResponse(BaseModel):
    staff_session_id: UUID
    staff_id: UUID
    terminal_id: UUID
    status: str


class StaffLogoutRequest(StaffScopedRequest):
    pass


class AdjustPointsRequest(StaffScopedRequest):
    delta: int
    reason: str = Field(min_length=1, max_length=500)
    idempotency_key: str = Field(min_length=1, max_length=128)


class PointsEntryResponse(BaseModel):
    entry_id: UUID
    customer_id: UUID
    delta: int
    balance_after: int
    entry_type: str


class CreateDraftRequest(StaffScopedRequest):
    gross_amount_minor: int = Field(gt=0)
    requested_points: int = Field(default=0, ge=0)
    selected_reward_ids: list[UUID] = Field(default_factory=list)
    currency_code: str = Field(default="RUB", min_length=3, max_length=3)


class DraftResponse(BaseModel):
    draft_id: UUID
    version: int
    customer_id: UUID | None
    gross_amount_minor: int
    requested_points: int
    selected_reward_ids: list[UUID]


class IdentifyDraftRequest(StaffScopedRequest):
    code: str = Field(pattern=r"^\d{5}$")


class QuoteRequest(StaffScopedRequest):
    pass


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


class ConfirmOrderRequest(StaffScopedRequest):
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


class RefundPreviewRequest(StaffScopedRequest):
    gross_refund_minor: int | None = Field(default=None, gt=0)


class RefundPreviewResponse(BaseModel):
    gross_refund_minor: int
    paid_refund_minor: int
    restored_points: int
    reversed_earned_points: int
    qualification_reversal_minor: int
    remaining_gross_minor: int


class ConfirmRefundRequest(RefundPreviewRequest):
    reason: str = Field(min_length=1, max_length=500)
    idempotency_key: str = Field(min_length=1, max_length=128)


class RefundResponse(BaseModel):
    refund_id: UUID
    order_id: UUID
    refund_type: str
    gross_refund_minor: int
    paid_refund_minor: int
    restored_points: int
    reversed_earned_points: int


class CancelOwnOrderRequest(StaffScopedRequest):
    reason: str = Field(min_length=1, max_length=500)
    idempotency_key: str = Field(min_length=1, max_length=128)
