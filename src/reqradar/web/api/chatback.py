import logging

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select

from reqradar.infrastructure.config import load_config
from reqradar.infrastructure.config_manager import ConfigManager
from reqradar.modules.llm_client import create_llm_client
from reqradar.web.dependencies import DbSession, CurrentUser
from reqradar.web.models import AnalysisTask
from reqradar.web.services.chatback_service import ChatbackService
from reqradar.web.services.version_service import VersionService

logger = logging.getLogger("reqradar.api.chatback")

router = APIRouter(prefix="/api/analyses/{task_id}", tags=["chatback"])


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
    task_result = await db.execute(
        select(AnalysisTask).where(
            AnalysisTask.id == task_id, AnalysisTask.user_id == current_user.id
        )
    )
    task = task_result.scalar_one_or_none()
    if task is None:
        raise HTTPException(status_code=404, detail="Analysis task not found")

    version_number = req.version_number or task.current_version or 1
    user_id = current_user.id

    config = load_config()
    cm = ConfigManager(db, config)
    provider = await cm.get_str(
        "llm.provider", user_id=user_id, project_id=task.project_id, default="openai"
    )
    api_key = await cm.get_str(
        "llm.api_key", user_id=user_id, project_id=task.project_id, default=""
    )
    llm_model = await cm.get_str(
        "llm.model", user_id=user_id, project_id=task.project_id, default=config.llm.model
    )
    llm_base_url = await cm.get_str(
        "llm.base_url",
        user_id=user_id,
        project_id=task.project_id,
        default=config.llm.base_url or "https://api.openai.com/v1",
    )

    if provider == "openai" and not api_key:
        raise HTTPException(status_code=400, detail="LLM API Key 未配置，请先在设置页面配置大模型")

    llm_client = create_llm_client(
        provider,
        api_key=api_key,
        model=llm_model,
        base_url=llm_base_url,
        timeout=config.llm.timeout,
        max_retries=config.llm.max_retries,
    )

    version_service = VersionService(db)
    chatback_service = ChatbackService(
        version_service=version_service, llm_client=llm_client, config=config
    )
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
    task_result = await db.execute(
        select(AnalysisTask).where(
            AnalysisTask.id == task_id, AnalysisTask.user_id == current_user.id
        )
    )
    task = task_result.scalar_one_or_none()
    if task is None:
        raise HTTPException(status_code=404, detail="Analysis task not found")

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
    task_result = await db.execute(
        select(AnalysisTask).where(
            AnalysisTask.id == task_id, AnalysisTask.user_id == current_user.id
        )
    )
    task = task_result.scalar_one_or_none()
    if task is None:
        raise HTTPException(status_code=404, detail="Analysis task not found")

    user_id = current_user.id
    version_service = VersionService(db)
    chatback_service = ChatbackService(version_service=version_service)
    result = await chatback_service.save_as_new_version(
        task_id=task_id,
        version_number=req.version_number,
        user_id=user_id,
    )
    return result
