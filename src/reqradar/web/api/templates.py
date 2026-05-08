import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select

from reqradar.web.dependencies import CurrentUser, DbSession
from reqradar.web.models import ReportTemplate

logger = logging.getLogger("reqradar.web.api.templates")

router = APIRouter(prefix="/api/templates", tags=["templates"])


class TemplateCreate(BaseModel):
    name: str
    description: str = ""
    definition: str
    render_template: str


class TemplateUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    definition: Optional[str] = None
    render_template: Optional[str] = None


class TemplateResponse(BaseModel):
    id: int
    name: str
    description: str
    definition: str
    render_template: str
    is_default: bool
    created_by: int | None

    model_config = {"from_attributes": True}


@router.get("", response_model=list[TemplateResponse])
async def list_templates(current_user: CurrentUser, db: DbSession):
    result = await db.execute(
        select(ReportTemplate).order_by(ReportTemplate.is_default.desc(), ReportTemplate.name.asc())
    )
    return list(result.scalars().all())


@router.get("/{template_id}", response_model=TemplateResponse)
async def get_template(template_id: int, current_user: CurrentUser, db: DbSession):
    result = await db.execute(select(ReportTemplate).where(ReportTemplate.id == template_id))
    template = result.scalar_one_or_none()
    if template is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Template not found")
    return template


@router.post("", response_model=TemplateResponse, status_code=status.HTTP_201_CREATED)
async def create_template(req: TemplateCreate, current_user: CurrentUser, db: DbSession):
    template = ReportTemplate(
        name=req.name,
        description=req.description,
        definition=req.definition,
        render_template=req.render_template,
        is_default=False,
        created_by=current_user.id,
    )
    db.add(template)
    await db.commit()
    await db.refresh(template)
    return template


@router.put("/{template_id}", response_model=TemplateResponse)
async def update_template(
    template_id: int,
    req: TemplateUpdate,
    current_user: CurrentUser,
    db: DbSession,
):
    result = await db.execute(select(ReportTemplate).where(ReportTemplate.id == template_id))
    template = result.scalar_one_or_none()
    if template is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Template not found")

    if template.is_default:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Cannot modify default template"
        )

    if req.name is not None:
        template.name = req.name
    if req.description is not None:
        template.description = req.description
    if req.definition is not None:
        template.definition = req.definition
    if req.render_template is not None:
        template.render_template = req.render_template

    await db.commit()
    await db.refresh(template)
    return template


@router.post("/{template_id}/set-default")
async def set_default_template(
    template_id: int,
    current_user: CurrentUser,
    db: DbSession,
):
    result = await db.execute(select(ReportTemplate).where(ReportTemplate.id == template_id))
    template = result.scalar_one_or_none()
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")

    all_defaults = await db.execute(select(ReportTemplate).where(ReportTemplate.is_default == True))
    for t in all_defaults.scalars().all():
        t.is_default = False

    template.is_default = True
    await db.commit()
    return {"success": True}


@router.delete("/{template_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_template(template_id: int, current_user: CurrentUser, db: DbSession):
    result = await db.execute(select(ReportTemplate).where(ReportTemplate.id == template_id))
    template = result.scalar_one_or_none()
    if template is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Template not found")

    if template.is_default:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Cannot delete default template"
        )

    await db.delete(template)
    await db.commit()
    return None
