"""Конфигурация AnomalyScannerAgent. Отдельный модуль, чтобы не трогать settings.py
(он не трекается в git — пользователь хранит его локально)."""
import MetaTrader5 as mt5


class AnomalySettings:
    """Параметры детектора аномалий и сканера."""
    EMA_PERIOD: int   = 50
    ATR_PERIOD: int   = 14
    ATR_MULT: float   = 4.0
    STOCH_FASTK: int  = 3
    STOCH_SLOWK: int  = 3
    STOCH_SLOWD: int  = 5
    STOCH_OB: float   = 93.0
    STOCH_OS: float   = 7.0
    TIMEFRAME: int    = mt5.TIMEFRAME_H1
    SCAN_INTERVAL_SEC: int = 300
    BARS_TO_FETCH: int     = 200
    MISS_TOLERANCE: int    = 2     # подряд пропусков символа до автозакрытия
    DB_PATH: str           = "data/anomalies.db"
