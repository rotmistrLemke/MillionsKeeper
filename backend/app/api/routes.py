"""
api/routes.py — FastAPI v2 роутер. Все эндпоинты приложения.

Архитектура:
  - /api/auth/*        — JWT аутентификация (без RequireAuth)
  - /api/account       — данные аккаунта (MT5 + Redis кэш)
  - /api/agents        — статус агентов
  - /api/positions     — открытые позиции
  - /api/positions/{ticket}/close — закрытие позиции
  - /api/events        — лог событий из PostgreSQL
  - /api/backtest/run  — запуск бэктеста
  - /api/backtest/results — история из PostgreSQL
  - /api/strategies    — список стратегий из PostgreSQL
  - /api/strategies/{name} — обновление конфига
  - /api/history       — история сделок из PostgreSQL
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

import MetaTrader5 as mt5
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import desc, select

from app.api.auth import LoginRequest, RequireAuth, TokenResponse, authenticate_mt5
from app.cache.market_cache import get_cache
from app.core.database import db_session
from app.models.db import AgentEvent, BacktestRun, StrategyConfig, Trade
from app.models.schemas import (
    AccountInfoSchema,
    BacktestRequest,
    PositionSchema,
    StrategyConfigUpdate,
)
from core.event_bus import bus
from core.events import Event, EventType

logger = logging.getLogger("API")

router = APIRouter(prefix="/api")


# ── Auth ──────────────────────────────────────────────────────────────────────

@router.post("/auth/login", response_model=TokenResponse, tags=["auth"])
async def login(req: LoginRequest) -> TokenResponse:
    return await authenticate_mt5(req)


# ── Account ───────────────────────────────────────────────────────────────────

@router.get("/account", tags=["trading"])
async def get_account(_: RequireAuth) -> dict:
    cache = get_cache()

    # Пробуем кэш
    cached = await cache.get_account()
    if cached:
        return cached

    # Читаем из MT5
    info = mt5.account_info()
    if info is None:
        raise HTTPException(status_code=503, detail="MT5 не подключён")

    result = {
        "balance":      round(info.balance, 2),
        "equity":       round(info.equity, 2),
        "margin":       round(info.margin, 2),
        "free_margin":  round(info.margin_free, 2),
        "margin_level": round(info.margin_level, 2),
        "currency":     info.currency,
        "login":        info.login,
        "server":       info.server,
    }
    await cache.set_account(result)
    return result


# ── Agents ────────────────────────────────────────────────────────────────────

@router.get("/agents", tags=["system"])
async def get_agents(_: RequireAuth) -> list:
    try:
        from core.agent_registry import registry
        return registry.get_all_statuses()
    except Exception as e:
        logger.error(f"get_agents: {e}")
        return []


# ── Positions ─────────────────────────────────────────────────────────────────

@router.get("/positions", tags=["trading"])
async def get_positions(_: RequireAuth) -> list:
    cache = get_cache()

    cached = await cache.get_positions()
    if cached is not None:
        return cached

    positions = mt5.positions_get()
    if positions is None:
        return []

    result = [
        {
            "ticket":     p.ticket,
            "symbol":     p.symbol,
            "type":       "BUY" if p.type == mt5.ORDER_TYPE_BUY else "SELL",
            "volume":     p.volume,
            "open_price": p.price_open,
            "sl":         p.sl,
            "tp":         p.tp,
            "pnl":        round(p.profit, 2),
            "open_time":  int(p.time),
        }
        for p in positions
    ]
    await cache.set_positions(result)
    return result


@router.post("/positions/{ticket}/close", tags=["trading"])
async def close_position(ticket: int, _: RequireAuth) -> dict:
    positions = mt5.positions_get(ticket=ticket)
    if not positions:
        raise HTTPException(status_code=404, detail=f"Position {ticket} not found")

    pos = positions[0]
    await bus.publish(Event(
        type=EventType.ORDER_CLOSE_REQUEST,
        source="api",
        payload={"ticket": ticket, "symbol": pos.symbol, "reason": "manual_api"},
    ))
    return {"ok": True, "ticket": ticket}


# ── Events ────────────────────────────────────────────────────────────────────

@router.get("/events", tags=["system"])
async def get_events(
    _: RequireAuth,
    limit: int = Query(50, ge=1, le=500),
    event_type: Optional[str] = None,
) -> list:
    async with db_session() as session:
        q = select(AgentEvent).order_by(desc(AgentEvent.ts)).limit(limit)
        if event_type:
            q = q.where(AgentEvent.event_type == event_type)
        rows = (await session.execute(q)).scalars().all()
        return [
            {
                "id":         r.id,
                "agent_name": r.source,
                "event_type": r.event_type,
                "status":     "idle",
                "message":    str(r.payload.get("message", "")) if r.payload else "",
                "created_at": r.ts.isoformat(),
                "payload":    r.payload or {},
            }
            for r in rows
        ]


# ── Backtest ──────────────────────────────────────────────────────────────────

@router.post("/backtest/run", tags=["backtest"])
async def run_backtest(req: BacktestRequest, _: RequireAuth) -> dict:
    await bus.publish(Event(
        type=EventType.BACKTEST_STARTED,
        source="api",
        payload={
            "strategy":  req.strategy,
            "symbol":    req.symbol,
            "bars":      req.bars,
            "deposit":   req.deposit,
            "spread":    req.spread,
            "risk":      req.risk,
            "timeframe": req.timeframe or "H1",
        },
    ))
    return {"ok": True, "message": f"Бэктест {req.strategy}/{req.symbol} запущен"}


@router.get("/backtest/results", tags=["backtest"])
async def get_backtest_results(
    _: RequireAuth,
    limit: int = Query(20, ge=1, le=100),
    strategy: Optional[str] = None,
) -> list:
    async with db_session() as session:
        q = select(BacktestRun).order_by(desc(BacktestRun.started_at)).limit(limit)
        if strategy:
            q = q.where(BacktestRun.strategy == strategy)
        rows = (await session.execute(q)).scalars().all()
        return [_bt_row_to_dict(r) for r in rows]


@router.get("/backtest/results/{run_id}", tags=["backtest"])
async def get_backtest_result(run_id: int, _: RequireAuth) -> dict:
    async with db_session() as session:
        row = await session.get(BacktestRun, run_id)
        if row is None:
            raise HTTPException(status_code=404, detail="Backtest run not found")
        return _bt_row_to_dict(row)


def _bt_row_to_dict(r: BacktestRun) -> dict:
    return {
        "id":         r.id,
        "strategy":   r.strategy,
        "symbol":     r.symbol,
        "timeframe":  r.timeframe,
        "bars":       r.bars,
        "deposit":    r.deposit,
        "metrics": {
            "total_trades":           r.total_trades,
            "win_rate":               r.win_rate,
            "profit_factor":          r.profit_factor,
            "sharpe_ratio":           r.sharpe_ratio,
            "max_drawdown":           r.max_drawdown,
            "max_drawdown_money":     0.0,
            "total_profit":           r.total_profit,
            "total_profit_points":    0.0,
            "avg_profit_per_trade":   round(r.total_profit / r.total_trades, 2) if r.total_trades else 0.0,
            "final_balance":          round(r.deposit + r.total_profit, 2),
            "return_pct":             round(r.total_profit / r.deposit * 100, 2) if r.deposit else 0.0,
            "max_consecutive_losses": 0,
        },
        "equity_curve": r.equity_curve or [],
        "started_at":  r.started_at.isoformat(),
        "finished_at": r.finished_at.isoformat(),
    }


# ── Strategies ────────────────────────────────────────────────────────────────

@router.get("/strategies", tags=["strategies"])
async def get_strategies(_: RequireAuth) -> list:
    async with db_session() as session:
        rows = (await session.execute(select(StrategyConfig))).scalars().all()
        return [
            {
                "name":             r.name,
                "display_name":     r.name.replace("_", " ").title(),
                "description":      r.description or "",
                "enabled":          r.enabled,
                "default_timeframe": (r.params or {}).get("timeframe", "H1"),
                "params":           {k: v for k, v in (r.params or {}).items() if k != "timeframe"},
            }
            for r in rows
        ]


@router.put("/strategies/{name}", tags=["strategies"])
async def update_strategy(name: str, update: StrategyConfigUpdate, _: RequireAuth) -> dict:
    async with db_session() as session:
        row = (
            await session.execute(select(StrategyConfig).where(StrategyConfig.name == name))
        ).scalar_one_or_none()

        if row is None:
            raise HTTPException(status_code=404, detail=f"Strategy '{name}' not found")

        if update.enabled is not None:
            row.enabled = update.enabled
        if update.params is not None:
            existing = dict(row.params or {})
            existing.update(update.params)
            row.params = existing

        await session.flush()
        return {"ok": True, "name": name, "enabled": row.enabled}


# ── History ───────────────────────────────────────────────────────────────────

@router.get("/history", tags=["history"])
async def get_history(
    _: RequireAuth,
    symbol: Optional[str] = None,
    limit: int = Query(200, ge=1, le=1000),
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
) -> list:
    async with db_session() as session:
        q = select(Trade).order_by(desc(Trade.close_time)).limit(limit)
        if symbol:
            q = q.where(Trade.symbol == symbol)
        if from_date:
            q = q.where(Trade.close_time >= datetime.fromisoformat(from_date))
        if to_date:
            q = q.where(Trade.close_time <= datetime.fromisoformat(to_date))

        rows = (await session.execute(q)).scalars().all()
        return [
            {
                "id":          r.id,
                "ticket":      r.ticket,
                "symbol":      r.symbol,
                "type":        r.order_type,
                "volume":      r.volume,
                "open_price":  r.open_price,
                "close_price": r.close_price,
                "sl":          r.sl,
                "tp":          r.tp,
                "pnl":         round(r.net_profit(), 2),
                "pnl_points":  round((r.close_price - r.open_price) / 0.0001, 1)
                               if r.order_type == "BUY"
                               else round((r.open_price - r.close_price) / 0.0001, 1),
                "open_time":   r.open_time.isoformat(),
                "close_time":  r.close_time.isoformat(),
                "strategy":    r.strategy or "",
            }
            for r in rows
        ]
