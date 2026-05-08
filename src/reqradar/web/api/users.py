from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from reqradar.web.dependencies import DbSession, CurrentUser
from reqradar.web.models import User

router = APIRouter(prefix="/api/users", tags=["users"])


class UserResponse(BaseModel):
    id: int
    email: str
    display_name: str
    role: str
    created_at: datetime

    model_config = {"from_attributes": True}


class UserUpdateRequest(BaseModel):
    role: Optional[str] = None
    display_name: Optional[str] = None


@router.get("")
async def list_users(
    db: DbSession,
    current_user: CurrentUser,
):
    if current_user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin only")

    result = await db.execute(select(User).order_by(User.created_at.desc()))
    users = result.scalars().all()
    return [
        {
            "id": u.id,
            "email": u.email,
            "display_name": u.display_name,
            "role": u.role,
            "created_at": u.created_at.isoformat() if u.created_at else "",
        }
        for u in users
    ]


@router.put("/{user_id}")
async def update_user(
    user_id: int,
    body: UserUpdateRequest,
    db: DbSession,
    current_user: CurrentUser,
):
    if current_user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin only")

    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    if user.id == current_user.id and body.role is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot change your own role"
        )

    if body.role is not None:
        if body.role not in ("admin", "user"):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid role")
        user.role = body.role
    if body.display_name is not None and body.display_name.strip():
        user.display_name = body.display_name.strip()

    await db.commit()
    return UserResponse.model_validate(user)


@router.delete("/{user_id}")
async def delete_user(
    user_id: int,
    db: DbSession,
    current_user: CurrentUser,
):
    if current_user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin only")

    if current_user.id == user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot delete yourself"
        )

    user = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    await db.delete(user)
    await db.commit()
    return {"deleted": True}
