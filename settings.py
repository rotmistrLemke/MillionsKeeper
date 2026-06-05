import MetaTrader5 as mt5

class TargetType():
    LONG = 0
    SHORT = 1
    NEUTRAL = 2

# GlobalValues удалён (слайс B2) — единый источник торгового конфига теперь streams.


TF_MAP = {
    "M1":  mt5.TIMEFRAME_M1,
    "M5":  mt5.TIMEFRAME_M5,
    "M15": mt5.TIMEFRAME_M15,
    "M30": mt5.TIMEFRAME_M30,
    "H1":  mt5.TIMEFRAME_H1,
    "H4":  mt5.TIMEFRAME_H4,
    "D1":  mt5.TIMEFRAME_D1,
}

TF_REVERSE = {v: k for k, v in TF_MAP.items()}
    
class IndicatorType:
    HUNDRED_INTERSECTION = 1
    EXTREMUM_REVERSE = 2
    ZERO_INTERSECTION = 3
    ALLIGATOR_MAIN = 4
    BOLLINGER_BANDS = 5
    ALLIGATOR_METALLS = 6
    ALLIGATOR_METALLS_SAVE = 7
    test = 8
    
class Dictionary:

    # symbolTradingStatus перенесён в trading_status.py (слайс B1).
    # symbolExtremumStatus и indicatorStatus удалены (слайс D) — не использовались.

    symbolStopLossValue = {
        
                "EURUSDrfd": 0.0,
                "NZDUSDrfd": 0.0,
                "EURGBPrfd": 0.0,
                "USDCHFrfd": 0.0,
                "USDJPYrfd": 700.0,
                "EURCHFrfd": 0.0,
                "GBPUSDrfd": 0.0,
                "USDCADrfd": 0.0,
                "EURJPYrfd": 700.0,
                "AUDCADrfd": 0.0,
                "AUDUSDrfd": 0.0,
                "AUDJPYrfd": 0.0,
                "AUDCHFrfd": 0.0,
                "CHFJPYrfd": 0.0,
                "EURAUDrfd": 0.0,
                "GBPCHFrfd": 0.0,
                "EURCADrfd": 0.0,
                "GBPCADrfd": 0.0,
                "XAUUSDrfd": 2000.0,
                "GBPJPYrfd": 0.0,
                "XAGUSDrfd": 2000.0,
                "USDSGDrfd": 0.0,
                "#LCO":      0.0
        }

    # Средние спреды в пунктах (5-значный котировщик) для подстановки
    # в бэктест по умолчанию, если пользователь не указал spread явно.
    # Значения ориентировочные (типичные для ECN/Pro), при необходимости
    # подкорректировать под конкретного брокера.
    symbolDefaultSpread = {
        "EURUSDrfd": 20,
        "NZDUSDrfd": 26,
        "EURGBPrfd": 30,
        "USDCHFrfd": 30,
        "USDJPYrfd": 30,
        "EURCHFrfd": 32,
        "GBPUSDrfd": 32,
        "USDCADrfd": 32,
        "EURJPYrfd": 32,
        "AUDCADrfd": 33,
        "AUDUSDrfd": 33,
        "AUDJPYrfd": 36,
        "AUDCHFrfd": 39,
        "CHFJPYrfd": 50,
        "EURAUDrfd": 25,
        "GBPCHFrfd": 35,
        "EURCADrfd": 25,
        "GBPCADrfd": 40,
        "XAUUSDrfd": 45,
        "GBPJPYrfd": 25,
        "XAGUSDrfd": 200,
        "USDSGDrfd": 30,
        "#LCO":      10,
    }
