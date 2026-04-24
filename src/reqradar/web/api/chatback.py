import logging

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select

from reqradar.web.dependencies import DbSession, CurrentUser
from reqradar.web.models import AnalysisTask
from reqradar.web.services.chatback_service import ChatbackService
from reqradar.web.services.version_service import VersionService

logger = logging.getLogger("reqradar.api.chatback")

router = APIRouter(prefix="/analyses/{task_id}", tags=["chatback"])


class ChatRequest(BaseModel):
    message: str
    version_number: int | None = None


class SaveRequest(BaseModel):
    version_number: int


@router.post("/chat")
async def chat(
    task_id: int,
    req: ChatRequest,
    db: DbSession,
    current_user: CurrentUser,
):
    task_result = await db.execute(select(AnalysisTask).where(AnalysisTask.id == task_id))
    task = task_result.scalar_one_or_none()
    if task is None:
        raise HTTPException(status_code=404, detail="Analysis task not found")

    version_number = req.version_number or task.current_version or 1
    user_id = current_user.id

    version_service = VersionService(db)
    chatback_service = ChatbackService(version_service=version_service)
    result = await chatback_service.chat(
        task_id=task_id,
        version_number=version_number,
        user_message=req.message,
        user_id=user_id,
    )
    return result


@router.get("/chat")
async def get_chat_history(
    task_id: int,
    db: DbSession,
    current_user: CurrentUser,
    version_number: int | None = Query(default=None),
):
    version_service = VersionService(db)
    chatback_service = ChatbackService(version_service=version_service)
    messages = await chatback_service.get_chat_history(task_id, version_number)
    return {"messages": messages}


@router.post("/chat/save")
async def save_chat_version(
    task_id: int,
    req: SaveRequest,
    db: DbSession,
    current_user: CurrentUser,
):
    user_id = current_user.id
    version_service = VersionService(db)
    chatback_service = ChatbackService(version_service=version_service)
    result = await chatback_service.save_as_new_version(
        task_id=task_id,
        version_number=req.version_number,
        user_id=user_id,
    )
    return result
