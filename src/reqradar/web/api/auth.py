import hashlib
import re
from datetime import datetime, timedelta, timezone
from typing import Annotated, Optional

import bcrypt
from fastapi import APIRouter, Depends, HTTPException, status
from jose import JWTError, jwt
from pydantic import BaseModel, EmailStr
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from reqradar.infrastructure.config import load_config
from reqradar.web.dependencies import DbSession, CurrentUser, oauth2_scheme
from reqradar.web.models import RevokedToken, User


router = APIRouter(prefix="/api/auth", tags=["auth"])

ALGORITHM = "HS256"
SECRET_KEY = "change-me-in-production"
ACCESS_TOKEN_EXPIRE_MINUTES = 1440


def get_secret_key(request=None) -> str:
    if request and hasattr(request.app.state, "secret_key"):
        return request.app.state.secret_key
    return SECRET_KEY


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str
    display_name: str


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class UserResponse(BaseModel):
    id: int
    email: str
    display_name: str
    role: str
    created_at: datetime

    model_config = {"from_attributes": True}


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


def _validate_password_strength(password: str) -> str | None:
    if len(password) < 8:
        return "Password must be at least 8 characters long"
    if not re.search(r"[A-Z]", password):
        return "Password must contain at least one uppercase letter"
    if not re.search(r"[a-z]", password):
        return "Password must contain at least one lowercase letter"
    if not re.search(r"\d", password):
        return "Password must contain at least one digit"
    return None


def create_access_token(user_id: int, expires_delta: Optional[timedelta] = None) -> str:
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    to_encode = {"sub": str(user_id), "exp": expire}
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(req: RegisterRequest, db: DbSession):
    pw_error = _validate_password_strength(req.password)
    if pw_error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=pw_error)

    result = await db.execute(select(User).where(User.email == req.email))
    if result.scalar_one_or_none() is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")

    password_hash = hash_password(req.password)
    user = User(
        email=req.email,
        password_hash=password_hash,
        display_name=req.display_name,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


@router.post("/login", response_model=TokenResponse)
async def login(req: LoginRequest, db: DbSession):
    result = await db.execute(select(User).where(User.email == req.email))
    user = result.scalar_one_or_none()
    if user is None or not verify_password(req.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    from reqradar.infrastructure.config_manager import ConfigManager

    cm = ConfigManager(db, load_config())
    expire_minutes = await cm.get_int(
        "web.access_token_expire_minutes",
        default=ACCESS_TOKEN_EXPIRE_MINUTES,
    )
    access_token = create_access_token(user.id, expires_delta=timedelta(minutes=expire_minutes))
    return TokenResponse(access_token=access_token)


@router.get("/me", response_model=UserResponse)
async def me(current_user: CurrentUser):
    return current_user


@router.post("/logout")
async def logout(
    token: Annotated[str, Depends(oauth2_scheme)],
    current_user: CurrentUser,
    db: DbSession,
):
    payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    expires_at = datetime.fromtimestamp(payload["exp"], tz=timezone.utc)

    token_hash = hashlib.sha256(token.encode()).hexdigest()
    revoked = RevokedToken(
        token_hash=token_hash,
        user_id=current_user.id,
        expires_at=expires_at,
    )
    try:
        db.add(revoked)
        await db.commit()
    except IntegrityError:
        await db.rollback()
    return {"detail": "Successfully logged out"}


class PasswordChangeRequest(BaseModel):
    old_password: str
    new_password: str


@router.put("/me/password")
async def change_password(
    req: PasswordChangeRequest,
    current_user: CurrentUser,
    db: DbSession,
):
    if not bcrypt.checkpw(
        req.old_password.encode("utf-8"),
        current_user.password_hash.encode("utf-8"),
    ):
        raise HTTPException(status_code=400, detail="Current password is incorrect")

    pw_error = _validate_password_strength(req.new_password)
    if pw_error:
        raise HTTPException(status_code=400, detail=pw_error)
    current_user.password_hash = bcrypt.hashpw(
        req.new_password.encode("utf-8"), bcrypt.gensalt()
    ).decode("utf-8")
    await db.commit()
    return {"detail": "Password changed successfully"}
