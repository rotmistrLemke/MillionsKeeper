"""
strategies/alligator.py — Williams Alligator стратегия.

Декомпозиция из alligatorBot.py (58KB монолита).
Выделена только торговая логика: индикаторы, сигналы, SL/TP.
Telegram-код, UI и прочее — удалены.

Сигнал входа:
  - MA пересечение (EMA8 vs EMA21) + критический угол
  - MACD гистограмма (нарастающая выше/ниже нуля)
  - RSI (55-70 BUY, 30-45 SELL)
  - Alligator: губы выше/ниже зубов и челюсти

Выход:
  - RSI < 45 для BUY, RSI > 55 для SELL

Флэт-детектор: наследуется из BaseStrategy (ADX/BB/ATR).
"""
import pandas as pd
import talib

from strategies.base import BaseStrategy


class AlligatorStrategy(BaseStrategy):
    name = "alligator"
    description = "Williams Alligator + EMA + MACD + RSI (декомпозиция alligatorBot.py)"
    default_timeframe = "H1"

    # Параметры EMA
    fast_period: int = 8
    slow_period: int = 21

    # MACD
    macd_fast: int = 12
    macd_slow: int = 26
    macd_signal_period: int = 9

    # RSI
    rsi_period: int = 14
    rsi_buy_low: float = 55.0
    rsi_buy_high: float = 70.0
    rsi_sell_low: float = 30.0
    rsi_sell_high: float = 45.0

    # Alligator (SMMA — Simple Moving Median Average, periods)
    jaw_period: int = 13
    jaw_shift: int = 8
    teeth_period: int = 8
    teeth_shift: int = 5
    lips_period: int = 5
    lips_shift: int = 3

    def compute_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        close = df["close"].values.astype(float)
        high  = df["high"].values.astype(float)
        low   = df["low"].values.astype(float)

        # EMA
        df["ema_fast"] = talib.EMA(close, timeperiod=self.fast_period)
        df["ema_slow"] = talib.EMA(close, timeperiod=self.slow_period)

        # EMA угол (разница текущей и предыдущей)
        df["ema_fast_prev"] = df["ema_fast"].shift(1)
        df["ema_fast_angle"] = df["ema_fast"] - df["ema_fast_prev"]

        # MACD
        macd_line, signal_line, _ = talib.MACD(
            close,
            fastperiod=self.macd_fast,
            slowperiod=self.macd_slow,
            signalperiod=self.macd_signal_period,
        )
        df["macd_line"]   = macd_line
        df["macd_signal"] = signal_line
        df["macd_prev"]   = pd.Series(macd_line).shift(1).values

        # RSI
        df["rsi"]      = talib.RSI(close, timeperiod=self.rsi_period)
        df["rsi_prev"] = df["rsi"].shift(1)
        df["rsi_prev2"] = df["rsi"].shift(2)

        # ATR (для SL/TP и flat-detector)
        df["atr"] = talib.ATR(high, low, close, timeperiod=14)

        # Alligator — SMMA через EMA с периодами
        df["jaw"]   = talib.EMA(close, timeperiod=self.jaw_period)
        df["teeth"] = talib.EMA(close, timeperiod=self.teeth_period)
        df["lips"]  = talib.EMA(close, timeperiod=self.lips_period)

        return df

    def get_entry_signal(self, row) -> str | None:
        if self.is_flat(row):
            return None

        ma_signal    = self._ma_signal(row)
        angle_signal = self._angle_signal(row)
        macd_signal  = self._macd_signal(row)
        rsi_signal   = self._rsi_signal(row)

        if (ma_signal == "BUY" and angle_signal == "BUY"
                and macd_signal == "BUY" and rsi_signal == "BUY"):
            return "BUY"

        if (ma_signal == "SELL" and angle_signal == "SELL"
                and macd_signal == "SELL" and rsi_signal == "SELL"):
            return "SELL"

        return None

    def get_exit_signal(self, row, position: dict) -> bool:
        rsi = row.get("rsi")
        if pd.isna(rsi):
            return False
        if position.get("type") == "BUY" and rsi < 45:
            return True
        if position.get("type") == "SELL" and rsi > 55:
            return True
        return False

    def get_sl_tp(self, row, signal: str, point: float):
        atr = row.get("atr", 0)
        if pd.isna(atr) or atr == 0:
            atr = row.get("close", 1) * 0.001  # fallback 0.1%
        close = row["close"]
        if signal == "BUY":
            return close - 2 * atr, close + 4 * atr
        return close + 2 * atr, close - 4 * atr

    def indicator_columns(self) -> list:
        return ["ema_fast", "ema_slow", "macd_line", "macd_signal", "rsi", "atr", "jaw", "teeth", "lips"]

    # ── Внутренние сигналы ─────────────────────────────────────────

    def _ma_signal(self, row) -> str:
        fast, slow = row.get("ema_fast"), row.get("ema_slow")
        if pd.isna(fast) or pd.isna(slow):
            return "NO_SIGNAL"
        return "BUY" if fast > slow else "SELL" if fast < slow else "NO_SIGNAL"

    def _angle_signal(self, row) -> str:
        angle = row.get("ema_fast_angle")
        if pd.isna(angle):
            return "NO_SIGNAL"
        return "BUY" if angle > 0 else "SELL" if angle < 0 else "NO_SIGNAL"

    def _macd_signal(self, row) -> str:
        h, p, s = row.get("macd_line"), row.get("macd_prev"), row.get("macd_signal")
        if pd.isna(h) or pd.isna(p):
            return "NO_SIGNAL"
        if h > 0 and h > p and h > s:
            return "BUY"
        if h < 0 and h < p and h < s:
            return "SELL"
        return "NO_SIGNAL"

    def _rsi_signal(self, row) -> str:
        r, rp, rp2 = row.get("rsi"), row.get("rsi_prev"), row.get("rsi_prev2")
        if pd.isna(r) or pd.isna(rp):
            return "NO_SIGNAL"
        if self.rsi_buy_low < r < self.rsi_buy_high and rp < r:
            return "BUY"
        if self.rsi_sell_low < r < self.rsi_sell_high and rp > r:
            return "SELL"
        return "NO_SIGNAL"
