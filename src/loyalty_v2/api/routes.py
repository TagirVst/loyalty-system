from uuid import UUID
from fastapi import APIRouter,Depends,HTTPException,status
from sqlalchemy.ext.asyncio import AsyncSession
from loyalty_v2.api.schemas import *
from loyalty_v2.application.auth_service import Permission,StaffAuthService
from loyalty_v2.application.order_service import IdentificationService,OrderService
from loyalty_v2.application.refund_service import RefundService
from loyalty_v2.application.services import CustomerAlreadyExists,CustomerNotFound,CustomerService,DomainError,InsufficientPoints,PointsService
from loyalty_v2.db.models import LedgerEntryType
from loyalty_v2.db.order_models import Order
from loyalty_v2.db.session import get_session
router=APIRouter(prefix="/v2"); customers,points=CustomerService(),PointsService(); identification,orders,staff_auth,refunds=IdentificationService(),OrderService(),StaffAuthService(),RefundService()
def _domain_http_error(exc):
    s=status.HTTP_422_UNPROCESSABLE_ENTITY
    if isinstance(exc,CustomerAlreadyExists): s=409
    elif isinstance(exc,CustomerNotFound): s=404
    elif isinstance(exc,InsufficientPoints): s=409
    elif exc.code in {"INVALID_PIN","PIN_LOCKED","STAFF_SESSION_INVALID","TERMINAL_NOT_AUTHORIZED"}: s=401
    elif exc.code=="PERMISSION_DENIED": s=403
    return HTTPException(status_code=s,detail={"code":exc.code,"message":str(exc)})
@router.post("/staff/login",response_model=StaffSessionResponse)
async def staff_login(body:StaffLoginRequest,session:AsyncSession=Depends(get_session)):
    try:
        async with session.begin(): a=await staff_auth.authenticate(session,organization_id=body.organization_id,terminal_id=body.terminal_id,pin=body.pin)
    except DomainError as e: raise _domain_http_error(e) from e
    return StaffSessionResponse(staff_session_id=a.id,staff_id=a.staff_id,terminal_id=a.terminal_id,status=a.status)
@router.post("/staff/logout",status_code=204)
async def staff_logout(body:StaffLogoutRequest,session:AsyncSession=Depends(get_session)):
    try:
        async with session.begin(): await staff_auth.logout(session,body.staff_session_id)
    except DomainError as e: raise _domain_http_error(e) from e
@router.post("/customers",response_model=CustomerResponse,status_code=201)
async def register_customer(body:RegisterCustomerRequest,session:AsyncSession=Depends(get_session)):
    try:
        async with session.begin(): r=await customers.register(session,organization_id=body.organization_id,telegram_id=body.telegram_id,first_name=body.first_name,phone=body.phone,birth_date=body.birth_date)
    except DomainError as e: raise _domain_http_error(e) from e
    return CustomerResponse(id=r.customer.id,first_name=r.customer.first_name,phone=r.customer.phone,balance=r.account.balance,tier_id=r.loyalty_state.automatic_tier_id,qualification_spend_minor=r.loyalty_state.qualification_spend_minor)
@router.post("/customers/{customer_id}/points/adjust",response_model=PointsEntryResponse)
async def adjust_points(customer_id:UUID,body:AdjustPointsRequest,session:AsyncSession=Depends(get_session)):
    try:
        async with session.begin(): await staff_auth.require(session,staff_session_id=body.staff_session_id,permission=Permission.POINTS_ADJUST); e=await points.apply(session,organization_id=body.organization_id,customer_id=customer_id,delta=body.delta,entry_type=LedgerEntryType.MANUAL,reason=body.reason,idempotency_key=body.idempotency_key)
    except DomainError as x: raise _domain_http_error(x) from x
    return PointsEntryResponse(entry_id=e.id,customer_id=e.customer_id,delta=e.delta,balance_after=e.balance_after,entry_type=e.entry_type)
@router.post("/identification-codes",response_model=IdentificationCodeResponse,status_code=201)
async def generate_identification_code(body:GenerateCodeRequest,session:AsyncSession=Depends(get_session)):
    try:
        async with session.begin(): i=await identification.generate(session,organization_id=body.organization_id,customer_id=body.customer_id)
    except DomainError as e: raise _domain_http_error(e) from e
    return IdentificationCodeResponse(identification_id=i.id,code=i.code,expires_at=i.expires_at)
@router.post("/order-drafts",response_model=DraftResponse,status_code=201)
async def create_order_draft(body:CreateDraftRequest,session:AsyncSession=Depends(get_session)):
    try:
        async with session.begin():
            a,_=await staff_auth.require(session,staff_session_id=body.staff_session_id,permission=Permission.SALE_CREATE)
            if a.organization_id!=body.organization_id: raise HTTPException(status_code=403,detail={"code":"ORGANIZATION_MISMATCH"})
            d=await orders.create_draft(session,organization_id=body.organization_id,location_id=body.location_id,gross_amount_minor=body.gross_amount_minor,requested_points=body.requested_points,currency_code=body.currency_code,selected_reward_ids=body.selected_reward_ids)
    except DomainError as e: raise _domain_http_error(e) from e
    return DraftResponse(draft_id=d.id,version=d.version,customer_id=d.customer_id,gross_amount_minor=d.gross_amount_minor,requested_points=d.requested_points,selected_reward_ids=[UUID(x) for x in d.selected_reward_ids])
