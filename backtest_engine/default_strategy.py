import pandas as pd
import numpy as np
import talib


# ─── Индикаторы основной стратегии ───────────────────────────────────────

def calc_ema_series(prices, period):
    alpha = 2 / (period + 1)
    ema = np.empty_like(prices)
    ema[0] = prices[0]
    for i in range(1, len(prices)):
        ema[i] = alpha * prices[i] + (1 - alpha) * ema[i - 1]
    return ema


def compute_indicators(df):
    close = df['close'].values.astype(float)
    high  = df['high'].values.astype(float)
    low   = df['low'].values.astype(float)

    df['ema8']  = pd.Series(close).ewm(span=8,  adjust=False).mean().values
    df['ema21'] = pd.Series(close).ewm(span=21, adjust=False).mean().values

    ema_fast    = calc_ema_series(close, 12)
    ema_slow    = calc_ema_series(close, 26)
    macd_line   = ema_fast - ema_slow
    signal_line = calc_ema_series(macd_line, 9)
    df['macd_line']   = macd_line
    df['macd_signal'] = signal_line
    macd_prev = np.empty_like(macd_line)
    macd_prev[0] = np.nan
    macd_prev[1:] = macd_line[:-1]
    df['macd_prev'] = macd_prev

    df['rsi']       = talib.RSI(close, timeperiod=14)
    df['rsi_prev']  = df['rsi'].shift(1)
    df['rsi_prev2'] = df['rsi'].shift(2)

    prev_close = np.roll(close, 1)
    prev_close[0] = close[0]
    tr = np.maximum(high - low, np.maximum(np.abs(high - prev_close), np.abs(low - prev_close)))
    df['atr'] = pd.Series(tr).rolling(14).mean().values

    return df


# ─── Сигналы основной стратегии ──────────────────────────────────────────

def get_ma_signal(row):
    if row['ema8'] > row['ema21']:   return 'BUY'
    elif row['ema8'] < row['ema21']: return 'SELL'
    return 'NO_SIGNAL'


def get_macd_signal(row):
    h, p, s = row['macd_line'], row['macd_prev'], row['macd_signal']
    if pd.isna(p): return 'NO_SIGNAL'
    if h > 0 and h > p and h > s:   return 'BUY'
    elif h < 0 and h < p and h < s: return 'SELL'
    return 'NO_SIGNAL'


def get_rsi_signal(row):
    r, rp, rp2 = row['rsi'], row['rsi_prev'], row['rsi_prev2']
    if pd.isna(r) or pd.isna(rp) or pd.isna(rp2): return 'NO_SIGNAL'
    if 70 > r > 55 and rp > rp2: return 'BUY'
    elif 45 > r > 30 and rp < rp2: return 'SELL'
    return 'NO_SIGNAL'


def get_combined_signal(row):
    ma_s, macd_s, rsi_s = get_ma_signal(row), get_macd_signal(row), get_rsi_signal(row)
    if ma_s == 'BUY'  and macd_s == 'BUY'  and rsi_s == 'BUY':  return 'BUY'
    if ma_s == 'SELL' and macd_s == 'SELL' and rsi_s == 'SELL': return 'SELL'
    return 'NO_SIGNAL'
