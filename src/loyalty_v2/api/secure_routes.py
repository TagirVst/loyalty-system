from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from loyalty_v2.api.secure_schemas import (
    AdjustPointsRequest, CancelOwnOrderRequest, ConfirmOrderRequest, ConfirmRefundRequest,
    CreateDraftRequest, DraftResponse, IdentifyDraftRequest, OrderResponse, PointsEntryResponse,
    QuoteRequest, QuoteResponse, RefundPreviewRequest, RefundPreviewResponse, RefundResponse,
    StaffLoginRequest, StaffLogoutRequest, StaffSessionResponse,
)
from loyalty_v2.application.auth_service import Permission, StaffAuthService
from loyalty_v2.application.order_service import IdentificationService, OrderService
from loyalty_v2.application.principal import PrincipalService
from loyalty_v2.application.refund_service import RefundService
from loyalty_v2.application.services import DomainError, InsufficientPoints, PointsService
from loyalty_v2.db.models import LedgerEntryType
from loyalty_v2.db.order_models import Order
from loyalty_v2.db.session import get_session

router = APIRouter(prefix="/api/v2")
staff_auth = StaffAuthService()
principals = PrincipalService()
points = PointsService()
orders = OrderService()
identification = IdentificationService()
refunds = RefundService()


def domain_error(exc: DomainError) -> HTTPException:
    code = exc.code
    if code in {"INVALID_PIN", "PIN_LOCKED", "STAFF_SESSION_INVALID", "TERMINAL_NOT_AUTHORIZED"}:
        http_status = status.HTTP_401_UNAUTHORIZED
    elif code == "PERMISSION_DENIED":
        http_status = status.HTTP_403_FORBIDDEN
    elif isinstance(exc, InsufficientPoints):
        http_status = status.HTTP_409_CONFLICT
    else:
        http_status = status.HTTP_422_UNPROCESSABLE_ENTITY
    return HTTPException(http_status, detail={"code": code, "message": str(exc)})


@router.post("/staff/login", response_model=StaffSessionResponse)
async def login(body: StaffLoginRequest, session: AsyncSession = Depends(get_session)) -> StaffSessionResponse:
    try:
        async with session.begin():
            auth = await staff_auth.authenticate(session, organization_id=body.organization_id, terminal_id=body.terminal_id, pin=body.pin)
    except DomainError as exc:
        raise domain_error(exc) from exc
    return StaffSessionResponse(staff_session_id=auth.id, staff_id=auth.staff_id, terminal_id=auth.terminal_id, status=auth.status)


@router.post("/staff/logout", status_code=204)
async def logout(body: StaffLogoutRequest, session: AsyncSession = Depends(get_session)) -> None:
    try:
        async with session.begin():
            await staff_auth.logout(session, body.staff_session_id)
    except DomainError as exc:
        raise domain_error(exc) from exc


@router.post("/customers/{customer_id}/points/adjust", response_model=PointsEntryResponse)
async def adjust_points(customer_id: UUID, body: AdjustPointsRequest, session: AsyncSession = Depends(get_session)) -> PointsEntryResponse:
    try:
        async with session.begin():
            principal = await principals.staff(session, staff_session_id=body.staff_session_id)
            principal.require(Permission.POINTS_ADJUST)
            entry = await points.apply(session, organization_id=principal.organization_id, customer_id=customer_id, delta=body.delta, entry_type=LedgerEntryType.MANUAL, reason=body.reason, idempotency_key=body.idempotency_key)
    except DomainError as exc:
        raise domain_error(exc) from exc
    return PointsEntryResponse(entry_id=entry.id, customer_id=entry.customer_id, delta=entry.delta, balance_after=entry.balance_after, entry_type=entry.entry_type)


@router.post("/order-drafts", response_model=DraftResponse, status_code=201)
async def create_draft(body: CreateDraftRequest, session: AsyncSession = Depends(get_session)) -> DraftResponse:
    try:
        async with session.begin():
            principal = await principals.staff(session, staff_session_id=body.staff_session_id)
            principal.require(Permission.SALE_CREATE)
            draft = await orders.create_draft(session, organization_id=principal.organization_id, location_id=principal.location_id, gross_amount_minor=body.gross_amount_minor, requested_points=body.requested_points, currency_code=body.currency_code, selected_reward_ids=body.selected_reward_ids)
    except DomainError as exc:
        raise domain_error(exc) from exc
    return DraftResponse(draft_id=draft.id, version=draft.version, customer_id=draft.customer_id, gross_amount_minor=draft.gross_amount_minor, requested_points=draft.requested_points, selected_reward_ids=[UUID(x) for x in draft.selected_reward_ids])


@router.post("/order-drafts/{draft_id}/identify", response_model=DraftResponse)
async def identify(draft_id: UUID, body: IdentifyDraftRequest, session: AsyncSession = Depends(get_session)) -> DraftResponse:
    try:
        async with session.begin():
            principal = await principals.staff(session, staff_session_id=body.staff_session_id)
            principal.require(Permission.SALE_CREATE)
            draft = await identification.attach_to_draft(session, organization_id=principal.organization_id, draft_id=draft_id, code=body.code)
            if draft.location_id != principal.location_id:
                raise HTTPException(403, detail={"code": "LOCATION_MISMATCH"})
    except DomainError as exc:
        raise domain_error(exc) from exc
    return DraftResponse(draft_id=draft.id, version=draft.version, customer_id=draft.customer_id, gross_amount_minor=draft.gross_amount_minor, requested_points=draft.requested_points, selected_reward_ids=[UUID(x) for x in draft.selected_reward_ids])