@router.post("/order-drafts/{draft_id}/identify",response_model=DraftResponse)
async def identify_order_draft(draft_id:UUID,body:IdentifyDraftRequest,session:AsyncSession=Depends(get_session)):
    try:
        async with session.begin(): await staff_auth.require(session,staff_session_id=body.staff_session_id,permission=Permission.SALE_CREATE); d=await identification.attach_to_draft(session,organization_id=body.organization_id,draft_id=draft_id,code=body.code)
    except DomainError as e: raise _domain_http_error(e) from e
    return DraftResponse(draft_id=d.id,version=d.version,customer_id=d.customer_id,gross_amount_minor=d.gross_amount_minor,requested_points=d.requested_points,selected_reward_ids=[UUID(x) for x in d.selected_reward_ids])
@router.post("/order-drafts/{draft_id}/quote",response_model=QuoteResponse)
async def quote_order(draft_id:UUID,body:QuoteRequest,session:AsyncSession=Depends(get_session)):
    try:
        async with session.begin(): await staff_auth.require(session,staff_session_id=body.staff_session_id,permission=Permission.SALE_CREATE); r=await orders.quote(session,organization_id=body.organization_id,draft_id=draft_id)
    except DomainError as e: raise _domain_http_error(e) from e
    q=r.quote; return QuoteResponse(quote_id=q.id,draft_id=q.draft_id,tier_id=q.tier_id,potential_tier_id=q.potential_tier_id,gross_amount_minor=q.gross_amount_minor,amount_after_rewards_minor=q.amount_after_rewards_minor,points_balance=r.points_balance,max_redeemable_points=q.max_redeemable_points,redeemed_points=q.redeemed_points,paid_amount_minor=q.paid_amount_minor,points_to_earn=q.points_to_earn,qualification_amount_minor=q.qualification_amount_minor,expires_at=q.expires_at)
@router.post("/order-drafts/{draft_id}/confirm",response_model=OrderResponse)
async def confirm_order(draft_id:UUID,body:ConfirmOrderRequest,session:AsyncSession=Depends(get_session)):
    try:
        async with session.begin(): _,staff=await staff_auth.require(session,staff_session_id=body.staff_session_id,permission=Permission.SALE_CONFIRM); o=await orders.confirm(session,organization_id=body.organization_id,draft_id=draft_id,quote_id=body.quote_id,idempotency_key=body.idempotency_key); o.actor_staff_id=staff.id
    except DomainError as e: raise _domain_http_error(e) from e
    return OrderResponse(order_id=o.id,customer_id=o.customer_id,gross_amount_minor=o.gross_amount_minor,redeemed_points=o.redeemed_points,paid_amount_minor=o.paid_amount_minor,points_earned=o.points_earned,tier_before_id=o.tier_before_id,tier_after_id=o.tier_after_id,status=o.status)
@router.post("/orders/{order_id}/refund-preview",response_model=RefundPreviewResponse)
async def refund_preview(order_id:UUID,body:RefundPreviewRequest,session:AsyncSession=Depends(get_session)):
    try:
        async with session.begin(): await staff_auth.require(session,staff_session_id=body.staff_session_id,permission=Permission.ADMIN_ACCESS); p=await refunds.preview(session,organization_id=body.organization_id,order_id=order_id,gross_refund_minor=body.gross_refund_minor)
    except DomainError as e: raise _domain_http_error(e) from e
    return RefundPreviewResponse(gross_refund_minor=p.gross_refund_minor,paid_refund_minor=p.paid_refund_minor,restored_points=p.restored_points,reversed_earned_points=p.reversed_earned_points,qualification_reversal_minor=p.qualification_reversal_minor,remaining_gross_minor=p.remaining_gross_minor)
@router.post("/orders/{order_id}/refund",response_model=RefundResponse)
async def confirm_refund(order_id:UUID,body:ConfirmRefundRequest,session:AsyncSession=Depends(get_session)):
    try:
        async with session.begin(): _,staff=await staff_auth.require(session,staff_session_id=body.staff_session_id,permission=Permission.ADMIN_ACCESS); r=await refunds.confirm(session,organization_id=body.organization_id,order_id=order_id,actor_staff_id=staff.id,reason=body.reason,idempotency_key=body.idempotency_key,gross_refund_minor=body.gross_refund_minor)
    except DomainError as e: raise _domain_http_error(e) from e
    return RefundResponse(refund_id=r.id,order_id=r.order_id,refund_type=r.refund_type,gross_refund_minor=r.gross_refund_minor,paid_refund_minor=r.paid_refund_minor,restored_points=r.restored_points,reversed_earned_points=r.reversed_earned_points)
@router.post("/orders/{order_id}/cancel-own",response_model=RefundResponse)
async def cancel_own_order(order_id:UUID,body:CancelOwnOrderRequest,session:AsyncSession=Depends(get_session)):
    try:
        async with session.begin():
            _,staff=await staff_auth.require(session,staff_session_id=body.staff_session_id,permission=Permission.SALE_CANCEL_OWN); o=await session.get(Order,order_id)
            if o is None or o.organization_id!=body.organization_id or o.actor_staff_id!=staff.id: raise HTTPException(status_code=403,detail={"code":"NOT_OWN_ORDER"})
            r=await refunds.confirm(session,organization_id=body.organization_id,order_id=order_id,actor_staff_id=staff.id,reason=body.reason,idempotency_key=body.idempotency_key,cashier_cancel=True)
    except DomainError as e: raise _domain_http_error(e) from e
    return RefundResponse(refund_id=r.id,order_id=r.order_id,refund_type=r.refund_type,gross_refund_minor=r.gross_refund_minor,paid_refund_minor=r.paid_refund_minor,restored_points=r.restored_points,reversed_earned_points=r.reversed_earned_points)
