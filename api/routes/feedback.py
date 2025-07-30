from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List
from common.schemas import FeedbackOut, FeedbackCreate, IdeaOut, IdeaCreate
from common import crud
from api.deps import get_session

router = APIRouter()

@router.post("/review", response_model=FeedbackOut)
async def create_feedback(feedback: FeedbackCreate, session: AsyncSession = Depends(get_session)):
    feedback_obj = await crud.create_feedback(session, **feedback.model_dump())
    return FeedbackOut.model_validate(feedback_obj)

@router.get("/", response_model=List[FeedbackOut])
async def list_feedbacks(session: AsyncSession = Depends(get_session), limit: int = 100, offset: int = 0):
    """Получить список всех отзывов (для админки)"""
    feedbacks = await crud.get_feedbacks(session, limit, offset)
    return [FeedbackOut.model_validate(f) for f in feedbacks]

@router.post("/idea", response_model=IdeaOut)
async def create_idea(idea: IdeaCreate, session: AsyncSession = Depends(get_session)):
    idea_obj = await crud.create_idea(session, **idea.model_dump())
    return IdeaOut.model_validate(idea_obj)

@router.get("/ideas", response_model=List[IdeaOut])
async def list_ideas(session: AsyncSession = Depends(get_session), limit: int = 100, offset: int = 0):
    """Получить список всех идей (для админки)"""
    ideas = await crud.get_ideas(session, limit, offset)
    return [IdeaOut.model_validate(i) for i in ideas]
