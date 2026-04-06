import json
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional

from core.agent_registry import registry
from core.event_bus import bus
from core.events import Event, EventType

router = APIRouter(prefix="/api")


# ──────────────────────────── Agents ──────────────────────────────

@router.get("/agents")
async def get_agents():
    return {"agents": registry.get_all_statuses()}


# ──────────────────────────── Account ─────────────────────────────

@router.get("/account")
async def get_account():
    try:
        from market_data_cache import cache
        info = cache.get_account_info()
        if info is None:
            return {"error": "MT5 не подключён"}
        return {
            "balance": round(info.balance, 2),
            "equity": round(info.equity, 2),
            "margin": round(info.margin, 2),
            "free_margin": round(info.margin_free, 2),
            "currency": info.currency,
        }
    except Exception as e:
        return {"error": str(e)}


# ──────────────────────────── Positions ───────────────────────────

@router.get("/positions")
async def get_positions():
    try:
        import MetaTrader5 as mt5
        positions = mt5.positions_get()
        if positions is None:
            return {"positions": []}
        result = []
        for p in positions:
            result.append({
                "ticket": p.ticket,
                "symbol": p.symbol,
                "type": "BUY" if p.type == mt5.ORDER_TYPE_BUY else "SELL",
                "volume": p.volume,
                "open_price": p.price_open,
                "sl": p.sl,
                "pnl": round(p.profit, 2),
                "open_time": int(p.time),
            })
        return {"positions": result}
    except Exception as e:
        return {"error": str(e)}


# ──────────────────────────── History ─────────────────────────────

@router.get("/history")
async def get_history(days: int = 1):
    try:
        from history import History
        h = History()
        if days == 1:
            data = h.get_profit_today()
        elif days == 7:
            data = h.get_profit_this_week()
        elif days == 30:
            data = h.get_profit_this_month()
        else:
            data = h.get_profit_last_days(days)
        return {"history": data if isinstance(data, dict) else {"profit": data}}
    except Exception as e:
        return {"error": str(e)}


# ──────────────────────────── Events ──────────────────────────────

@router.get("/events")
async def get_events(event_type: Optional[str] = None, limit: int = 50):
    events = bus.get_recent_events(event_type=event_type, limit=limit)
    return {"events": [e.to_dict() for e in events]}


# ──────────────────────────── Trading control ─────────────────────

class TradingStatusRequest(BaseModel):
    symbol: str
    status: int  # 0=разрешена, 3=выключена


@router.post("/trading/status")
async def set_trading_status(req: TradingStatusRequest):
    from settings import Dictionary
    if req.symbol not in Dictionary.symbolTradingStatus:
        raise HTTPException(status_code=404, detail=f"Символ {req.symbol} не найден")
    Dictionary.symbolTradingStatus[req.symbol] = req.status
    await bus.publish(Event(
        type=EventType.TRADING_STATUS_CHANGED,
        source="api",
        payload={"symbol": req.symbol, "status": req.status, "reason": "api_request"}
    ))
    return {"ok": True, "symbol": req.symbol, "status": req.status}


@router.get("/trading/status")
async def get_trading_status():
    from settings import Dictionary
    return {"status": Dictionary.symbolTradingStatus}


# ──────────────────────────── Backtest ────────────────────────────

class BacktestRequest(BaseModel):
    symbol: str
    bars: int = 2000
    deposit: float = 0.0
    spread: int = 0
    risk: float = 80.0
    volume: float = 0.0


@router.post("/backtest")
async def run_backtest(req: BacktestRequest):
    await bus.publish(Event(
        type=EventType.BACKTEST_STARTED,
        source="api",
        payload={
            "symbol": req.symbol,
            "bars": req.bars,
            "deposit": req.deposit,
            "spread": req.spread,
            "risk": req.risk,
            "volume": req.volume,
        }
    ))
    return {"ok": True, "message": f"Бэктест {req.symbol} запущен"}


# ──────────────────────────── Close position ──────────────────────

class ClosePositionRequest(BaseModel):
    ticket: int
    symbol: str


@router.post("/position/close")
async def close_position(req: ClosePositionRequest):
    await bus.publish(Event(
        type=EventType.ORDER_CLOSE_REQUEST,
        source="api",
        payload={"ticket": req.ticket, "symbol": req.symbol, "reason": "manual_api"}
    ))
    return {"ok": True, "ticket": req.ticket}
