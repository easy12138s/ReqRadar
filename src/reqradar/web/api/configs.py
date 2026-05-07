"""配置管理 API - 系统级/项目级/用户级"""

import logging
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from reqradar.infrastructure.config import load_config
from reqradar.infrastructure.config_manager import ConfigManager
from reqradar.web.dependencies import CurrentUser, DbSession, get_current_user, get_db
from reqradar.web.models import Project, ProjectConfig, SystemConfig, User, UserConfig

logger = logging.getLogger("reqradar.web.api.configs")

router = APIRouter(prefix="/api", tags=["configs"])


class ConfigValueRequest(BaseModel):
    value: Any | None = None
    value_type: str | None = None
    description: str = ""
    is_sensitive: bool = False


class ConfigValueResponse(BaseModel):
    key: str
    value: Any
    value_type: str
    is_sensitive: bool
    updated_at: str | None = None

    model_config = {"from_attributes": True}


class ConfigResolveResponse(BaseModel):
    key: str
    resolved_value: Any
    source: str


# ------------------------------------------------------------------
# 依赖：管理员权限
# ------------------------------------------------------------------


async def _get_admin_user(
    token: str = Depends(lambda: None),
    db: AsyncSession = Depends(get_db),
) -> User:
    user = await get_current_user(
        token=token if token else "",
        db=db,
    )
    if user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")
    return user


AdminUser = Annotated[User, Depends(_get_admin_user)]


# ------------------------------------------------------------------
# 序列化辅助
# ------------------------------------------------------------------


def _serialize_config_row(row) -> dict:
    value = row.config_value
    if row.is_sensitive:
        value = ConfigManager._mask_sensitive(value)
    return {
        "key": row.config_key,
        "value": value,
        "value_type": row.value_type,
        "is_sensitive": row.is_sensitive,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }


# ------------------------------------------------------------------
# 系统级配置 API（管理员权限）
# ------------------------------------------------------------------


@router.get("/configs/system", response_model=list[ConfigValueResponse])
async def list_system_configs(
    db: DbSession,
    current_user: AdminUser,
):
    result = await db.execute(select(SystemConfig))
    rows = result.scalars().all()
    return [_serialize_config_row(r) for r in rows]


@router.get("/configs/system/{key:path}", response_model=ConfigValueResponse)
async def get_system_config(
    key: str,
    db: DbSession,
    current_user: AdminUser,
):
    result = await db.execute(select(SystemConfig).where(SystemConfig.config_key == key))
    row = result.scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Config not found")
    return _serialize_config_row(row)


@router.put("/configs/system/{key:path}", response_model=ConfigValueResponse)
async def set_system_config(
    key: str,
    req: ConfigValueRequest,
    db: DbSession,
    current_user: AdminUser,
):
    cm = ConfigManager(db, load_config())

    if req.value is None:
        result = await db.execute(select(SystemConfig).where(SystemConfig.config_key == key))
        existing = result.scalar_one_or_none()
        if existing is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Config not found, value required"
            )
        return _serialize_config_row(existing)

    if req.value == "":
        deleted = await cm.delete_system(key)
        if not deleted:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Config not found")
        raise HTTPException(status_code=status.HTTP_204_NO_CONTENT)

    config = await cm.set_system(
        key,
        req.value,
        value_type=req.value_type,
        description=req.description,
        is_sensitive=req.is_sensitive,
    )
    return _serialize_config_row(config)


@router.delete("/configs/system/{key:path}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_system_config(
    key: str,
    db: DbSession,
    current_user: AdminUser,
):
    cm = ConfigManager(db, load_config())
    deleted = await cm.delete_system(key)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Config not found")
    return None


# ------------------------------------------------------------------
# 项目级配置 API（项目所有者权限）
# ------------------------------------------------------------------


async def _check_project_access(project_id: int, user_id: int, db: AsyncSession):
    result = await db.execute(
        select(Project).where(Project.id == project_id, Project.owner_id == user_id)
    )
    if result.scalar_one_or_none() is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Project not found or access denied"
        )


@router.get("/projects/{project_id}/configs", response_model=list[ConfigValueResponse])
async def list_project_configs(
    project_id: int,
    db: DbSession,
    current_user: CurrentUser,
):
    await _check_project_access(project_id, current_user.id, db)
    result = await db.execute(select(ProjectConfig).where(ProjectConfig.project_id == project_id))
    rows = result.scalars().all()
    return [_serialize_config_row(r) for r in rows]


@router.get("/projects/{project_id}/configs/{key:path}", response_model=ConfigValueResponse)
async def get_project_config(
    project_id: int,
    key: str,
    db: DbSession,
    current_user: CurrentUser,
):
    await _check_project_access(project_id, current_user.id, db)
    result = await db.execute(
        select(ProjectConfig).where(
            ProjectConfig.project_id == project_id, ProjectConfig.config_key == key
        )
    )
    row = result.scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Config not found")
    return _serialize_config_row(row)


@router.put("/projects/{project_id}/configs/{key:path}", response_model=ConfigValueResponse)
async def set_project_config(
    project_id: int,
    key: str,
    req: ConfigValueRequest,
    db: DbSession,
    current_user: CurrentUser,
):
    await _check_project_access(project_id, current_user.id, db)
    cm = ConfigManager(db, load_config())

    if req.value is None:
        result = await db.execute(
            select(ProjectConfig).where(
                ProjectConfig.project_id == project_id, ProjectConfig.config_key == key
            )
        )
        existing = result.scalar_one_or_none()
        if existing is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Config not found, value required"
            )
        return _serialize_config_row(existing)

    if req.value == "":
        deleted = await cm.delete_project(project_id, key)
        if not deleted:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Config not found")
        raise HTTPException(status_code=status.HTTP_204_NO_CONTENT)

    config = await cm.set_project(
        project_id,
        key,
        req.value,
        value_type=req.value_type,
        is_sensitive=req.is_sensitive,
    )
    return _serialize_config_row(config)


