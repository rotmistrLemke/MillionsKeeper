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
    
class Settings:
    dictPairXvalue = {
    "EURUSDrfd": 95,
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

    dictPairTradingStop = {
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
    
    dictPairTrailingStopValue = {
       
        "XAUUSDrfd": 1500,
        "XAGUSDrfd": 2000   
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
    "XAUUSDrfd": 425,
    "XAGUSDrfd": 1230  
}
    
    onlyMetalsM1 = {
    "XAUUSDrfd": 30,
    "XAGUSDrfd": 135,
    "EURUSDrfd": 40
}
    
    onlyMetalsM5 = {
    "XAUUSDrfd": 185,
    "XAGUSDrfd": 135,
    "EURUSDrfd": 40
}
    
    goldH1 = {
    "EURUSDrfd": 95,
    "XAUUSDrfd": 425,
    "XAGUSDrfd": 1230

}
    
    dictIndicatorStatus = {
    "XAUUSDrfd_KAMA": 1, # 1 - stop 0 - start 
    "XAUUSDrfd_Alligator": 1,
    "EURUSDrfd_KAMA": 1, # 1 - stop 0 - start 
    "EURUSDrfd_Alligator": 1,
    "XAGUSDrfd_KAMA": 1, # 1 - stop 0 - start 
    "XAGUSDrfd_Alligator": 1   
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

    filenameAlligator = "C:/Users/Administrator/projects/MillionsKeeper/logs/alligator_data_2.0.xlsx"
    filenameCCIStoch = "C:/Users/Administrator/projects/MillionsKeeper/logs/CCI_Stoch_data.xlsx"
    filenameErrors = "C:/Users/Administrator/projects/MillionsKeeper/logs/errors.xlsx"
    filenameBollingerBands="C:/Users/Administrator/projects/MillionsKeeper/logs/bollinger_bands_data.xlsx"

   