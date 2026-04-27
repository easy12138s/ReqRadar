from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from reqradar.web.models import User


oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")

async_session_factory = None


async def get_db(request: Request):
    session_factory = getattr(request.app.state, "session_factory", None) or async_session_factory
    async with session_factory() as session:
        yield session


DbSession = Annotated[AsyncSession, Depends(get_db)]


async def get_current_user(token: Annotated[str, Depends(oauth2_scheme)], request: Request, db: DbSession):
    from reqradar.web.api.auth import ALGORITHM, _revoked_tokens

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
        if token in _revoked_tokens:
            raise credentials_exception
        user_id_raw = payload.get("sub")
        if user_id_raw is None:
            raise credentials_exception
        user_id: int = int(user_id_raw)
    except (JWTError, ValueError, TypeError):
        raise credentials_exception

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise credentials_exception
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]