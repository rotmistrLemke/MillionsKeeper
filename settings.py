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
    symbolXvalueH1 = {
    "EURUSDrfd": 100,
    "NZDUSDrfd": 65,
    "EURGBPrfd": 40,
    "USDCHFrfd": 55,
    "USDJPYrfd": 170,
    "EURCHFrfd": 25,
    "GBPUSDrfd": 90,
    "USDCADrfd": 50,
    "EURJPYrfd": 120,
    "AUDCADrfd": 55,
    "AUDUSDrfd": 55,
    "AUDJPYrfd": 70,
    "AUDCHFrfd": 30,
    "CHFJPYrfd": 120,
    "EURAUDrfd": 75,
    "GBPCHFrfd": 55,
    "EURCADrfd": 90,
    "GBPCADrfd": 95,
    "XAUUSDrfd": 425,
    "GBPJPYrfd": 130,
    "XAGUSDrfd": 1230,
    "USDSGDrfd": 60    
}

    symbolTradingStatus = {
        "EURUSDrfd": 3,
        "NZDUSDrfd": 3,
        "EURGBPrfd": 3,
        "USDCHFrfd": 3,
        "USDJPYrfd": 3,
        "EURCHFrfd": 3,
        "GBPUSDrfd": 3,
        "USDCADrfd": 3,
        "EURJPYrfd": 3,
        "AUDCADrfd": 3,
        "AUDUSDrfd": 3,
        "AUDJPYrfd": 3,
        "AUDCHFrfd": 3,
        "CHFJPYrfd": 3,
        "EURAUDrfd": 3,
        "GBPCHFrfd": 3,
        "EURCADrfd": 3,
        "GBPCADrfd": 3,
        "XAUUSDrfd": 1,
        "GBPJPYrfd": 3,
        "XAGUSDrfd": 1,
        "USDSGDrfd": 3    
    }
    
    symbolStopLossPoint = {
       
        "XAUUSDrfd": 1500,
        "XAGUSDrfd": 2000,
        "EURUSDrfd": 500
    }

    symbolStopLossValue = {
        
            "XAUUSDrfd": 0.0,
            "XAGUSDrfd": 0.0,
            "EURUSDrfd": 0.0   
        }

    symbolTakeProfitPoint = {
       
        "XAUUSDrfd": 500,
        "XAGUSDrfd": 1000,
        "EURUSDrfd": 200  
    }
 
    indicatorStatus = {
    "XAUUSDrfd_KAMA": 1, # 1 - stop 0 - start 
    "XAUUSDrfd_Alligator": 1,
    "EURUSDrfd_KAMA": 1, # 1 - stop 0 - start 
    "EURUSDrfd_Alligator": 1,
    "XAGUSDrfd_KAMA": 1, # 1 - stop 0 - start 
    "XAGUSDrfd_Alligator": 1   
}


   