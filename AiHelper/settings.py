class TargetType():
    LONG = 0
    SHORT = 1

class IndicatorType:
    HUNDRED_INTERSECTION = 1
    EXTREMUM_REVERSE = 2
    ZERO_INTERSECTION = 3
    ALLIGATOR_MAIN = 4
    ALLIGATOR_PERIODICITY = 5
    
class Settings:
    account = {"login":2000099548,"password":"VeeDM6A$E1","server":"AlfaForexRU-Real"}
    openAIapiKey = "sk-proj-phtwpp0xxxXJiyQns9zvUdN6RWXHpA-jT980fmis62nLveTU6WXdT02crcUSeBNiSrv6K3tjIWT3BlbkFJdD5DGFXyqbGCYWY5lHOsqV40BGN1XR0UyrsZ7J5ctU4qyvkeJNh2helJgb_zg33RtyzldtAD8A"
    deepSeekapiKey="sk-aitunnel-HGzxuEbTva3yHoSjke7UOOy9deMT17pp"
    deepSeekUrl="https://api.aitunnel.ru/v1/"
    proxyForOpenAI = "socks5h://127.0.0.1:9150"
    modelOpenAI = "gpt-4.1-mini-2025-04-14"
    #modelDeepSeek = "deepseek-r1-0528"
    modelDeepSeek = "gpt-4o-mini"
    
    candleCount = 2000
    
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
    "XAUUSDrfd": 1005,
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

    