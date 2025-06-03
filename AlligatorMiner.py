from mt5Connector import MT5Connector
import MetaTrader5 as mt5
from appEnum import TargetType,IndicatorType
import time
import pandas as pd
from anilizer import Aligator
from logger import Logger

account = {"login":2000099548,"password":"VeeDM6A$E1","server":"AlfaForexRU-Real"}
mt5Connector = MT5Connector(account)
aligator = Aligator(mt5Connector)
logger = Logger()
LOG_FILE = "logger.txt"  # Файл для записи

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

def checkOpen(jaw, teeth, lips, angle, candlediff, pair):
    if mt5Connector.symbolInPostions(pair,TargetType.LONG,IndicatorType.ALLIGATOR_MAIN) or mt5Connector.symbolInPostions(pair,TargetType.SHORT,IndicatorType.ALLIGATOR_MAIN):
        #Уже есть ордер по данной паре и данному индикатору
        return
    if lips > teeth and lips > jaw and angle >= 10 and candlediff <= dictLipsCandleDiff.get(pair, 35):
        serverTime = mt5Connector.ServerTime(pair)
        mt5Connector.orderOpenForAlligatorMain(pair,TargetType.LONG,IndicatorType.ALLIGATOR_MAIN)
        print(f"\nОрдер LONG открыт по условию \npair: {pair}, jaw: {jaw}, teeth: {teeth}, lips: {lips}, angle: {angle}, CandleDiff: {candleDiff}, time:{serverTime}")
        with open(LOG_FILE, "a") as f:
            f.write(f"\nОрдер LONG открыт по условию \npair: {pair}, jaw: {jaw}, teeth: {teeth}, lips: {lips}, angle: {angle}, CandleDiff: {candleDiff}, time:{serverTime}")

    if lips < teeth and lips < jaw and angle <= -10 and candlediff <= dictLipsCandleDiff.get(pair, 35):
        mt5Connector.orderOpenForAlligatorMain(pair,TargetType.SHORT,IndicatorType.ALLIGATOR_MAIN)
        print(f"\nОрдер SHORT открыт по условию\npair: {pair}, jaw: {jaw}, teeth: {teeth}, lips: {lips}, angle: {angle}, CandleDiff: {candleDiff}, time:{serverTime}")
        with open(LOG_FILE, "a") as f:
            f.write(f"\nОрдер SHORT открыт по условию \npair: {pair}, jaw: {jaw}, teeth: {teeth}, lips: {lips}, angle: {angle}, CandleDiff: {candleDiff}, time:{serverTime}")
    
def checkClose(jaw, teeth,lips, angle, lipsVsTeethDiff, pair):
    if lips < teeth and angle > 5 and lipsVsTeethDiff <= dictLipsTeethDiff.get(pair, 10) or (angle > 5 and lips > teeth) or (lips < teeth and angle > 15):
        ticket = mt5Connector.getTicket(pair,TargetType.SHORT,IndicatorType.ALLIGATOR_MAIN)
        if ticket:
            serverTime = mt5Connector.ServerTime(pair)
            mt5Connector.orderClose(ticket,pair)
            print(f"\nОрдер SHORT снят \npair: {pair}, jaw: {jaw}, teeth: {teeth}, lips: {lips}, angle: {angle}, LipsVsTeethDiff: {lipsVsTeethDiff}, time:{serverTime}")
            with open(LOG_FILE, "a") as f:
                f.write(f"\nОрдер SHORT снят \npair: {pair}, jaw: {jaw}, teeth: {teeth}, lips: {lips}, angle: {angle}, LipsVsTeethDiff: {lipsVsTeethDiff}, time:{serverTime}")
            mt5Connector.orderOpenForAlligatorMain(pair,TargetType.LONG,IndicatorType.ALLIGATOR_MAIN)
            print(f"\nОрдер LONG открыт по закрытию предыдущего \npair: {pair}, jaw: {jaw}, teeth: {teeth}, lips: {lips}, angle: {angle}, CandleDiff: {candleDiff}, time:{serverTime}")
            with open(LOG_FILE, "a") as f:
                f.write(f"\nОрдер LONG по закрытию предыдущего \npair: {pair}, jaw: {jaw}, teeth: {teeth}, lips: {lips}, angle: {angle}, CandleDiff: {candleDiff}, time:{serverTime}")

    if lips > teeth and angle < -5 and lipsVsTeethDiff <= dictLipsTeethDiff.get(pair, 10) or (angle < -5 and lips < teeth) or (lips > teeth and angle < -15):
        ticket = mt5Connector.getTicket(pair,TargetType.LONG,IndicatorType.ALLIGATOR_MAIN)
        if ticket:
            serverTime = mt5Connector.ServerTime(pair)
            mt5Connector.orderClose(ticket, pair)
            print(f"\nОрдер LONG снят \npair: {pair}, jaw: {jaw}, teeth: {teeth}, lips: {lips}, angle: {angle}, LipsVsTeethDiff: {lipsVsTeethDiff}, time:{serverTime}")
            with open(LOG_FILE, "a") as f:
                f.write(f"\nОрдер LONG снят \npair: {pair}, jaw: {jaw}, teeth: {teeth}, lips: {lips}, angle: {angle}, LipsVsTeethDiff: {lipsVsTeethDiff}, time:{serverTime}")
            mt5Connector.orderOpenForAlligatorMain(pair,TargetType.SHORT,IndicatorType.ALLIGATOR_MAIN)
            print(f"\nОрдер SHORT по закрытию предыдущего \npair: {pair}, jaw: {jaw}, teeth: {teeth}, lips: {lips}, angle: {angle}, CandleDiff: {candleDiff}, time:{serverTime}")
            with open(LOG_FILE, "a") as f:
                f.write(f"\nОрдер SHORT по закрытию предыдущего \npair: {pair}, jaw: {jaw}, teeth: {teeth}, lips: {lips}, angle: {angle}, CandleDiff: {candleDiff}, time:{serverTime}")


