"""
core/events.py — Типы событий и структура Event для EventBus.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Optional


class EventType(str, Enum):
    # MT5 connection
    MT5_CONNECTED       = "mt5_connected"
    MT5_DISCONNECTED    = "mt5_disconnected"

    # Market data
    NEW_BAR             = "new_bar"
    INDICATORS_READY    = "indicators_ready"

    # Signals & orders
    SIGNAL_GENERATED        = "signal_generated"
    ORDER_OPENED            = "order_opened"
    ORDER_CLOSED            = "order_closed"
    ORDER_CLOSE_REQUEST     = "order_close_request"
    ORDER_ERROR             = "order_error"
    RSI_EXIT_TRIGGERED      = "rsi_exit_triggered"

    # Position / account
    POSITION_UPDATE         = "position_update"
    ACCOUNT_UPDATE          = "account_update"
    HISTORY_SNAPSHOT        = "history_snapshot"

    # Backtest
    BACKTEST_STARTED        = "backtest_started"
    BACKTEST_RESULT         = "backtest_result"

    # Trading status
    TRADING_STATUS_CHANGED  = "trading_status_changed"

    # Agents
    AGENT_STATUS            = "agent_status"


@dataclass
class Event:
    type: EventType
    source: str
    payload: dict[str, Any] = field(default_factory=dict)
    correlation_id: Optional[str] = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: datetime = field(default_factory=datetime.utcnow)
