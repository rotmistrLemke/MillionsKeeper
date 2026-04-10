"""
strategies/base.py — Базовый класс всех торговых стратегий.

Контракт:
  - compute_indicators(df) → df с добавленными колонками
  - get_entry_signal(row) → "BUY" | "SELL" | None
  - get_exit_signal(row, position) → bool
  - get_sl_tp(row, signal, point) → (sl, tp)
  - is_flat(row) → bool  (встроенный флэт-детектор)
"""
from __future__ import annotations

import math
from abc import ABC, abstractmethod
from typing import Optional, Tuple

import pandas as pd


class BaseStrategy(ABC):
    name: str = ""
    description: str = ""
    default_timeframe: str = "M1"

    # Параметры флэт-детектора
    adx_period: int = 14
    adx_flat_threshold: float = 20.0   # ADX < 20 → флэт
    bb_period: int = 20
    bb_flat_ratio: float = 0.002       # BB_width/close < 0.2% → флэт

    # ── Абстрактный контракт ─────────────────────────────────────────

    @abstractmethod
    def compute_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """Добавляет колонки индикаторов в DataFrame и возвращает его."""

    @abstractmethod
    def get_entry_signal(self, row) -> Optional[str]:
        """Возвращает "BUY", "SELL" или None."""

    @abstractmethod
    def get_exit_signal(self, row, position: dict) -> bool:
        """True → закрыть позицию."""

    @abstractmethod
    def get_sl_tp(self, row, signal: str, point: float) -> Tuple[float, float]:
        """Возвращает (stop_loss, take_profit) в ценовых единицах."""

    def indicator_columns(self) -> list[str]:
        """Список колонок, добавляемых compute_indicators (для тестов)."""
        return []

    # ── Флэт-детектор (базовая реализация) ──────────────────────────

    def is_flat(self, row) -> bool:
        """
        Возвращает True, если рынок во флэте.
        Использует ADX и/или ширину полос Боллинджера.
        Подклассы могут переопределить.
        """
        # ADX-based
        adx = row.get("adx") if hasattr(row, "get") else getattr(row, "adx", None)
        if adx is not None and not _isnan(adx):
            if adx < self.adx_flat_threshold:
                return True

        # BB-based (bb_upper, bb_lower, close)
        try:
            upper = row.get("bb_upper") if hasattr(row, "get") else getattr(row, "bb_upper", None)
            lower = row.get("bb_lower") if hasattr(row, "get") else getattr(row, "bb_lower", None)
            close = row.get("close")    if hasattr(row, "get") else getattr(row, "close", None)
            if upper is not None and lower is not None and close and not _isnan(upper):
                width_ratio = (upper - lower) / close
                if width_ratio < self.bb_flat_ratio:
                    return True
        except Exception:
            pass

        return False


def _isnan(v) -> bool:
    try:
        return math.isnan(float(v))
    except (TypeError, ValueError):
        return True
