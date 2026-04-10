"""
trading/broker.py — Абстракция над MetaTrader5 API.

Изолирует прямые mt5.* вызовы в одном месте.
Агенты работают через интерфейс IBroker, а не напрямую с mt5.

Usage:
    from app.trading.broker import MT5Broker
    broker = MT5Broker()
    result = await broker.open_order("XAUUSDrfd", "BUY", 0.1, sl=1900.0, tp=1950.0)
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional
import MetaTrader5 as mt5


@dataclass
class OrderResult:
    success: bool
    ticket: int
    price: float
    symbol: str
    order_type: str
    error: Optional[str] = None


@dataclass
class Position:
    ticket: int
    symbol: str
    order_type: str  # "BUY" | "SELL"
    volume: float
    open_price: float
    sl: float
    tp: float
    profit: float
    open_time: int


@dataclass
class AccountInfo:
    balance: float
    equity: float
    margin: float
    margin_free: float
    currency: str


class IBroker(ABC):
    @abstractmethod
    def open_order(
        self,
        symbol: str,
        order_type: str,
        volume: float,
        sl: float = 0.0,
        tp: float = 0.0,
        comment: str = "",
    ) -> OrderResult: ...

    @abstractmethod
    def close_order(self, ticket: int, symbol: str) -> bool: ...

    @abstractmethod
    def get_positions(self) -> list[Position]: ...

    @abstractmethod
    def get_account_info(self) -> Optional[AccountInfo]: ...


class MT5Broker(IBroker):
    """Реальная реализация через MetaTrader5 Python API."""

    _DEVIATION = 20
    _ORDER_TYPE_MAP = {
        "BUY": mt5.ORDER_TYPE_BUY,
        "SELL": mt5.ORDER_TYPE_SELL,
    }

    def open_order(
        self,
        symbol: str,
        order_type: str,
        volume: float,
        sl: float = 0.0,
        tp: float = 0.0,
        comment: str = "",
    ) -> OrderResult:
        tick = mt5.symbol_info_tick(symbol)
        if tick is None:
            return OrderResult(success=False, ticket=0, price=0.0, symbol=symbol,
                               order_type=order_type, error="No tick data")

        price = tick.ask if order_type == "BUY" else tick.bid
        mt5_type = self._ORDER_TYPE_MAP.get(order_type)
        if mt5_type is None:
            return OrderResult(success=False, ticket=0, price=0.0, symbol=symbol,
                               order_type=order_type, error=f"Unknown order type: {order_type}")

        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": symbol,
            "volume": volume,
            "type": mt5_type,
            "price": price,
            "sl": sl,
            "tp": tp,
            "deviation": self._DEVIATION,
            "comment": comment,
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_FOK,
        }

        result = mt5.order_send(request)
        if result is None or result.retcode != mt5.TRADE_RETCODE_DONE:
            error = str(mt5.last_error()) if result is None else f"retcode={result.retcode}"
            return OrderResult(success=False, ticket=0, price=price, symbol=symbol,
                               order_type=order_type, error=error)

        return OrderResult(success=True, ticket=result.order, price=result.price,
                           symbol=symbol, order_type=order_type)

    def close_order(self, ticket: int, symbol: str) -> bool:
        result = mt5.Close(symbol=symbol, ticket=ticket)
        if not result:
            _ = mt5.last_error()
        return bool(result)

    def get_positions(self) -> list[Position]:
        raw = mt5.positions_get()
        if raw is None:
            return []
        return [
            Position(
                ticket=p.ticket,
                symbol=p.symbol,
                order_type="BUY" if p.type == mt5.ORDER_TYPE_BUY else "SELL",
                volume=p.volume,
                open_price=p.price_open,
                sl=p.sl,
                tp=p.tp,
                profit=p.profit,
                open_time=p.time,
            )
            for p in raw
        ]

    def get_account_info(self) -> Optional[AccountInfo]:
        info = mt5.account_info()
        if info is None:
            return None
        return AccountInfo(
            balance=info.balance,
            equity=info.equity,
            margin=info.margin,
            margin_free=info.margin_free,
            currency=info.currency,
        )
