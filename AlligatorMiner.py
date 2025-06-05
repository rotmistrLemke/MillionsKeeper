from mt5Connector import MT5Connector
from appEnum import TargetType,IndicatorType, Settings
import time
from anilizer import Alligator
from logger import Logger

account = {"login":2000099548,"password":"VeeDM6A$E1","server":"AlfaForexRU-Real"}
mt5Connector = MT5Connector(account)
aligator = Alligator()
logger = Logger()
settings = Settings()
lastCheckedTime = None

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
    serverTime = mt5Connector.ServerTime(pair)
    if mt5Connector.symbolInPostions(pair,TargetType.LONG,IndicatorType.ALLIGATOR_MAIN) or mt5Connector.symbolInPostions(pair,TargetType.SHORT,IndicatorType.ALLIGATOR_MAIN):
        #Уже есть ордер по данной паре и данному индикатору
        return
    #if lips > teeth and lips > jaw and angle >= 10 and candlediff <= Settings.dictLipsCandleDiff.get(pair, 35):
    if (lips < teeth and angle > 5 and lipsVsTeethDiff <= Settings.dictLipsTeethDiff.get(pair, 10)) or (angle > 5 and lips > teeth) or (lips < teeth and angle > 15) or (angle > 30):
        mt5Connector.orderOpenForAlligatorMain(pair,TargetType.LONG,IndicatorType.ALLIGATOR_MAIN)
        print(f"\n{"-" * 50}, \ntime:{serverTime}, \npair: {pair}, \njaw: {jaw}, \nteeth: {teeth}, \nlips: {lips}, \nangle: {angle}, \ncomment: Ордер LONG выставлен по условию, \n{"-" * 50}")
        Alligator.saveToExcel(pair, "OPEN_LONG", jaw, teeth, lips, angle, candleDiff, lipsVsTeethDiff, "Ордер LONG выставлен по условию")
            
    #if lips < teeth and lips < jaw and angle <= -10 and candlediff <= Settings.dictLipsCandleDiff.get(pair, 35):
    if (lips > teeth and angle < -5 and lipsVsTeethDiff <= Settings.dictLipsTeethDiff.get(pair, 10)) or (angle < -5 and lips < teeth) or (lips > teeth and angle < -15) or (angle < -30):
        
        mt5Connector.orderOpenForAlligatorMain(pair,TargetType.SHORT,IndicatorType.ALLIGATOR_MAIN)
        print(f"\n{"-" * 50}, \ntime:{serverTime}, \npair: {pair}, \njaw: {jaw}, \nteeth: {teeth}, \nlips: {lips}, \nangle: {angle}, \ncomment: Ордер SHORT выставлен по условию, \n{"-" * 50}")
        Alligator.saveToExcel(pair, "OPEN_SHORT", jaw, teeth, lips, angle, candleDiff, lipsVsTeethDiff, "Ордер SHORT выставлен по условию")
            