if __name__ == '__main__':
    #pairs = mt5Connector.getSymbols(50)
    pairs = dictPairXvalue.keys()
    last_log_time = None
    nextLogTime = logger.getNextLogTime(mt5Connector.ServerTime('EURUSDrfd'))
    prev_bar_time = None

    
    while True:        
        for pair in pairs:
            #mt5Connector.getHistoricalData(pair,mt5.TIMEFRAME_H1,500)
            
            # Получаем данные цен (медианные цены HL/2)
            bars = mt5.copy_rates_from_pos(pair, mt5.TIMEFRAME_H1, 0, 500)
            if bars is None:
                print("Не удалось получить данные:", mt5.last_error())

            df = pd.DataFrame(bars)
            medianPrice = (df['high'] + df['low']) / 2  # Медианная цена (HL/2)
            
            # Рассчитываем линии Аллигатора
            jaw = aligator.smma(medianPrice, 13)  # Челюсти (13)
            teeth = aligator.smma(medianPrice, 8)   # Зубы (8)
            lips = aligator.smma(medianPrice, 5)    # Губы (5)

            # Смещаем линии  (бары 3, 1, -1)
            jawShifted = jaw.shift(3)
            teethShifted = teeth.shift(1)
            lipsShifted = lips.shift(-1)
            
            # Последние значения
            countDecimalPlace = aligator.CountDecimalPlace(pair)
            lastJaw = float(f"{jawShifted.iloc[-2]:.{countDecimalPlace}f}")
            lastTeeth =  float(f"{teethShifted.iloc[-2]:.{countDecimalPlace}f}")
            lastLips = float(f"{lipsShifted.iloc[-2]:.{countDecimalPlace}f}")
            prelastLips = float(f"{lipsShifted.iloc[-3]:.{countDecimalPlace}f}")
            angle = int(f"{aligator.angle(lastLips,prelastLips,pair,dictPairXvalue.get(pair, 100)):.0f}")
            candleDiff = int(f"{aligator.getAlligatorVsCurrentCandelDiff(pair,lastLips):.0f}")
            lipsVsTeethDiff = int(f"{aligator.getLipsVsTeethDiff(pair, lastLips, lastTeeth):.0f}")
            
            currentTime = mt5Connector.ServerTime(pair)
        
            # Проверяем, нужно ли записывать время
            if currentTime >= nextLogTime:
                with open(LOG_FILE, "a") as f:
                    f.write(f"\npair: {pair}, jaw: {lastJaw}, teeth: {lastTeeth}, lips: {lastLips}, angle: {angle}, CandleDiff: {candleDiff}, LipsVsTeethDiff: {lipsVsTeethDiff}, time:{mt5Connector.ServerTime(pair)}")

            
           
            
            #print(f"\npair: {pair}, jaw: {last_jaw}, teeth: {last_teeth}, lips: {last_lips}, angle: {angle}, CandleDiff: {candleDiff}, LipsVsTeethDiff: {lipsVsTeethDiff}, time:{get_server_time(pair)}")
            checkOpen(lastJaw, lastTeeth, lastLips, angle, candleDiff, pair)    
            checkClose(lastJaw, lastTeeth, lastLips, angle, lipsVsTeethDiff, pair)    
        # Обновляем время следующей записи

        nextLogTime = logger.getNextLogTime(currentTime)
        
        print(f"Все в порядке, время:{mt5Connector.ServerTime(pair)}")
        time.sleep(3600)
        

    
        
