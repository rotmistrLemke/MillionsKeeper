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
    "XAUUSDrfd": 425,
    "XAGUSDrfd": 1230,
    "GBPJPYrfd": 130,
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
        "XAUUSDrfd": 0,
        "GBPJPYrfd": 3,
        "XAGUSDrfd": 0,
        "USDSGDrfd": 3    
    }
    
    symbolStopLossPoint = {
       
        "XAUUSDrfd": 200,
        "XAGUSDrfd": 500,
        "EURUSDrfd": 500
    }

    symbolTakeProfitPoint = {
       
        "XAUUSDrfd": 500,
        "XAGUSDrfd": 1000,
        "EURUSDrfd": 200  
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

    symbolTakeProfitValue = {
            
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

    symbolXvalueH1 = {
        "XAUUSDrfd": 50,
        "XAGUSDrfd": 150
    }

    strengthValue = {
        "XAUUSDrfd": 0.5,
        "XAGUSDrfd": 0.01
    }

    strengthValueForClose = {
        "XAUUSDrfd": 0.8,
        "XAGUSDrfd": 0.2
    }

    spreadValue = {
        "XAUUSDrfd": 50,
        "XAGUSDrfd": 150
    }
   