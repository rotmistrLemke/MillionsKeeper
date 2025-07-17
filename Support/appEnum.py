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
    
class Settings:
    dictPairXvalue = {
    "EURUSDrfd": 100,
    "NZDUSDrfd": 110,
    "EURGBPrfd": 90,
    "USDCHFrfd": 120,
    "USDJPYrfd": 245,
    "EURCHFrfd": 100,
    "GBPUSDrfd": 180,
    "USDCADrfd": 240,
    "EURJPYrfd": 265,
    "AUDCADrfd": 100,
    "AUDUSDrfd": 105,
    "AUDJPYrfd": 150,
    "AUDCHFrfd": 85,
    "CHFJPYrfd": 210,
    "EURAUDrfd": 175,
    "GBPCHFrfd": 135,
    "EURCADrfd": 210,
    "GBPCADrfd": 160,
    "XAUUSDrfd": 425,
    "GBPJPYrfd": 195,
    "XAGUSDrfd": 1230,
    "USDSGDrfd": 135    
}

    dictLipsCandleDiff = {
        "EURUSDrfd": 100,
        "NZDUSDrfd": 110,
        "EURGBPrfd": 90,
        "USDCHFrfd": 120,
        "USDJPYrfd": 245,
        "EURCHFrfd": 100,
        "GBPUSDrfd": 180,
        "USDCADrfd": 240,
        "EURJPYrfd": 265,
        "AUDCADrfd": 100,
        "AUDUSDrfd": 60,
        "AUDJPYrfd": 50,
        "AUDCHFrfd": 85,
        "CHFJPYrfd": 210,
        "EURAUDrfd": 175,
        "GBPCHFrfd": 135,
        "EURCADrfd": 210,
        "GBPCADrfd": 40,
        "XAUUSDrfd": 1000,
        "GBPJPYrfd": 195,
        "XAGUSDrfd": 200,
        "USDSGDrfd": 135    
    }

    dictLipsTeethDiff = {    
        "XAUUSDrfd": 150,
        "XAGUSDrfd": 170,
        "AUDJPYrfd": 15,
        "USDSGDrfd": 15,
        "AUDUSDrfd": 15
    }
    
    onlyMetalsH1 = {
    "XAUUSDrfd": 1005,
    "XAGUSDrfd": 1230  
}

    onlyForex = {
    "EURUSDrfd": 100,
    "NZDUSDrfd": 110,
    "EURGBPrfd": 90,
    "USDCHFrfd": 120,
    "USDJPYrfd": 245,
    "EURCHFrfd": 100,
    "GBPUSDrfd": 180,
    "USDCADrfd": 240,
    "EURJPYrfd": 265,
    "AUDCADrfd": 100,
    "AUDUSDrfd": 105,
    "AUDJPYrfd": 150,
    "AUDCHFrfd": 85,
    "CHFJPYrfd": 210,
    "EURAUDrfd": 175,
    "GBPCHFrfd": 135,
    "EURCADrfd": 210,
    "GBPCADrfd": 160,
    "GBPJPYrfd": 195
  
}

    dictPairTradingStop = {
        "EURUSDrfd": 1,
        "NZDUSDrfd": 1,
        "EURGBPrfd": 1,
        "USDCHFrfd": 1,
        "USDJPYrfd": 1,
        "EURCHFrfd": 1,
        "GBPUSDrfd": 1,
        "USDCADrfd": 1,
        "EURJPYrfd": 1,
        "AUDCADrfd": 1,
        "AUDUSDrfd": 1,
        "AUDJPYrfd": 1,
        "AUDCHFrfd": 1,
        "CHFJPYrfd": 1,
        "EURAUDrfd": 1,
        "GBPCHFrfd": 1,
        "EURCADrfd": 1,
        "GBPCADrfd": 1,
        "XAUUSDrfd": 1,
        "GBPJPYrfd": 1,
        "XAGUSDrfd": 1,
        "USDSGDrfd": 1    
    }
    
    dictPairTrailingStopValue = {
       
        "XAUUSDrfd": 1500,
        "XAGUSDrfd": 2000   
    }
    
    filenameAlligator = "C:/MillionsKeeper/logs/alligator_data_2.0.xlsx"
    filenameCCIStoch = "C:/MillionsKeeper/logs/CCI_Stoch_data.xlsx"
    filenameErrors = "C:/MillionsKeeper/logs/errors.xlsx"
    filenameBollingerBands="C:/MillionsKeeper/logs/bollinger_bands_data.xlsx"

   