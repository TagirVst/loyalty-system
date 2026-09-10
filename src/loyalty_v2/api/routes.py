from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from loyalty_v2.api.schemas import (
    AdjustPointsRequest,
    ConfirmOrderRequest,
    CreateDraftRequest,
    CustomerResponse,
    DraftResponse,
    GenerateCodeRequest,
    IdentificationCodeResponse,
    IdentifyDraftRequest,
    OrderResponse,
    PointsEntryResponse,
    QuoteRequest,
    QuoteResponse,
    RegisterCustomerRequest,
)
from loyalty_v2.application.order_service import IdentificationService, OrderService
from loyalty_v2.application.services import (
    CustomerAlreadyExists,
    CustomerNotFound,
    CustomerService,
    DomainError,
    InsufficientPoints,
    PointsService,
)
from loyalty_v2.db.models import LedgerEntryType
from loyalty_v2.db.session import get_session

router = APIRouter(prefix="/v2")
customers = CustomerService()
points = PointsService()
identification = IdentificationService()
orders = OrderService()


def _domain_http_error(exc: DomainError) -> HTTPException:
    code = exc.code
    if isinstance(exc, CustomerAlreadyExists):
        http_status = status.HTTP_409_CONFLICT
    elif isinstance(exc, CustomerNotFound):
        http_status = status.HTTP_404_NOT_FOUND
    elif isinstance(exc, InsufficientPoints):
        http_status = status.HTTP_409_CONFLICT
    else:
        http_status = status.HTTP_422_UNPROCESSABLE_ENTITY
    return HTTPException(status_code=http_status, detail={"code": code, "message": str(exc)})


@router.post("/customers", response_model=CustomerResponse, status_code=status.HTTP_201_CREATED)
async def register_customer(body: RegisterCustomerRequest, session: AsyncSession = Depends(get_session)) -> CustomerResponse:
    try:
        async with session.begin():
            result = await customers.register(
                session,
                organization_id=body.organization_id,
                telegram_id=body.telegram_id,
                first_name=body.first_name,
                phone=body.phone,
                birth_date=body.birth_date,
            )
    except DomainError as exc:
        raise _domain_http_error(exc) from exc
    return CustomerResponse(
        id=result.customer.id,
        first_name=result.customer.first_name,
        phone=result.customer.phone,
        balance=result.account.balance,
        tier_id=result.loyalty_state.automatic_tier_id,
        qualification_spend_minor=result.loyalty_state.qualification_spend_minor,
    )


@router.post("/customers/{customer_id}/points/adjust", response_model=PointsEntryResponse)
async def adjust_points(customer_id: UUID, body: AdjustPointsRequest, session: AsyncSession = Depends(get_session)) -> PointsEntryResponse:
    try:
        async with session.begin():
            entry = await points.apply(
                session,
                organization_id=body.organization_id,
                customer_id=customer_id,
                delta=body.delta,
                entry_type=LedgerEntryType.MANUAL,
                reason=body.reason,
                idempotency_key=body.idempotency_key,
            )
    except DomainError as exc:
        raise _domain_http_error(exc) from exc
    return PointsEntryResponse(
        entry_id=entry.id,
        customer_id=entry.customer_id,
        delta=entry.delta,
        balance_after=entry.balance_after,
        entry_type=entry.entry_type,
    )


@router.post("/identification-codes", response_model=IdentificationCodeResponse, status_code=status.HTTP_201_CREATED)
async def generate_identification_code(body: GenerateCodeRequest, session: AsyncSession = Depends(get_session)) -> IdentificationCodeResponse:
    try:
        async with session.begin():
            item = await identification.generate(
                session, organization_id=body.organization_id, customer_id=body.customer_id
            )
    except DomainError as exc:
        raise _domain_http_error(exc) from exc
    return IdentificationCodeResponse(identification_id=item.id, code=item.code, expires_at=item.expires_at)


@router.post("/order-drafts", response_model=DraftResponse, status_code=status.HTTP_201_CREATED)
async def create_order_draft(body: CreateDraftRequest, session: AsyncSession = Depends(get_session)) -> DraftResponse:
    try:
        async with session.begin():
            draft = await orders.create_draft(
                session,
                organization_id=body.organization_id,
                location_id=body.location_id,
                gross_amount_minor=body.gross_amount_minor,
                requested_points=body.requested_points,
                currency_code=body.currency_code,
            )
    except DomainError as exc:
        raise _domain_http_error(exc) from exc
    return DraftResponse(
        draft_id=draft.id,
        version=draft.version,
        customer_id=draft.customer_id,
        gross_amount_minor=draft.gross_amount_minor,
        requested_points=draft.requested_points,
    )


@router.post("/order-drafts/{draft_id}/identify", response_model=DraftResponse)
async def identify_order_draft(draft_id: UUID, body: IdentifyDraftRequest, session: AsyncSession = Depends(get_session)) -> DraftResponse:
    try:
        async with session.begin():
            draft = await identification.attach_to_draft(
                session,
                organization_id=body.organization_id,
                draft_id=draft_id,
                code=body.code,
            )
    except DomainError as exc:
        raise _domain_http_error(exc) from exc
    return DraftResponse(
        draft_id=draft.id,
        version=draft.version,
        customer_id=draft.customer_id,
        gross_amount_minor=draft.gross_amount_minor,
        requested_points=draft.requested_points,
    )


@router.post("/order-drafts/{draft_id}/quote", response_model=QuoteResponse)
async def quote_order(draft_id: UUID, body: QuoteRequest, session: AsyncSession = Depends(get_session)) -> QuoteResponse:
    try:
        async with session.begin():
            result = await orders.quote(session, organization_id=body.organization_id, draft_id=draft_id)
    except DomainError as exc:
        raise _domain_http_error(exc) from exc
    quote = result.quote
    return QuoteResponse(
        quote_id=quote.id,
        draft_id=quote.draft_id,
        tier_id=quote.tier_id,
        potential_tier_id=quote.potential_tier_id,
        gross_amount_minor=quote.gross_amount_minor,
        amount_after_rewards_minor=quote.amount_after_rewards_minor,
        points_balance=result.points_balance,
        max_redeemable_points=quote.max_redeemable_points,
        redeemed_points=quote.redeemed_points,
        paid_amount_minor=quote.paid_amount_minor,
        points_to_earn=quote.points_to_earn,
        qualification_amount_minor=quote.qualification_amount_minor,
        expires_at=quote.expires_at,
    )


@router.post("/order-drafts/{draft_id}/confirm", response_model=OrderResponse)
async def confirm_order(draft_id: UUID, body: ConfirmOrderRequest, session: AsyncSession = Depends(get_session)) -> OrderResponse:
    try:
        async with session.begin():
            order = await orders.confirm(
                session,
                organization_id=body.organization_id,
                draft_id=draft_id,
                quote_id=body.quote_id,
                idempotency_key=body.idempotency_key,
            )
    except DomainError as exc:
        raise _domain_http_error(exc) from exc
    return OrderResponse(
        order_id=order.id,
        customer_id=order.customer_id,
        gross_amount_minor=order.gross_amount_minor,
        redeemed_points=order.redeemed_points,
        paid_amount_minor=order.paid_amount_minor,
        points_earned=order.points_earned,
        tier_before_id=order.tier_before_id,
        tier_after_id=order.tier_after_id,
        status=order.status,
    )
