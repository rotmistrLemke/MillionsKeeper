from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

import auth
from anomaly.store import AnomalyStore

router = APIRouter(prefix="/api/anomalies", tags=["anomalies"])

# Auth dependency — mirrors the pattern from web/api_routes.py
_bearer = HTTPBearer(auto_error=False)


def _get_current_user(
    creds: Optional[HTTPAuthorizationCredentials] = Depends(_bearer),
) -> auth.UserRecord:
    if creds is None or not creds.credentials:
        raise HTTPException(status_code=401, detail="Требуется авторизация")
    user = auth.user_from_token(creds.credentials)
    if user is None:
        raise HTTPException(status_code=401, detail="Недействительный токен")
    return user


class AnomalyDeps:
    """Контейнер для агента/стора. Инициализируется в main.py."""
    store: Optional[AnomalyStore] = None
    agent = None  # AnomalyScannerAgent


deps = AnomalyDeps()


@router.get("/active")
def get_active(_user: auth.UserRecord = Depends(_get_current_user)):
    if deps.agent is None:
        return []
    out = []
    for symbol, rec in deps.agent.active.items():
        snap = rec["snapshot"]
        out.append({
            "symbol": symbol,
            "types": sorted(t.value for t in rec["types"]),
            "opened_at": rec["opened_at"],
            **(snap.to_dict() if snap else {}),
        })
    return out


@router.get("/history")
def get_history(
    limit: int = 100,
    offset: int = 0,
    symbol: Optional[str] = None,
    type: Optional[str] = None,
    from_: Optional[str] = None,
    to: Optional[str] = None,
    _user: auth.UserRecord = Depends(_get_current_user),
):
    if deps.store is None:
        raise HTTPException(503, "store not ready")
    return deps.store.list_history(
        limit=limit, offset=offset, symbol=symbol,
        type_=type, from_=from_, to=to,
    )


@router.post("/scan")
async def scan_now(_user: auth.UserRecord = Depends(_get_current_user)):
    if deps.agent is None:
        raise HTTPException(503, "agent not ready")
    await deps.agent.scan_once()
    return {"ok": True, "active": len(deps.agent.active)}
