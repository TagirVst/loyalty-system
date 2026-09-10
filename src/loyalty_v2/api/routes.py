from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from loyalty_v2.api.schemas import (
    AdjustPointsRequest,
    CustomerResponse,
    PointsEntryResponse,
    RegisterCustomerRequest,
)
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
async def register_customer(
    body: RegisterCustomerRequest,
    session: AsyncSession = Depends(get_session),
) -> CustomerResponse:
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
async def adjust_points(
    customer_id: UUID,
    body: AdjustPointsRequest,
    session: AsyncSession = Depends(get_session),
) -> PointsEntryResponse:
    # Authorization/permission checks will be added with the AuthService layer.
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
