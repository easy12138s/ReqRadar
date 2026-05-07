import logging

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse
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

    from reqradar.modules.llm_connectivity import is_llm_reachable

    connectivity = is_llm_reachable(provider, api_key, llm_base_url)
    if connectivity is False:
        raise HTTPException(
            status_code=400,
            detail="LLM 连接不通，请检查设置页面的 API 配置并使用「测试连接」按钮验证",
        )

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


@router.post("/chat/stream")
async def chat_stream(
    task_id: int,
    req: ChatRequest,
    db: DbSession,
    current_user: CurrentUser,
):
    import json as _json
    from reqradar.agent.prompts.chatback_phase import build_chatback_system_prompt
    from reqradar.web.models import ReportChat
    from reqradar.web.services.chatback_service import classify_intent

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
        raise HTTPException(status_code=400, detail="LLM API Key 未配置")

    from reqradar.modules.llm_connectivity import is_llm_reachable

    connectivity = is_llm_reachable(provider, api_key, llm_base_url)
    if connectivity is False:
        raise HTTPException(status_code=400, detail="LLM 连接不通")

    llm_client = create_llm_client(
        provider,
        api_key=api_key,
        model=llm_model,
        base_url=llm_base_url,
        timeout=config.llm.timeout,
        max_retries=config.llm.max_retries,
    )

    version_service = VersionService(db)
    intent = classify_intent(req.message)

    chat_record = ReportChat(
        task_id=task_id,
        version_number=version_number,
        role="user",
        content=req.message,
        intent_type=intent,
    )
    db.add(chat_record)
    await db.commit()
    await db.refresh(chat_record)

    async def token_generator():
        collected = []
        try:
            version = await version_service.get_version(task_id, version_number)
            if version is None:
                yield f"data: {_json.dumps({'error': 'Version not found'})}\n\n"
                return

            report_data = version.report_data or {}
            context_snapshot = (
                await version_service.get_context_snapshot(task_id, version_number) or {}
            )
            system_prompt = build_chatback_system_prompt(
                report_data=report_data, context_snapshot=context_snapshot
            )
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": req.message},
            ]

            async for token in llm_client.stream_complete(messages):
                collected.append(token)
                yield f"data: {_json.dumps({'token': token})}\n\n"

            full_reply = "".join(collected)
            agent_reply = ReportChat(
                task_id=task_id,
                version_number=version_number,
                role="agent",
                content=full_reply,
                evidence_refs=[],
            )
            db.add(agent_reply)
            await db.commit()
            await db.refresh(agent_reply)
            yield f"data: {_json.dumps({'done': True, 'chat_id': agent_reply.id})}\n\n"

        except Exception as e:
            logger.warning("Stream chat failed: %s", e)
            yield f"data: {_json.dumps({'error': '调用失败，请检查 LLM 配置'})}\n\n"

    return StreamingResponse(token_generator(), media_type="text/event-stream")


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
