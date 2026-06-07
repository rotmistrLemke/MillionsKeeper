from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, Optional
from enum import Enum


class EventType(str, Enum):
    # MarketDataAgent
    MARKET_CACHE_INVALIDATED = "market.cache_invalidated"
    NEW_BAR                  = "market.new_bar"
    MT5_CONNECTED            = "market.mt5_connected"
    MT5_DISCONNECTED         = "market.mt5_disconnected"

    # IndicatorAgent
    INDICATORS_READY         = "indicator.ready"

    # SignalAgent
    SIGNAL_GENERATED         = "signal.generated"

    # RiskAgent
    VOLUME_CALCULATED        = "risk.volume_calculated"

    # ExecutionAgent
    ORDER_OPEN_REQUEST       = "execution.open_request"
    ORDER_OPENED             = "execution.order_opened"
    ORDER_CLOSE_REQUEST      = "execution.close_request"
    ORDER_CLOSED             = "execution.order_closed"
    ORDER_ERROR              = "execution.error"

    # PositionMonitorAgent
    POSITION_UPDATE          = "position.update"
    RSI_EXIT_TRIGGERED       = "position.rsi_exit_triggered"

    # HistoryAgent
    HISTORY_SNAPSHOT         = "history.snapshot"

    # TelegramAgent
    TELEGRAM_SENT            = "telegram.sent"

    # BacktestAgent
    BACKTEST_STARTED         = "backtest.started"
    BACKTEST_RESULT          = "backtest.result"

    # AnomalyScannerAgent
    ANOMALY_OPENED           = "anomaly.opened"
    ANOMALY_UPDATED          = "anomaly.updated"
    ANOMALY_CLOSED           = "anomaly.closed"

    # System
    AGENT_STATUS             = "agent.status"
    AGENT_STALE              = "agent.stale"
    TRADING_STATUS_CHANGED   = "trading.status_changed"
    ACCOUNT_UPDATE           = "account.update"


@dataclass
class Event:
    type: EventType
    source: str
    timestamp: datetime = field(default_factory=datetime.now)
    payload: Dict[str, Any] = field(default_factory=dict)
    correlation_id: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "type": self.type,
            "source": self.source,
            "timestamp": self.timestamp.isoformat(),
            "payload": self.payload,
            "correlation_id": self.correlation_id,
        }
