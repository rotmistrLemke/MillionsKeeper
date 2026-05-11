"""
EMA50 Overstretch + MTF Stoch/RSI — копия ручного подхода трейдера.

Идея (со слов автора счёта):
  «Смотрел большую удалённость от EMA50. Проверял на старшем таймфрейме
  перекупленность/перепроданность через Stochastic и RSI. Входил с SL и TP.
  На любой паре с понедельника по пятницу.»

Реализация — mean-reversion на оверстретче от EMA50 базового TF (H1)
с подтверждением экстремума на старшем TF (по умолчанию H4):

  SELL:
    Цена закрытия >= EMA50 + K * ATR(N)            — оверстретч вверх
    И HTF_RSI > rsi_overbought  ИЛИ  HTF_StochK > stoch_overbought

  BUY:
    Цена закрытия <= EMA50 - K * ATR(N)            — оверстретч вниз
    И HTF_RSI < rsi_oversold    ИЛИ  HTF_StochK < stoch_oversold

Выход — только по SL/TP (по ATR от формы или дефолтным мультипликаторам).
Mon–Fri: гарантирован движком (closes_on_weekend=True) и расписанием рынка.
"""

import numpy as np
import pandas as pd
import talib

from strategies.base import BaseStrategy


class Ema50OverstretchMtfStrategy(BaseStrategy):
    name = "ema50_overstretch_mtf"
    description = ("EMA50 Overstretch + MTF Stoch/RSI — фейдим перерастяжение от EMA50 "
                   "при экстремуме старшего ТФ")
    default_timeframe = "H1"

    def __init__(self,
                 ema_period: int = 50,
                 atr_period: int = 14,
                 stretch_atr: float = 4.5,
                 htf_factor: int = 4,           # 1 бар HTF = htf_factor баров базового
                 rsi_period: int = 14,
                 rsi_overbought: float = 70.0,
                 rsi_oversold:   float = 30.0,
                 stoch_k:  int = 14,
                 stoch_d:  int = 3,
                 stoch_slow_d: int = 3,
                 stoch_overbought: float = 80.0,
                 stoch_oversold:   float = 20.0,
                 sl_atr_mult: float = 1.5,
                 tp_atr_mult: float = 3.0):
        self.ema_period       = int(ema_period)
        self.atr_period       = int(atr_period)
        self.stretch_atr      = float(stretch_atr)
        self.htf_factor       = max(2, int(htf_factor))
        self.rsi_period       = int(rsi_period)
        self.rsi_overbought   = float(rsi_overbought)
        self.rsi_oversold     = float(rsi_oversold)
        self.stoch_k          = int(stoch_k)
        self.stoch_d          = int(stoch_d)
        self.stoch_slow_d     = int(stoch_slow_d)
        self.stoch_overbought = float(stoch_overbought)
        self.stoch_oversold   = float(stoch_oversold)
        self.sl_atr_mult      = float(sl_atr_mult or 0.0)
        self.tp_atr_mult      = float(tp_atr_mult or 0.0)

    def compute_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        close = df['close'].values.astype(float)
        high  = df['high'].values.astype(float)
        low   = df['low'].values.astype(float)

        df['ema50'] = talib.EMA(close, timeperiod=self.ema_period)
        df['atr']  = talib.ATR(high, low, close, timeperiod=self.atr_period)

        # ── HTF: агрегируем базовый TF в окна размера htf_factor ──────
        # Берём последний полностью закрытый HTF-бар, поэтому сдвигаем на 1 группу
        # (защита от peek-ahead: на момент бара i знаем только бары i .. i-(K-1),
        #  поэтому HTF-индикатор считаем по группе, заканчивающейся на i и сдвигаем
        #  на htf_factor вперёд — получаем «известное на этом баре» значение).
        K = self.htf_factor
        n = len(df)
        # group id: целочисленное деление индекса на K
        group_id = np.arange(n) // K

        # OHLC на HTF: open=open первого бара группы, high=max, low=min, close=close последнего.
        htf = pd.DataFrame({
            'open':  df['open'].groupby(group_id).transform('first'),
            'high':  df['high'].groupby(group_id).transform('max'),
            'low':   df['low'].groupby(group_id).transform('min'),
            'close': df['close'].groupby(group_id).transform('last'),
        })
        # Берём значение в КОНЦЕ группы и shift на K, чтобы на текущем баре было
        # значение последнего ЗАКРЫТОГО HTF-бара.
        # idx последнего бара группы:
        last_in_group = pd.Series(group_id, index=df.index).groupby(group_id).transform('count')
        # вместо магии — просто закрытые HTF-серии: посчитаем индикатор по полному
        # ряду htf_close, выровненному по концу группы.
        htf_close = htf['close'].astype(float).values
        htf_high  = htf['high'].astype(float).values
        htf_low   = htf['low'].astype(float).values

        # RSI / Stochastic считаем на полной серии HTF-«цены» (она пересчитывается
        # на каждом базовом баре — это чуть пессимистично, но безопасно). Для
        # устранения peek-ahead сдвинем на htf_factor: используем значение,
        # каким оно БЫЛО на баре, замыкавшем предыдущую HTF-группу.
        rsi  = talib.RSI(htf_close, timeperiod=self.rsi_period)
        slk, sld = talib.STOCH(htf_high, htf_low, htf_close,
                               fastk_period=self.stoch_k,
                               slowk_period=self.stoch_slow_d, slowk_matype=0,
                               slowd_period=self.stoch_d,      slowd_matype=0)

        df['htf_rsi']     = pd.Series(rsi,  index=df.index).shift(K)
        df['htf_stoch_k'] = pd.Series(slk,  index=df.index).shift(K)
        df['htf_stoch_d'] = pd.Series(sld,  index=df.index).shift(K)
        return df

    def is_flat(self, row) -> bool:
        # Mean-revert по своей сути работает в боковике; флэт-фильтр выключаем.
        return False

    def closes_on_weekend(self) -> bool:
        return True

    def uses_trailing_exit(self) -> bool:
        return False

    def get_entry_signal(self, row):
        required = ('ema50', 'atr', 'htf_rsi', 'htf_stoch_k')
        if any(row.get(c) is None or pd.isna(row.get(c)) for c in required):
            return None
        ema50 = row['ema50']
        atr  = row['atr']
        if atr <= 0:
            return None
        close = row['close']
        distance  = close - ema50
        threshold = self.stretch_atr * atr

        htf_rsi = row['htf_rsi']
        htf_k   = row['htf_stoch_k']

        # SELL: цена сильно выше EMA50 И HTF в перекупе (RSI или Stoch).
        if distance >= threshold and (htf_rsi > self.rsi_overbought or htf_k > self.stoch_overbought):
            return 'SELL'
        # BUY: цена сильно ниже EMA50 И HTF в перепроданности.
        if distance <= -threshold and (htf_rsi < self.rsi_oversold or htf_k < self.stoch_oversold):
            return 'BUY'
        return None

    def get_exit_signal(self, row, position: dict) -> bool:
        return False

    def get_sl_tp(self, row, signal: str, point: float):
        atr = row.get('atr')
        price = row['close']
        if atr is None or pd.isna(atr) or atr <= 0:
            atr = 100 * point
        sl = tp = None
        if self.sl_atr_mult > 0:
            sl = (price - self.sl_atr_mult * atr) if signal == 'BUY' \
                 else (price + self.sl_atr_mult * atr)
        if self.tp_atr_mult > 0:
            tp = (price + self.tp_atr_mult * atr) if signal == 'BUY' \
                 else (price - self.tp_atr_mult * atr)
        return sl, tp

    def indicator_columns(self):
        return ['ema50', 'atr', 'htf_rsi', 'htf_stoch_k']
