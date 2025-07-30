from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from common.schemas import CodeOut
from common import crud
from api.deps import get_session

router = APIRouter()

@router.post("/generate", response_model=CodeOut)
async def generate_code(user_id: int, session: AsyncSession = Depends(get_session)):
    code = await crud.generate_code(session, user_id)
    return CodeOut.model_validate(code)

@router.post("/use", response_model=CodeOut)
async def use_code(code_value: str, session: AsyncSession = Depends(get_session)):
    code = await crud.use_code(session, code_value)
    if not code:
        raise HTTPException(400, "Код недействителен или уже использован")
    return CodeOut.model_validate(code)