@router.post("/order-drafts/{draft_id}/quote", response_model=QuoteResponse)
async def quote(draft_id: UUID, body: QuoteRequest, session: AsyncSession = Depends(get_session)) -> QuoteResponse:
    try:
        async with session.begin():
            principal = await principals.staff(session, staff_session_id=body.staff_session_id)
            principal.require(Permission.SALE_CREATE)
            result = await orders.quote(session, organization_id=principal.organization_id, draft_id=draft_id)
    except DomainError as exc:
        raise domain_error(exc) from exc
    q = result.quote
    return QuoteResponse(quote_id=q.id, draft_id=q.draft_id, tier_id=q.tier_id, potential_tier_id=q.potential_tier_id, gross_amount_minor=q.gross_amount_minor, amount_after_rewards_minor=q.amount_after_rewards_minor, points_balance=result.points_balance, max_redeemable_points=q.max_redeemable_points, redeemed_points=q.redeemed_points, paid_amount_minor=q.paid_amount_minor, points_to_earn=q.points_to_earn, qualification_amount_minor=q.qualification_amount_minor)


@router.post("/order-drafts/{draft_id}/confirm", response_model=OrderResponse)
async def confirm(draft_id: UUID, body: ConfirmOrderRequest, session: AsyncSession = Depends(get_session)) -> OrderResponse:
    try:
        async with session.begin():
            principal = await principals.staff(session, staff_session_id=body.staff_session_id)
            principal.require(Permission.SALE_CONFIRM)
            order = await orders.confirm(session, organization_id=principal.organization_id, draft_id=draft_id, quote_id=body.quote_id, idempotency_key=body.idempotency_key, actor_staff_id=principal.staff_id)
            if order.location_id != principal.location_id:
                raise HTTPException(403, detail={"code": "LOCATION_MISMATCH"})
    except DomainError as exc:
        raise domain_error(exc) from exc
    return OrderResponse(order_id=order.id, customer_id=order.customer_id, gross_amount_minor=order.gross_amount_minor, redeemed_points=order.redeemed_points, paid_amount_minor=order.paid_amount_minor, points_earned=order.points_earned, tier_before_id=order.tier_before_id, tier_after_id=order.tier_after_id, status=order.status)


@router.post("/orders/{order_id}/refund-preview", response_model=RefundPreviewResponse)
async def refund_preview(order_id: UUID, body: RefundPreviewRequest, session: AsyncSession = Depends(get_session)) -> RefundPreviewResponse:
    try:
        async with session.begin():
            principal = await principals.staff(session, staff_session_id=body.staff_session_id)
            principal.require(Permission.ADMIN_ACCESS)
            preview = await refunds.preview(session, organization_id=principal.organization_id, order_id=order_id, gross_refund_minor=body.gross_refund_minor)
    except DomainError as exc:
        raise domain_error(exc) from exc
    return RefundPreviewResponse(**preview.__dict__)


@router.post("/orders/{order_id}/refund", response_model=RefundResponse)
async def refund(order_id: UUID, body: ConfirmRefundRequest, session: AsyncSession = Depends(get_session)) -> RefundResponse:
    try:
        async with session.begin():
            principal = await principals.staff(session, staff_session_id=body.staff_session_id)
            principal.require(Permission.ADMIN_ACCESS)
            item = await refunds.confirm(session, organization_id=principal.organization_id, order_id=order_id, actor_staff_id=principal.staff_id, reason=body.reason, idempotency_key=body.idempotency_key, gross_refund_minor=body.gross_refund_minor)
    except DomainError as exc:
        raise domain_error(exc) from exc
    return RefundResponse(refund_id=item.id, order_id=item.order_id, refund_type=item.refund_type, gross_refund_minor=item.gross_refund_minor, paid_refund_minor=item.paid_refund_minor, restored_points=item.restored_points, reversed_earned_points=item.reversed_earned_points)


@router.post("/orders/{order_id}/cancel-own", response_model=RefundResponse)
async def cancel_own(order_id: UUID, body: CancelOwnOrderRequest, session: AsyncSession = Depends(get_session)) -> RefundResponse:
    try:
        async with session.begin():
            principal = await principals.staff(session, staff_session_id=body.staff_session_id)
            principal.require(Permission.SALE_CANCEL_OWN)
            order = await session.get(Order, order_id)
            if order is None or order.organization_id != principal.organization_id or order.location_id != principal.location_id or order.actor_staff_id != principal.staff_id:
                raise HTTPException(403, detail={"code": "NOT_OWN_ORDER"})
            item = await refunds.confirm(session, organization_id=principal.organization_id, order_id=order_id, actor_staff_id=principal.staff_id, reason=body.reason, idempotency_key=body.idempotency_key, cashier_cancel=True)
    except DomainError as exc:
        raise domain_error(exc) from exc
    return RefundResponse(refund_id=item.id, order_id=item.order_id, refund_type=item.refund_type, gross_refund_minor=item.gross_refund_minor, paid_refund_minor=item.paid_refund_minor, restored_points=item.restored_points, reversed_earned_points=item.reversed_earned_points)
