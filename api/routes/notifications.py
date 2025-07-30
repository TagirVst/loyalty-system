from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from common.schemas import NotificationCreate, NotificationOut
from common import crud
from api.deps import get_session

router = APIRouter()

@router.post("/", response_model=NotificationOut)
async def send_notification(notification: NotificationCreate, session: AsyncSession = Depends(get_session)):
    note = await crud.create_notification(session, notification.text, notification.sent_by, notification.user_id)
    return NotificationOut.model_validate(note)
