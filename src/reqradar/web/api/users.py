from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from reqradar.web.dependencies import DbSession, CurrentUser
from reqradar.web.models import User

router = APIRouter(prefix="/api/users", tags=["users"])


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
    body: dict,
    db: DbSession,
    current_user: CurrentUser,
):
    if current_user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin only")

    # admin不能通过API改变自己的角色
    if current_user.id == user_id and "role" in body:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot change your own role"
        )

    user = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    if "role" in body and body["role"] in ("admin", "user"):
        user.role = body["role"]
    if "display_name" in body and body["display_name"]:
        user.display_name = body["display_name"]

    await db.commit()
    return {"id": user.id, "updated": True}


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
