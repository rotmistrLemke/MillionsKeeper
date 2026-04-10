"""
models/schemas.py — Pydantic v2 схемы для API запросов/ответов и DB моделей.

Синхронизированы с TypeScript интерфейсами во frontend/src/types/.
"""
from datetime import datetime
from typing import Any, Optional
from pydantic import BaseModel, Field


# ── Agent ──────────────────────────────────────────────────────────

class AgentStatus(BaseModel):
    name: str
    status: str  # idle | running | error | stopped
    last_run: Optional[datetime] = None
    error_count: int = 0
    metrics: dict[str, Any] = {}


# ── Account ────────────────────────────────────────────────────────

class AccountInfoSchema(BaseModel):
    balance: float
    equity: float
    margin: float
    free_margin: float
    margin_level: float = 0.0
    currency: str
    login: int = 0
    server: str = ""


# ── Position ───────────────────────────────────────────────────────

class PositionSchema(BaseModel):
    ticket: int
    symbol: str
    type: str  # BUY | SELL
    volume: float
    open_price: float
    sl: float
    tp: float
    pnl: float
    open_time: int


# ── Backtest ───────────────────────────────────────────────────────

class BacktestRequest(BaseModel):
    strategy: str
    symbol: str
    bars: int = Field(2000, ge=100, le=50000)
    deposit: float = Field(10000.0, gt=0)
    spread: int = Field(0, ge=0)
    risk: float = Field(1.0, ge=0.1, le=100.0, description="Risk per trade, %")
    volume: float = Field(0.0, ge=0.0, description="Fixed volume, 0 = auto from risk")
    timeframe: Optional[str] = None
    start: Optional[str] = None
    end: Optional[str] = None


class BacktestMetrics(BaseModel):
    total_trades: int
    win_rate: float
    profit_factor: float
    sharpe_ratio: float
    max_drawdown: float
    max_drawdown_money: float = 0.0
    total_profit: float
    total_profit_points: float = 0.0
    avg_profit_per_trade: float
    final_balance: float = 0.0
    return_pct: float = 0.0
    max_consecutive_losses: int = 0


class BacktestResult(BaseModel):
    id: Optional[int] = None
    strategy: str
    symbol: str
    timeframe: str = "H1"
    bars: int
    deposit: float = 10000.0
    metrics: BacktestMetrics
    equity_curve: list[float] = []
    started_at: datetime
    finished_at: datetime


# ── Trading control ────────────────────────────────────────────────

class TradingStatusRequest(BaseModel):
    symbol: str
    status: int = Field(description="0=enabled, 3=disabled")


class ClosePositionRequest(BaseModel):
    ticket: int
    symbol: str


# ── Strategy ───────────────────────────────────────────────────────

class StrategyInfo(BaseModel):
    name: str
    display_name: str = ""
    description: str
    enabled: bool
    default_timeframe: str
    params: dict[str, Any] = {}


class StrategyConfigUpdate(BaseModel):
    enabled: Optional[bool] = None
    params: Optional[dict[str, Any]] = None


# ── Event ─────────────────────────────────────────────────────────

class EventSchema(BaseModel):
    type: str
    source: str
    timestamp: datetime
    payload: dict[str, Any] = {}
    correlation_id: Optional[str] = None
