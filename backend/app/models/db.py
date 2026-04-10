"""
models/db.py — SQLAlchemy 2.0 ORM модели (async).

Таблицы:
  - trades          — история закрытых сделок
  - backtest_runs   — результаты бэктестов
  - strategy_configs — конфигурации стратегий
  - agent_events    — лог важных событий шины

Использование:
    from app.models.db import Trade, BacktestRun, StrategyConfig, AgentEvent
"""
from datetime import datetime
from typing import Any, Optional

from sqlalchemy import (
    BigInteger, Boolean, DateTime, Float, Index,
    Integer, JSON, String, Text, func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Trade(Base):
    """Закрытая сделка, записывается HistoryAgent."""

    __tablename__ = "trades"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    ticket: Mapped[int] = mapped_column(BigInteger, unique=True, nullable=False, index=True)
    symbol: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    order_type: Mapped[str] = mapped_column(String(4), nullable=False)  # BUY | SELL
    volume: Mapped[float] = mapped_column(Float, nullable=False)
    open_price: Mapped[float] = mapped_column(Float, nullable=False)
    close_price: Mapped[float] = mapped_column(Float, nullable=False)
    sl: Mapped[float] = mapped_column(Float, default=0.0)
    tp: Mapped[float] = mapped_column(Float, default=0.0)
    profit: Mapped[float] = mapped_column(Float, nullable=False)
    swap: Mapped[float] = mapped_column(Float, default=0.0)
    commission: Mapped[float] = mapped_column(Float, default=0.0)
    strategy: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    comment: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)
    open_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    close_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        Index("ix_trades_symbol_close_time", "symbol", "close_time"),
    )

    def net_profit(self) -> float:
        return self.profit + self.swap + self.commission


class BacktestRun(Base):
    """Результат запуска бэктеста, записывается BacktestAgent."""

    __tablename__ = "backtest_runs"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    strategy: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    symbol: Mapped[str] = mapped_column(String(32), nullable=False)
    timeframe: Mapped[str] = mapped_column(String(8), nullable=False)  # M1, H1, ...
    bars: Mapped[int] = mapped_column(Integer, nullable=False)
    deposit: Mapped[float] = mapped_column(Float, nullable=False)
    spread: Mapped[int] = mapped_column(Integer, default=0)
    risk_percent: Mapped[float] = mapped_column(Float, default=1.0)

    # Метрики
    total_trades: Mapped[int] = mapped_column(Integer, default=0)
    win_rate: Mapped[float] = mapped_column(Float, default=0.0)
    profit_factor: Mapped[float] = mapped_column(Float, default=0.0)
    sharpe_ratio: Mapped[float] = mapped_column(Float, default=0.0)
    max_drawdown: Mapped[float] = mapped_column(Float, default=0.0)
    total_profit: Mapped[float] = mapped_column(Float, default=0.0)

    # Детальные данные в JSON
    equity_curve: Mapped[Optional[Any]] = mapped_column(JSON, nullable=True)
    trades_json: Mapped[Optional[Any]] = mapped_column(JSON, nullable=True)

    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    finished_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class StrategyConfig(Base):
    """Конфигурация стратегии — параметры и флаг включения."""

    __tablename__ = "strategy_configs"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    params: Mapped[Optional[Any]] = mapped_column(JSON, nullable=True)  # dict с параметрами
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class AgentEvent(Base):
    """Лог важных событий EventBus (не всё — только error + ключевые)."""

    __tablename__ = "agent_events"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    source: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[Optional[Any]] = mapped_column(JSON, nullable=True)
    ts: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )

    __table_args__ = (
        Index("ix_agent_events_type_ts", "event_type", "ts"),
    )