def checkClose(jaw, teeth,lips, angle, lipsVsTeethDiff, pair):
    serverTime = mt5Connector.ServerTime(pair)
    
    if (lips < teeth and angle > 5 and lipsVsTeethDiff <= Settings.dictLipsTeethDiff.get(pair, 10)) or (angle > 5 and lips > teeth) or (lips < teeth and angle > 15) or (angle > 30):
        
        ticket = mt5Connector.getTicket(pair,TargetType.SHORT,IndicatorType.ALLIGATOR_MAIN)
        
        if ticket:
            
            mt5Connector.orderClose(ticket,pair)
            print(f"\n{"-" * 50}, \ntime:{serverTime}, \npair: {pair}, \njaw: {jaw}, \nteeth: {teeth}, \nlips: {lips}, \nangle: {angle}, \nLipsVsTeethDiff: {lipsVsTeethDiff}, \ncomment: Ордер SHORT снят, \n{"-" * 50}")
            Alligator.saveToExcel(pair, "CLOSE_SHORT", jaw, teeth, lips, angle, candleDiff, lipsVsTeethDiff, "Ордер SHORT снят")
           
            mt5Connector.orderOpenForAlligatorMain(pair,TargetType.LONG,IndicatorType.ALLIGATOR_MAIN)
            print(f"\n{"-" * 50}, \ntime:{serverTime}, \npair: {pair}, \njaw: {jaw}, \nteeth: {teeth}, \nlips: {lips}, \nangle: {angle}, \ncomment: Ордер LONG выставлен по закрытию предыдущего, \n{"-" * 50}")
            Alligator.saveToExcel(pair, "OPEN_LONG", jaw, teeth, lips, angle, candleDiff, lipsVsTeethDiff, "Ордер LONG выставлен по закрытию предыдущего")
            
    if (lips > teeth and angle < -5 and lipsVsTeethDiff <= Settings.dictLipsTeethDiff.get(pair, 10)) or (angle < -5 and lips < teeth) or (lips > teeth and angle < -15) or (angle < -30):
        ticket = mt5Connector.getTicket(pair,TargetType.LONG,IndicatorType.ALLIGATOR_MAIN)        
        if ticket:
            mt5Connector.orderClose(ticket, pair)
            print(f"\n{"-" * 50}, \ntime:{serverTime}, \npair: {pair}, \njaw: {jaw}, \nteeth: {teeth}, \nlips: {lips}, \nangle: {angle}, \nLipsVsTeethDiff: {lipsVsTeethDiff}, \ncomment: Ордер LONG снят, \n{"-" * 50}")
            Alligator.saveToExcel(pair, "CLOSE_LONG", jaw, teeth, lips, angle, candleDiff, lipsVsTeethDiff, "Ордер LONG снят")
            
            mt5Connector.orderOpenForAlligatorMain(pair,TargetType.SHORT,IndicatorType.ALLIGATOR_MAIN)
            print(f"\n{"-" * 50}, \ntime:{serverTime}, \npair: {pair}, \njaw: {jaw}, \nteeth: {teeth}, \nlips: {lips}, \nangle: {angle}, \ncomment: Ордер SHORT выставлен по закрытию предыдущего, \n{"-" * 50}")
            Alligator.saveToExcel(pair, "OPEN_SHORT", jaw, teeth, lips, angle, candleDiff, lipsVsTeethDiff, "Ордер SHORT выставлен по закрытию предыдущего")

if __name__ == '__main__':

    pairs = Settings.dictPairXvalue.keys()
    last_log_time = None
    nextLogTime = logger.getNextLogTime(mt5Connector.ServerTime('EURUSDrfd'))
    prev_bar_time = None
    
    while True:
        df = aligator.Df('EURUSDrfd')
        isNewBar, lastCheckedTime = aligator.IsNewBar(df, lastCheckedTime)    
        if isNewBar:
            for pair in pairs:
                df = aligator.Df(pair)
                medianPrice,jaw,teeth,lips = aligator.MainData(df) # Основные значения
                jawShifted,teethShifted,lipsShifted = aligator.ShiftedData(jaw,teeth,lips,medianPrice) # Значения со сдвигом            
                lastJaw,lastTeeth,lastLips,prelastLips = aligator.LastData(pair,jawShifted,teethShifted,lipsShifted) # Последние значения            
                angle,candleDiff,lipsVsTeethDiff = aligator.SupportData(lastLips,prelastLips,pair,dictPairXvalue,lastTeeth) #Вспомогательные значения

                currentTime = mt5Connector.ServerTime(pair)            
                # if currentTime >= nextLogTime: # Проверяем, нужно ли записывать время
                #     aligator.saveToExcel(pair, "LOG", jaw, teeth, lips, angle, candleDiff, lipsVsTeethDiff, "")

                #print(f"\npair: {pair}, jaw: {last_jaw}, teeth: {last_teeth}, lips: {last_lips}, angle: {angle}, CandleDiff: {candleDiff}, LipsVsTeethDiff: {lipsVsTeethDiff}, time:{get_server_time(pair)}")
                # checkOpen(lastJaw, lastTeeth, lastLips, angle, candleDiff, pair)    
                # checkClose(lastJaw, lastTeeth, lastLips, angle, lipsVsTeethDiff, pair)    
                # Обновляем время следующей записи
                nextLogTime = logger.getNextLogTime(currentTime)            
                print(f"Все в порядке, время:{mt5Connector.ServerTime(pair)}")
        time.sleep(5)
        

    
        
