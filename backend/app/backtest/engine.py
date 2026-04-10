"""
backtest/engine.py — Движок бэктеста.

Декомпозиция backtest.py (31KB). Поддерживает любую BaseStrategy-совместимую стратегию.
Не зависит от MT5 (данные передаются как DataFrame или загружаются отдельно).

Usage:
    engine = BacktestEngine()
    result = engine.run(
        strategy=BollingerScalpStrategy(),
        symbol="XAUUSDrfd",
        bars=2000,
        deposit=10000.0,
    )
    print(result.metrics_dict())
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Optional

import MetaTrader5 as mt5
import numpy as np
import pandas as pd

from app.backtest.metrics import BacktestResult

logger = logging.getLogger("BacktestEngine")

_TF_MAP: dict[str, int] = {
    "M1":  mt5.TIMEFRAME_M1,
    "M5":  mt5.TIMEFRAME_M5,
    "M15": mt5.TIMEFRAME_M15,
    "H1":  mt5.TIMEFRAME_H1,
    "H4":  mt5.TIMEFRAME_H4,
    "D1":  mt5.TIMEFRAME_D1,
}

WARMUP_BARS = 60   # минимальное кол-во баров для прогрева индикаторов


class BacktestEngine:
    """Универсальный движок бэктеста для любой BaseStrategy."""

    def run(
        self,
        strategy,
        symbol: str,
        bars: int = 2000,
        deposit: float = 10000.0,
        spread_points: int = 0,
        risk_pct: float = 1.0,
        timeframe_str: str = "H1",
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
        df: Optional[pd.DataFrame] = None,
    ) -> Optional[BacktestResult]:
        """
        Запускает бэктест стратегии.

        Args:
            strategy: экземпляр BaseStrategy (с compute_indicators, get_entry_signal, get_exit_signal, get_sl_tp)
            symbol: торговый символ
            bars: кол-во баров (игнорируется если df передан)
            deposit: начальный депозит
            spread_points: спред в пунктах
            risk_pct: риск на сделку, %
            timeframe_str: "M1", "H1", etc.
            date_from/date_to: диапазон дат (опционально)
            df: готовый DataFrame (если None — загружается из MT5)
        """
        if df is None:
            df = self._load(symbol, timeframe_str, bars, date_from, date_to)

        if df is None or len(df) < WARMUP_BARS + 10:
            logger.warning(f"Insufficient data for {symbol}: {len(df) if df is not None else 0} bars")
            return None

        # Вычисляем индикаторы стратегии + flat-detector
        df = strategy.compute_indicators(df)
        if hasattr(strategy, "compute_flat_indicators"):
            df = strategy.compute_flat_indicators(df)

        symbol_info = mt5.symbol_info(symbol)
        point = symbol_info.point if symbol_info else 0.0001

        result = BacktestResult(initial_deposit=deposit)
        position: Optional[dict] = None
        balance  = deposit
        trade_status = 0

        for i in range(WARMUP_BARS, len(df)):
            row = df.iloc[i]

            # Пропускаем выходные и пятницу вечером
            if self._is_weekend_block(row):
                if position is not None:
                    pnl = self._calc_pnl(position, row, point, spread_points)
                    balance += pnl["pnl_money"]
                    result.trades.append({**pnl, "close_reason": "WEEKEND", "balance": round(balance, 2)})
                    result.equity_curve.append(round(balance - deposit, 2))
                    position = None
                    trade_status = 0
                else:
                    result.equity_curve.append(round(balance - deposit, 2))
                continue

            # Управление открытой позицией
            if position is not None:
                pnl_now = self._calc_pnl(position, row, point, spread_points)

                # SL / TP хит
                if self._sl_tp_hit(position, row):
                    balance += pnl_now["pnl_money"]
                    result.trades.append({**pnl_now, "close_reason": "SL/TP", "balance": round(balance, 2)})
                    result.equity_curve.append(round(balance - deposit, 2))
                    position = None
                    trade_status = 0
                    continue

                # Сигнал выхода от стратегии
                if strategy.get_exit_signal(row, position):
                    balance += pnl_now["pnl_money"]
                    result.trades.append({**pnl_now, "close_reason": "SIGNAL", "balance": round(balance, 2)})
                    result.equity_curve.append(round(balance - deposit, 2))
                    position = None
                    trade_status = 0
                    continue

                result.equity_curve.append(round(balance - deposit, 2))
                continue

            # Поиск сигнала входа
            if trade_status != 0:
                result.equity_curve.append(round(balance - deposit, 2))
                continue

            signal = strategy.get_entry_signal(row)
            if signal not in ("BUY", "SELL"):
                result.equity_curve.append(round(balance - deposit, 2))
                continue

            sl, tp = strategy.get_sl_tp(row, signal, point)
            volume = self._calc_volume(balance, risk_pct, sl, row["close"], point, symbol_info, signal)

            position = {
                "type":        signal,
                "entry_price": row["close"],
                "entry_bar":   i,
                "sl":          sl,
                "tp":          tp,
                "volume":      volume,
                "entry_time":  row.get("time"),
            }
            trade_status = 1
            result.equity_curve.append(round(balance - deposit, 2))

        return result

    # ── Вспомогательные ───────────────────────────────────────────

    @staticmethod
    def _load(symbol: str, tf_str: str, bars: int, date_from, date_to) -> Optional[pd.DataFrame]:
        tf = _TF_MAP.get(tf_str, mt5.TIMEFRAME_H1)
        if date_from and date_to:
            rates = mt5.copy_rates_range(symbol, tf, date_from, date_to)
        elif date_from:
            rates = mt5.copy_rates_from(symbol, tf, date_from, bars)
        else:
            rates = mt5.copy_rates_from_pos(symbol, tf, 0, bars)

        if rates is None or len(rates) == 0:
            return None

        df = pd.DataFrame(rates)
        df["time"] = pd.to_datetime(df["time"], unit="s")
        return df

    @staticmethod
    def _is_weekend_block(row) -> bool:
        t = row.get("time")
        if t is None:
            return False
        if not isinstance(t, pd.Timestamp):
            t = pd.Timestamp(t)
        wd, h = t.weekday(), t.hour
        return (wd == 4 and h >= 23) or wd in (5, 6) or (wd == 0 and h < 2)

    @staticmethod
    def _calc_pnl(position: dict, row, point: float, spread: int) -> dict:
        ep = position["entry_price"]
        cp = row["close"]
        vol = position.get("volume", 0.01)

        if position["type"] == "BUY":
            pnl_pts = (cp - ep) / point - spread
        else:
            pnl_pts = (ep - cp) / point - spread

        pnl_money = pnl_pts * point * 100_000 * vol  # упрощённо для Forex
        return {
            "type":        position["type"],
            "entry_price": ep,
            "close_price": cp,
            "pnl_points":  round(pnl_pts, 1),
            "pnl_money":   round(pnl_money, 2),
            "volume":      vol,
        }

    @staticmethod
    def _sl_tp_hit(position: dict, row) -> bool:
        close = row["close"]
        sl, tp = position.get("sl"), position.get("tp")
        if position["type"] == "BUY":
            return (sl and close <= sl) or (tp and close >= tp)
        return (sl and close >= sl) or (tp and close <= tp)

    @staticmethod
    def _calc_volume(balance: float, risk_pct: float, sl: float, entry: float, point: float, info, signal: str) -> float:
        if info is None or sl == 0:
            return 0.01
        sl_pips = abs(entry - sl) / point
        if sl_pips <= 0:
            return info.volume_min if info else 0.01
        risk_money = balance * risk_pct / 100
        pip_value  = point * (info.trade_contract_size if info else 100_000)
        volume = risk_money / (sl_pips * pip_value)
        if info:
            volume = max(info.volume_min, min(info.volume_max, volume))
            if info.volume_step > 0:
                volume = round(volume / info.volume_step) * info.volume_step
        return round(volume, 2)
