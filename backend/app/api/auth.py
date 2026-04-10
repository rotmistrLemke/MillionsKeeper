"""
api/auth.py — JWT аутентификация на основе MT5 логина/пароля/сервера.

Выдаёт JWT при успешном mt5.login(). Проверяет токен в Depends.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Annotated, Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from jose import JWTError, jwt
from pydantic import BaseModel

from app.core.config import settings

logger = logging.getLogger("Auth")

_bearer = HTTPBearer(auto_error=False)


# ── Schemas ───────────────────────────────────────────────────────────────────

class LoginRequest(BaseModel):
    login: int
    password: str
    server: str


class TokenResponse(BaseModel):
    token: str
    expires_in: int  # seconds


class TokenData(BaseModel):
    login: int
    server: str


# ── JWT helpers ───────────────────────────────────────────────────────────────

def _create_token(login: int, server: str) -> str:
    expire = datetime.now(tz=timezone.utc) + timedelta(hours=settings.jwt_expire_hours)
    payload = {
        "sub": str(login),
        "server": server,
        "exp": expire,
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm="HS256")


def _decode_token(token: str) -> Optional[TokenData]:
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])
        return TokenData(login=int(payload["sub"]), server=payload["server"])
    except (JWTError, KeyError, ValueError):
        return None


# ── Dependency ────────────────────────────────────────────────────────────────

def get_current_user(
    credentials: Annotated[Optional[HTTPAuthorizationCredentials], Depends(_bearer)]
) -> TokenData:
    if credentials is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    token_data = _decode_token(credentials.credentials)
    if token_data is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")
    return token_data


OptionalAuth = Annotated[Optional[TokenData], Depends(
    lambda credentials=Depends(_bearer): _decode_token(credentials.credentials) if credentials else None
)]

RequireAuth = Annotated[TokenData, Depends(get_current_user)]


# ── Login endpoint helper ─────────────────────────────────────────────────────

async def authenticate_mt5(req: LoginRequest) -> TokenResponse:
    """
    Пытается залогиниться в MT5. Успех → JWT.
    MT5 должен быть уже инициализирован (mt5.initialize() вызывается при старте).
    """
    import MetaTrader5 as mt5

    ok = mt5.login(login=req.login, password=req.password, server=req.server)
    if not ok:
        err = mt5.last_error()
        logger.warning(f"MT5 login failed for #{req.login}@{req.server}: {err}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"MT5 login failed: {err[1] if err else 'unknown error'}",
        )

    token = _create_token(req.login, req.server)
    logger.info(f"Authenticated #{req.login}@{req.server}")
    return TokenResponse(token=token, expires_in=settings.jwt_expire_hours * 3600)
