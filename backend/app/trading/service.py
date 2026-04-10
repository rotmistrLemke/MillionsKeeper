"""
trading/service.py — TradingService: оркестратор торговых операций.

Инъецируется в агентов через __init__. Изолирует всю бизнес-логику
торговли от агентов и не допускает прямых mt5.* вызовов снаружи.

Usage:
    service = TradingService(broker=MT5Broker(), risk=RiskCalculator(broker))
    result = await service.open(symbol="XAUUSDrfd", signal="BUY", atr=5.0, balance=10000.0)
"""
from __future__ import annotations

import asyncio
import logging
from typing import Optional

import MetaTrader5 as mt5

from app.core.config import settings
from app.trading.broker import IBroker, OrderResult, Position
from app.trading.risk import RiskCalculator, SlTp

logger = logging.getLogger("TradingService")

# Символы, разрешённые к торговле: 0=разрешён, 3=выключен
# Заменяет settings.py Dictionary.symbolTradingStatus
_TRADING_STATUS: dict[str, int] = {
    "EURUSDrfd": 3, "NZDUSDrfd": 3, "EURGBPrfd": 3, "USDCHFrfd": 3,
    "USDJPYrfd": 3, "EURCHFrfd": 3, "GBPUSDrfd": 3, "USDCADrfd": 3,
    "EURJPYrfd": 3, "AUDCADrfd": 3, "AUDUSDrfd": 3, "AUDJPYrfd": 3,
    "AUDCHFrfd": 3, "CHFJPYrfd": 3, "EURAUDrfd": 3, "GBPCHFrfd": 3,
    "EURCADrfd": 3, "GBPCADrfd": 3, "XAUUSDrfd": 0, "GBPJPYrfd": 3,
    "XAGUSDrfd": 3, "USDSGDrfd": 3,
}


class TradingService:
    """Высокоуровневый торговый сервис. Используется агентами через DI."""

    def __init__(self, broker: IBroker, risk: RiskCalculator):
        self._broker = broker
        self._risk = risk

    # ── Статус торговли ────────────────────────────────────────────

    def get_status(self, symbol: str) -> int:
        return _TRADING_STATUS.get(symbol, 3)

    def set_status(self, symbol: str, status: int) -> None:
        if symbol in _TRADING_STATUS:
            _TRADING_STATUS[symbol] = status

    def get_all_statuses(self) -> dict[str, int]:
        return dict(_TRADING_STATUS)

    def active_symbols(self) -> list[str]:
        return [s for s, v in _TRADING_STATUS.items() if v != 3]

    # ── Торговые операции ──────────────────────────────────────────

    async def open(
        self,
        symbol: str,
        signal: str,
        atr: float,
        balance: float,
        comment: str = "",
    ) -> Optional[OrderResult]:
        """
        Открывает позицию по сигналу.
        Рассчитывает объём и SL/TP через RiskCalculator.
        """
        if self.get_status(symbol) != 0:
            logger.debug(f"Trading disabled for {symbol}")
            return None

        positions = await self._get_positions()
        active = self.active_symbols()
        if len(positions) >= len(active):
            logger.debug(f"All slots filled ({len(positions)}/{len(active)})")
            return None

        if any(p.symbol == symbol for p in positions):
            logger.debug(f"Already have position on {symbol}")
            return None

        tick = await asyncio.get_event_loop().run_in_executor(
            None, mt5.symbol_info_tick, symbol
        )
        entry = tick.ask if signal == "BUY" else tick.bid if tick else 0.0

        stop_loss_pips = (2 * atr / mt5.symbol_info(symbol).point) if atr > 0 else 100
        volume = self._risk.position_volume(
            symbol=symbol,
            balance=balance,
            risk_pct=settings.default_risk_percent,
            stop_loss_pips=stop_loss_pips,
            order_type=signal,
            entry_price=entry,
            num_free_slots=max(len(active) - len(positions), 1),
        )

        if volume <= 0:
            logger.warning(f"Calculated volume=0 for {symbol}, skipping")
            return None

        sl_tp: SlTp = self._risk.sl_tp_from_atr(symbol, signal, entry, atr)

        result = await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: self._broker.open_order(
                symbol=symbol,
                order_type=signal,
                volume=volume,
                sl=sl_tp.sl,
                tp=sl_tp.tp,
                comment=comment,
            ),
        )

        if result.success:
            self.set_status(symbol, 1)  # позиция открыта
            logger.info(f"Opened {signal} {symbol} vol={volume} ticket={result.ticket}")
        else:
            logger.error(f"Open order failed {symbol}: {result.error}")

        return result

    async def close(self, ticket: int, symbol: str) -> bool:
        """Закрывает позицию по тикету."""
        ok = await asyncio.get_event_loop().run_in_executor(
            None, self._broker.close_order, ticket, symbol
        )
        if ok:
            self.set_status(symbol, 0)
            logger.info(f"Closed position {ticket} {symbol}")
        return ok

    async def get_positions(self) -> list[Position]:
        return await self._get_positions()

    async def get_account_balance(self) -> float:
        info = await asyncio.get_event_loop().run_in_executor(
            None, self._broker.get_account_info
        )
        return info.balance if info else 0.0

    # ── Внутренние ─────────────────────────────────────────────────

    async def _get_positions(self) -> list[Position]:
        return await asyncio.get_event_loop().run_in_executor(
            None, self._broker.get_positions
        )
