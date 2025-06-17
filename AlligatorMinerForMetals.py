from Support.mt5Connector import MT5Connector
from Support.appEnum import TargetType,IndicatorType, Settings
import time
import pandas as pd
import MetaTrader5 as mt5
from Support.anilizer import Alligator
from Support.logger import Logger

account = {"login":2000099548,"password":"VeeDM6A$E1","server":"AlfaForexRU-Real"}
mt5Connector = MT5Connector(account)
alligator = Alligator()
logger = Logger()
settings = Settings()
lastCheckedTime_H1 = None
lastCheckedTime_H4 = None


def checkOpen(angle, pair, timeFrame):    
    serverTime = mt5Connector.ServerTime(pair)
    if mt5Connector.symbolInPostions(pair,TargetType.LONG,f"{IndicatorType.ALLIGATOR_MAIN}_{timeFrame}") or mt5Connector.symbolInPostions(pair,TargetType.SHORT,f"{IndicatorType.ALLIGATOR_MAIN}_{timeFrame}"):
        #Уже есть ордер по данной паре и данному индикатору
        return
    
    if angle > 15:
        mt5Connector.orderOpenForAlligatorMain(pair, TargetType.LONG, f"{IndicatorType.ALLIGATOR_MAIN}_{timeFrame}")
        print(f"\n{"-" * 50}, \ntime:{serverTime} \npair: {pair} \nangle: {angle} \ncomment: Ордер LONG выставлен по условию, \n{"-" * 50}")
        logger.saveToExcel(pair, "OPEN_LONG", 0, angle, "Ордер LONG выставлен по условию", Settings.filenameAlligator)
            
    if angle < -15:        
        mt5Connector.orderOpenForAlligatorMain(pair, TargetType.SHORT, f"{IndicatorType.ALLIGATOR_MAIN}_{timeFrame}")
        print(f"\n{"-" * 50} \ntime:{serverTime} \npair: {pair} \nangle: {angle} \ncomment: Ордер SHORT выставлен по условию, \n{"-" * 50}")
        logger.saveToExcel(pair, "OPEN_SHORT", 0,  angle, "Ордер SHORT выставлен по условию", Settings.filenameAlligator)
            
def checkClose(currentPrice, openPrice, jaw, pair, timeFrame):
    serverTime = mt5Connector.ServerTime(pair)
    
    if currentPrice > jaw > openPrice:
        
        ticket = mt5Connector.getTicket(pair,TargetType.SHORT,f"{IndicatorType.ALLIGATOR_MAIN}_{timeFrame}")
        
        if ticket:
            
            mt5Connector.orderClose(ticket,pair)
            print(f"\n{"-" * 50} \ntime:{serverTime} \npair: {pair} \ncurrentPrice: {currentPrice} \nteeth: {jaw} \nopenPrice: {openPrice} \ncomment: Ордер SHORT снят \n{"-" * 50}")
            logger.saveToExcel(pair, "CLOSE_SHORT",jaw, angle,  "Ордер SHORT снят", Settings.filenameAlligator)
            
    if currentPrice < jaw < openPrice:
        
        ticket = mt5Connector.getTicket(pair,TargetType.LONG,f"{IndicatorType.ALLIGATOR_MAIN}_{timeFrame}")
        
        if ticket:
            
            mt5Connector.orderClose(ticket,pair)
            print(f"\n{"-" * 50} \ntime:{serverTime} \npair: {pair} \ncurrentPrice: {currentPrice} \nteeth: {jaw} \nopenPrice: {openPrice} \ncomment: Ордер LONG снят \n{"-" * 50}")
            logger.saveToExcel(pair, "CLOSE_LONG",jaw, angle,  "Ордер LONG снят", Settings.filenameAlligator)
          

if __name__ == '__main__':

    pairs = Settings.onlyMetalsH1.keys()
    timeFrames = [mt5.TIMEFRAME_H1, mt5.TIMEFRAME_H4]
    nextLogTime = logger.getNextLogTime(mt5Connector.ServerTime('XAUUSDrfd'))
    currentTime = mt5Connector.ServerTime('XAUUSDrfd')
    
    while True:
        try:
            df_H1 = alligator.Df('XAUUSDrfd', mt5.TIMEFRAME_H1)
            df_H4 = alligator.Df('XAUUSDrfd', mt5.TIMEFRAME_H4)
            isNewBar_H1, lastCheckedTime_H1 = alligator.IsNewBar(df_H1, lastCheckedTime_H1, mt5.TIMEFRAME_H1)
            isNewBar_H4, lastCheckedTime_H4 = alligator.IsNewBar(df_H4, lastCheckedTime_H4, mt5.TIMEFRAME_H4)
            for timeFrame in timeFrames:
                    
                for pair in pairs:
                    currentTime = mt5Connector.ServerTime('XAUUSDrfd')
                    currentPrice = mt5.symbol_info_tick(pair).ask
                    df = alligator.Df(pair, timeFrame)
                    medianPrice,jaw,teeth,lips,openPrice = alligator.MainData(df) # Основные значения
                    jawShifted,teethShifted,lipsShifted = alligator.ShiftedData(jaw,teeth,lips,medianPrice) # Значения со сдвигом            
                    lastJaw,lastTeeth,lastLips,prelastLips = alligator.LastData(pair,jawShifted,teethShifted,lipsShifted) # Последние значения            
                    angle, candleDiff,lipsVsTeethDiff = alligator.SupportData(lastLips,prelastLips,pair,Settings.dictPairXvalue,lastTeeth) #Вспомогательные значения

                            
                    if currentTime >= nextLogTime: # Проверяем, нужно ли записывать время
                        logger.saveToExcel(pair, "ALLIGATOR_LOG", lastJaw, angle, f"{timeFrame}", Settings.filenameAlligator)

                
                    if isNewBar_H1 and timeFrame == mt5.TIMEFRAME_H1:
                        checkOpen(angle, pair, timeFrame) 
                    if isNewBar_H4 and timeFrame == mt5.TIMEFRAME_H4:
                        checkOpen(angle, pair, timeFrame)       
                        
                    checkClose(currentPrice, openPrice, lastJaw, pair, timeFrame) 
                    #Обновляем время следующей записи
                    
                
                
            print(f"AlligatorForMetals все в порядке, время:{mt5Connector.ServerTime('XAUUSDrfd')}")
            nextLogTime = logger.getNextLogTime(currentTime)
        except Exception as e:
            print(f"Ошибка при создании графика: {str(e)}")
            continue
                
        time.sleep(17)
        

    
        
