import hashlib
import random
from datetime import datetime, timezone
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from reqradar.web.models import User


oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")

async_session_factory = None


async def get_db(request: Request):
    session_factory = getattr(request.app.state, "session_factory", None) or async_session_factory
    async with session_factory() as session:
        yield session


DbSession = Annotated[AsyncSession, Depends(get_db)]


async def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)], request: Request, db: DbSession
):
    from reqradar.web.api.auth import ALGORITHM

    secret_key = getattr(request.app.state, "secret_key", None)
    if secret_key is None:
        from reqradar.web.api.auth import SECRET_KEY

        secret_key = SECRET_KEY

    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, secret_key, algorithms=[ALGORITHM])
        user_id_raw = payload.get("sub")
        if user_id_raw is None:
            raise credentials_exception
        user_id: int = int(user_id_raw)
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token has expired")
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")

    from reqradar.web.models import RevokedToken

    token_hash = hashlib.sha256(token.encode()).hexdigest()
    result = await db.execute(select(RevokedToken).where(RevokedToken.token_hash == token_hash))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=401, detail="Token has been revoked")

    if random.randint(0, 100) == 0:
        await db.execute(
            delete(RevokedToken).where(RevokedToken.expires_at < datetime.now(timezone.utc))
        )

    user = await db.get(User, user_id)
    if user is None:
        raise credentials_exception
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]
