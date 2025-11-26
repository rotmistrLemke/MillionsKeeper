class TargetType():
    LONG = 0
    SHORT = 1
    NEUTRAL = 2

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

    symbolTradingStatus = {
        "EURUSDrfd": 3,
        "NZDUSDrfd": 3,
        "EURGBPrfd": 3,
        "USDCHFrfd": 3,
        "USDJPYrfd": 0,
        "EURCHFrfd": 3,
        "GBPUSDrfd": 3,
        "USDCADrfd": 3,
        "EURJPYrfd": 3,
        "AUDCADrfd": 3,
        "AUDUSDrfd": 3,
        "AUDJPYrfd": 0,
        "AUDCHFrfd": 3,
        "CHFJPYrfd": 3,
        "EURAUDrfd": 3,
        "GBPCHFrfd": 3,
        "EURCADrfd": 3,
        "GBPCADrfd": 3,
        "XAUUSDrfd": 0,
        "GBPJPYrfd": 3,
        "XAGUSDrfd": 3,
        "USDSGDrfd": 3    
    }
    
    symbolExtremumStatus = {
        "EURUSDrfd": 0,
        "NZDUSDrfd": 0,
        "EURGBPrfd": 0,
        "USDCHFrfd": 0,
        "USDJPYrfd": 0,
        "EURCHFrfd": 0,
        "GBPUSDrfd": 0,
        "USDCADrfd": 0,
        "EURJPYrfd": 0,
        "AUDCADrfd": 0,
        "AUDUSDrfd": 0,
        "AUDJPYrfd": 0,
        "AUDCHFrfd": 0,
        "CHFJPYrfd": 0,
        "EURAUDrfd": 0,
        "GBPCHFrfd": 0,
        "EURCADrfd": 0,
        "GBPCADrfd": 0,
        "XAUUSDrfd": 0,
        "GBPJPYrfd": 0,
        "XAGUSDrfd": 0,
        "USDSGDrfd": 0    
    }
    
    symbolStopLossValue = {
        
                "EURUSDrfd": 0.0,
                "NZDUSDrfd": 0.0,
                "EURGBPrfd": 0.0,
                "USDCHFrfd": 0.0,
                "USDJPYrfd": 0.0,
                "EURCHFrfd": 0.0,
                "GBPUSDrfd": 0.0,
                "USDCADrfd": 0.0,
                "EURJPYrfd": 0.0,
                "AUDCADrfd": 0.0,
                "AUDUSDrfd": 0.0,
                "AUDJPYrfd": 0.0,
                "AUDCHFrfd": 0.0,
                "CHFJPYrfd": 0.0,
                "EURAUDrfd": 0.0,
                "GBPCHFrfd": 0.0,
                "EURCADrfd": 0.0,
                "GBPCADrfd": 0.0,
                "XAUUSDrfd": 0.0,
                "GBPJPYrfd": 0.0,
                "XAGUSDrfd": 0.0,
                "USDSGDrfd": 0.0
        }

    indicatorStatus = {
    "XAUUSDrfd_KAMA": 1, # 1 - stop 0 - start 
    "XAUUSDrfd_Alligator": 1,
    "EURUSDrfd_KAMA": 1, # 1 - stop 0 - start 
    "EURUSDrfd_Alligator": 1,
    "XAGUSDrfd_KAMA": 1, # 1 - stop 0 - start 
    "XAGUSDrfd_Alligator": 1   
}

   