@router.delete("/projects/{project_id}/configs/{key:path}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_project_config(
    project_id: int,
    key: str,
    db: DbSession,
    current_user: CurrentUser,
):
    await _check_project_access(project_id, current_user.id, db)
    cm = ConfigManager(db, load_config())
    deleted = await cm.delete_project(project_id, key)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Config not found")
    return None


# ------------------------------------------------------------------
# 用户级配置 API（本人权限）
# ------------------------------------------------------------------


@router.get("/me/configs", response_model=list[ConfigValueResponse])
async def list_user_configs(
    db: DbSession,
    current_user: CurrentUser,
):
    result = await db.execute(select(UserConfig).where(UserConfig.user_id == current_user.id))
    rows = result.scalars().all()
    return [_serialize_config_row(r) for r in rows]


@router.get("/me/configs/{key:path}", response_model=ConfigValueResponse)
async def get_user_config(
    key: str,
    db: DbSession,
    current_user: CurrentUser,
):
    cm = ConfigManager(db, load_config())
    value = await cm.get(key, user_id=current_user.id)
    return {"key": key, "value": value, "value_type": "string", "is_sensitive": False}


@router.put("/me/configs/{key:path}", response_model=ConfigValueResponse)
async def set_user_config(
    key: str,
    req: ConfigValueRequest,
    db: DbSession,
    current_user: CurrentUser,
):
    cm = ConfigManager(db, load_config())

    if req.value is None:
        result = await db.execute(
            select(UserConfig).where(
                UserConfig.user_id == current_user.id, UserConfig.config_key == key
            )
        )
        existing = result.scalar_one_or_none()
        if existing is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Config not found, value required"
            )
        return _serialize_config_row(existing)

    if req.value == "":
        deleted = await cm.delete_user(current_user.id, key)
        if not deleted:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Config not found")
        raise HTTPException(status_code=status.HTTP_204_NO_CONTENT)

    config = await cm.set_user(
        current_user.id,
        key,
        req.value,
        value_type=req.value_type,
        is_sensitive=req.is_sensitive,
    )
    return _serialize_config_row(config)


@router.delete("/me/configs/{key:path}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user_config(
    key: str,
    db: DbSession,
    current_user: CurrentUser,
):
    cm = ConfigManager(db, load_config())
    deleted = await cm.delete_user(current_user.id, key)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Config not found")
    return None


# ------------------------------------------------------------------
# 配置解析查询 API
# ------------------------------------------------------------------


@router.get("/configs/resolve", response_model=ConfigResolveResponse)
async def resolve_config(
    current_user: CurrentUser,
    db: DbSession,
    key: str = Query(..., description="配置键"),
    project_id: int | None = Query(None, description="项目 ID"),
):
    """查看当前用户 + 指定项目下解析后的最终配置值及其来源"""
    cm = ConfigManager(db, load_config())

    user_result = await db.execute(
        select(UserConfig).where(
            UserConfig.user_id == current_user.id, UserConfig.config_key == key
        )
    )
    if user_result.scalar_one_or_none():
        value = await cm.get(key, user_id=current_user.id, project_id=project_id)
        return ConfigResolveResponse(key=key, resolved_value=value, source="user")

    if project_id is not None:
        proj_result = await db.execute(
            select(ProjectConfig).where(
                ProjectConfig.project_id == project_id, ProjectConfig.config_key == key
            )
        )
        if proj_result.scalar_one_or_none():
            value = await cm.get(key, user_id=current_user.id, project_id=project_id)
            return ConfigResolveResponse(key=key, resolved_value=value, source="project")

    sys_result = await db.execute(select(SystemConfig).where(SystemConfig.config_key == key))
    if sys_result.scalar_one_or_none():
        value = await cm.get(key, user_id=current_user.id, project_id=project_id)
        return ConfigResolveResponse(key=key, resolved_value=value, source="system")

    file_value = cm._get_from_file(key)
    if file_value is not None:
        return ConfigResolveResponse(key=key, resolved_value=file_value, source="file")

    value = await cm.get(key, user_id=current_user.id, project_id=project_id)
    return ConfigResolveResponse(key=key, resolved_value=value, source="default")


@router.post("/me/test-llm")
async def test_llm_connection(
    body: dict,
    current_user: CurrentUser,
):
    provider = body.get("provider", "openai")
    api_key = body.get("api_key", "")
    base_url = body.get("base_url", "https://api.openai.com/v1")
    model = body.get("model", "gpt-4o-mini")

    if provider == "openai" and not api_key:
        raise HTTPException(status_code=400, detail="API Key is required")

    import httpx

    async with httpx.AsyncClient(timeout=15) as client:
        try:
            resp = await client.post(
                f"{base_url.rstrip('/')}/chat/completions",
                headers={"Authorization": f"Bearer {api_key}"},
                json={
                    "model": model,
                    "messages": [{"role": "user", "content": "ping"}],
                    "max_tokens": 5,
                },
            )
            if resp.status_code == 200:
                return {"ok": True, "model": model, "message": "API 连接正常"}
            else:
                detail = ""
                try:
                    detail = resp.json().get("error", {}).get("message", resp.text[:200])
                except Exception:
                    detail = resp.text[:200]
                raise HTTPException(
                    status_code=400, detail=f"API error ({resp.status_code}): {detail}"
                )
        except httpx.ConnectError:
            raise HTTPException(status_code=400, detail="无法连接到 API 服务器，请检查 base_url")
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"连接失败: {str(e)[:200]}")
