import json
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from reqradar.web.dependencies import CurrentUser, DbSession, get_db, get_current_user
from reqradar.web.models import SynonymMapping

logger = logging.getLogger("reqradar.web.api.synonyms")

router = APIRouter(prefix="/api/synonyms", tags=["synonyms"])


class SynonymCreate(BaseModel):
    project_id: int | None = None
    business_term: str
    code_terms: list[str] = []
    priority: int = 100
    source: str = "user"


class SynonymUpdate(BaseModel):
    business_term: Optional[str] = None
    code_terms: Optional[list[str]] = None
    priority: Optional[int] = None


class SynonymResponse(BaseModel):
    id: int
    project_id: int | None
    business_term: str
    code_terms: list[str]
    priority: int
    source: str
    created_by: int | None

    model_config = {"from_attributes": True}

    @classmethod
    def from_orm_with_terms(cls, mapping: SynonymMapping) -> "SynonymResponse":
        terms = json.loads(mapping.code_terms) if mapping.code_terms else []
        return cls(
            id=mapping.id,
            project_id=mapping.project_id,
            business_term=mapping.business_term,
            code_terms=terms,
            priority=mapping.priority,
            source=mapping.source,
            created_by=mapping.created_by,
        )


@router.get("", response_model=list[SynonymResponse])
async def list_synonyms(
    current_user: CurrentUser,
    db: DbSession,
    project_id: int = Query(...),
):
    query = select(SynonymMapping).where(SynonymMapping.project_id == project_id)
    result = await db.execute(query.order_by(SynonymMapping.priority.asc(), SynonymMapping.business_term.asc()))
    mappings = result.scalars().all()
    return [SynonymResponse.from_orm_with_terms(m) for m in mappings]


@router.post("", response_model=SynonymResponse, status_code=status.HTTP_201_CREATED)
async def create_synonym(req: SynonymCreate, current_user: CurrentUser, db: DbSession):
    mapping = SynonymMapping(
        project_id=req.project_id,
        business_term=req.business_term,
        code_terms=json.dumps(req.code_terms),
        priority=req.priority,
        source=req.source,
        created_by=current_user.id,
    )
    db.add(mapping)
    await db.commit()
    await db.refresh(mapping)
    return SynonymResponse.from_orm_with_terms(mapping)


@router.put("/{synonym_id}", response_model=SynonymResponse)
async def update_synonym(
    synonym_id: int,
    req: SynonymUpdate,
    current_user: CurrentUser,
    db: DbSession,
):
    result = await db.execute(select(SynonymMapping).where(SynonymMapping.id == synonym_id))
    mapping = result.scalar_one_or_none()
    if mapping is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Synonym mapping not found")

    if req.business_term is not None:
        mapping.business_term = req.business_term
    if req.code_terms is not None:
        mapping.code_terms = json.dumps(req.code_terms)
    if req.priority is not None:
        mapping.priority = req.priority

    await db.commit()
    await db.refresh(mapping)
    return SynonymResponse.from_orm_with_terms(mapping)


@router.delete("/{synonym_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_synonym(
    synonym_id: int,
    current_user: CurrentUser,
    db: DbSession,
    project_id: int = Query(...),
):
    result = await db.execute(
        select(SynonymMapping).where(SynonymMapping.id == synonym_id, SynonymMapping.project_id == project_id)
    )
    mapping = result.scalar_one_or_none()
    if mapping is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Synonym mapping not found")
    await db.delete(mapping)
    await db.commit()
    return None
