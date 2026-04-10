"""
trading/risk.py — Расчёт объёма сделки и SL/TP.

Логика перенесена из backtest.py (calc_volume) и trading.py
(calculateSafeTradeWithMargin). Не зависит от MT5 напрямую —
MT5 вызовы передаются через IBroker.

Usage:
    calc = RiskCalculator(broker)
    volume = calc.position_volume(
        symbol="XAUUSDrfd",
        balance=10000.0,
        risk_pct=1.0,
        stop_loss_pips=200,
        order_type="BUY",
    )
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING

import MetaTrader5 as mt5

if TYPE_CHECKING:
    from app.trading.broker import IBroker

logger = logging.getLogger("RiskCalculator")


@dataclass
class SlTp:
    sl: float
    tp: float


class RiskCalculator:
    """Расчёт безопасного объёма позиции и SL/TP на основе ATR."""

    MARGIN_SAFETY = 1.1  # запас маржи 10%

    def __init__(self, broker: "IBroker"):
        self._broker = broker

    # ── Основной метод ─────────────────────────────────────────────

    def position_volume(
        self,
        symbol: str,
        balance: float,
        risk_pct: float,
        stop_loss_pips: float,
        order_type: str = "BUY",
        entry_price: float = 0.0,
        num_free_slots: int = 1,
    ) -> float:
        """
        Возвращает объём лота с учётом риска и доступной маржи.

        Args:
            symbol: торговый символ
            balance: текущий баланс счёта
            risk_pct: риск на сделку, % (напр. 1.0)
            stop_loss_pips: размер стоп-лосса в пипсах
            order_type: "BUY" или "SELL"
            entry_price: цена входа (0 = текущая)
            num_free_slots: сколько слотов ещё открыто
        """
        info = mt5.symbol_info(symbol)
        if info is None:
            logger.warning(f"No symbol info for {symbol}")
            return 0.0

        pip_value = self._pip_value_per_lot(symbol, info)
        if pip_value <= 0 or stop_loss_pips <= 0:
            return info.volume_min

        # Объём по риску
        risk_money = balance * (risk_pct / 100.0)
        volume_by_risk = risk_money / (pip_value * stop_loss_pips)

        # Ограничение по марже
        volume = volume_by_risk
        if entry_price > 0:
            mt5_type = mt5.ORDER_TYPE_BUY if order_type == "BUY" else mt5.ORDER_TYPE_SELL
            try:
                margin_per_lot = mt5.order_calc_margin(mt5_type, symbol, 1.0, entry_price)
                if margin_per_lot and margin_per_lot > 0:
                    available = (balance / max(num_free_slots, 1)) / self.MARGIN_SAFETY
                    volume = min(volume_by_risk, available / margin_per_lot)
            except Exception as e:
                logger.debug(f"Margin calc failed for {symbol}: {e}")

        return self._clamp_volume(volume, info)

    # ── SL / TP расчёт ─────────────────────────────────────────────

    def sl_tp_from_atr(
        self,
        symbol: str,
        order_type: str,
        entry_price: float,
        atr: float,
        sl_atr_mult: float = 2.0,
        tp_atr_mult: float = 4.0,
    ) -> SlTp:
        """
        Рассчитывает SL и TP как кратное ATR.
        BUY:  sl = entry - 2*ATR,  tp = entry + 4*ATR
        SELL: sl = entry + 2*ATR,  tp = entry - 4*ATR
        """
        if order_type == "BUY":
            return SlTp(
                sl=entry_price - sl_atr_mult * atr,
                tp=entry_price + tp_atr_mult * atr,
            )
        return SlTp(
            sl=entry_price + sl_atr_mult * atr,
            tp=entry_price - tp_atr_mult * atr,
        )

    def trailing_sl(
        self,
        symbol: str,
        current_profit_pips: float,
        current_sl: float,
        atr: float,
        order_type: str,
    ) -> float:
        """
        Трейлинг-стоп на основе ATR (логика из trading.py calculateStopLoss).
        Возвращает новый SL в пунктах счёта (не в пипсах).
        """
        info = mt5.symbol_info(symbol)
        if info is None:
            return current_sl

        atr_pips = atr / info.point
        if current_profit_pips > 2 * atr_pips:
            new_sl_pips = current_profit_pips - atr_pips
        elif current_profit_pips > atr_pips:
            new_sl_pips = 0.0
        else:
            new_sl_pips = current_profit_pips - 2 * atr_pips

        if order_type == "BUY":
            return max(current_sl, new_sl_pips * info.point)
        return min(current_sl, -new_sl_pips * info.point) if current_sl != 0.0 else new_sl_pips * info.point

    # ── Внутренние утилиты ─────────────────────────────────────────

    @staticmethod
    def _pip_value_per_lot(symbol: str, info) -> float:
        """Стоимость 1 пипса при объёме 1 лот в валюте счёта."""
        pip_value = info.point * info.trade_contract_size
        if info.currency_profit != info.currency_margin:
            # Конвертация через кросс-курс
            for conv_sym in (
                info.currency_profit + info.currency_margin + "rfd",
                info.currency_margin + info.currency_profit + "rfd",
            ):
                conv_info = mt5.symbol_info(conv_sym)
                if conv_info is not None:
                    tick = mt5.symbol_info_tick(conv_sym)
                    if tick:
                        rate = tick.ask if conv_sym.startswith(info.currency_profit) else 1.0 / tick.bid
                        pip_value *= rate
                        break
        return pip_value

    @staticmethod
    def _clamp_volume(volume: float, info) -> float:
        """Зажимает объём в допустимые границы и округляет до volume_step."""
        volume = max(info.volume_min, min(info.volume_max, volume))
        if info.volume_step > 0:
            volume = round(volume / info.volume_step) * info.volume_step
        return round(volume, 2)
