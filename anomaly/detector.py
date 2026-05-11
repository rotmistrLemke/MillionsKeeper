from dataclasses import dataclass

import numpy as np
import pandas as pd
import talib

from anomaly.schemas import AnomalyType, DetectResult, Snapshot


@dataclass
class DetectorConfig:
    ema_period: int = 50
    atr_period: int = 14
    atr_mult: float = 4.0
    stoch_fastk: int = 3
    stoch_slowk: int = 3
    stoch_slowd: int = 5
    stoch_ob: float = 93.0
    stoch_os: float = 7.0


MIN_BARS_HEADROOM = 10


def evaluate(df: pd.DataFrame, cfg: DetectorConfig) -> DetectResult:
    """Оценить последний ЗАКРЫТЫЙ бар (iloc[-2]) на наличие аномалии.

    df: ohlc с колонками open/high/low/close/time, отсортирован по возрастанию.
    Возвращает DetectResult.types == [] если данных мало или аномалии нет.
    """
    min_bars = max(cfg.ema_period, cfg.atr_period, cfg.stoch_fastk + cfg.stoch_slowk + cfg.stoch_slowd) + MIN_BARS_HEADROOM
    if df is None or len(df) < min_bars:
        return DetectResult(types=[], snapshot=None)

    close = df["close"].to_numpy(dtype=float)
    high  = df["high"].to_numpy(dtype=float)
    low   = df["low"].to_numpy(dtype=float)

    ema  = talib.EMA(close, timeperiod=cfg.ema_period)
    atr  = talib.ATR(high, low, close, timeperiod=cfg.atr_period)
    slowk, slowd = talib.STOCH(
        high, low, close,
        fastk_period=cfg.stoch_fastk,
        slowk_period=cfg.stoch_slowk, slowk_matype=0,
        slowd_period=cfg.stoch_slowd, slowd_matype=0,
    )

    # Берём предпоследнюю строку (последний закрытый бар).
    idx = -2
    price = float(close[idx])
    e     = float(ema[idx]) if not np.isnan(ema[idx]) else None
    a     = float(atr[idx]) if not np.isnan(atr[idx]) else None
    k     = float(slowk[idx]) if not np.isnan(slowk[idx]) else None
    d     = float(slowd[idx]) if not np.isnan(slowd[idx]) else None

    if e is None or a is None or k is None or d is None or a <= 0:
        return DetectResult(types=[], snapshot=None)

    dist_atr = (price - e) / a
    types: list[AnomalyType] = []
    if dist_atr >= cfg.atr_mult:
        types.append(AnomalyType.EMA_FAR_UP)
    elif dist_atr <= -cfg.atr_mult:
        types.append(AnomalyType.EMA_FAR_DOWN)

    if k > cfg.stoch_ob:
        types.append(AnomalyType.STOCH_OB)
    elif k < cfg.stoch_os:
        types.append(AnomalyType.STOCH_OS)

    bar_time = pd.Timestamp(df["time"].iloc[idx]).tz_convert("UTC").isoformat() \
        if pd.Timestamp(df["time"].iloc[idx]).tzinfo \
        else pd.Timestamp(df["time"].iloc[idx], tz="UTC").isoformat()

    snap = Snapshot(
        price=price, ema50=e, atr=a, dist_atr=dist_atr,
        stoch_k=k, stoch_d=d, bar_time=bar_time,
    )
    return DetectResult(types=types, snapshot=snap)
