from Support.mt5Connector import MT5Connector
from Support.appEnum import TargetType,IndicatorType, Settings
import time
import pandas as pd
import MetaTrader5 as mt5
from Support.anilizer import Alligator, AdaptiveMovingAverage
from logs.logger import Logger
from Support.account import Account

account = Account.accountDemo
mt5Connector = MT5Connector(account)
alligator = Alligator()
logger = Logger()
settings = Settings()
AMA = AdaptiveMovingAverage()
lastCheckedTime_H1 = None
lastCheckedTime_H4 = None
checkFlat = None


def checkOpen(angle, pair, timeFrame):    
    serverTime = mt5Connector.ServerTime(pair)
    if mt5Connector.symbolInPostions(pair,TargetType.LONG,f"{IndicatorType.ALLIGATOR_MAIN}") or mt5Connector.symbolInPostions(pair,TargetType.SHORT,f"{IndicatorType.ALLIGATOR_MAIN}"):
        #Уже есть ордер по данной паре и данному индикатору
        return
    
    if angle > 15:
        mt5Connector.orderOpenForAlligatorMain(pair, TargetType.LONG, f"{IndicatorType.ALLIGATOR_MAIN}")
        print(f"\n{"-" * 50}, \ntime:{serverTime} \npair: {pair} \nangle: {angle} \ncomment: Ордер LONG выставлен по условию, \n{"-" * 50}")
        logger.saveToExcel(pair, "OPEN_LONG", 0, angle, "Ордер LONG выставлен по условию", Settings.filenameAlligator)
            
    if angle < -15:        
        mt5Connector.orderOpenForAlligatorMain(pair, TargetType.SHORT, f"{IndicatorType.ALLIGATOR_MAIN}")
        print(f"\n{"-" * 50} \ntime:{serverTime} \npair: {pair} \nangle: {angle} \ncomment: Ордер SHORT выставлен по условию, \n{"-" * 50}")
        logger.saveToExcel(pair, "OPEN_SHORT", 0,  angle, "Ордер SHORT выставлен по условию", Settings.filenameAlligator)
            
def checkClose(currentPrice, openPrice, jaw, pair, timeFrame):
    serverTime = mt5Connector.ServerTime(pair)
    
    if currentPrice > jaw > openPrice:
        
        ticket = mt5Connector.getTicket(pair,TargetType.SHORT,f"{IndicatorType.ALLIGATOR_MAIN}")
        
        if ticket:
            
            mt5Connector.orderClose(ticket,pair)
            print(f"\n{"-" * 50} \ntime:{serverTime} \npair: {pair} \ncurrentPrice: {currentPrice} \nteeth: {jaw} \nopenPrice: {openPrice} \ncomment: Ордер SHORT снят \n{"-" * 50}")
            logger.saveToExcel(pair, "CLOSE_SHORT",jaw, angle,  "Ордер SHORT снят", Settings.filenameAlligator)
            
    if currentPrice < jaw < openPrice:
        
        ticket = mt5Connector.getTicket(pair,TargetType.LONG,f"{IndicatorType.ALLIGATOR_MAIN}")
        
        if ticket:
            
            mt5Connector.orderClose(ticket,pair)
            print(f"\n{"-" * 50} \ntime:{serverTime} \npair: {pair} \ncurrentPrice: {currentPrice} \nteeth: {jaw} \nopenPrice: {openPrice} \ncomment: Ордер LONG снят \n{"-" * 50}")
            logger.saveToExcel(pair, "CLOSE_LONG",jaw, angle,  "Ордер LONG снят", Settings.filenameAlligator)
          

def checkPairTicket(pair):
        
    ticketShort = mt5Connector.getTicket(pair,TargetType.SHORT,f"{IndicatorType.ALLIGATOR_MAIN}")
    ticketLong = mt5Connector.getTicket(pair,TargetType.LONG,f"{IndicatorType.ALLIGATOR_MAIN}")
        
    if ticketShort or ticketLong:
        return True
    else:
        return False
        


if __name__ == '__main__':

    pairs = Settings.onlyForex.keys()
    timeFrames = [mt5.TIMEFRAME_H1]
    nextLogTime = logger.getNextLogTime(mt5Connector.ServerTime('EURUSDrfd'))
    currentTime = mt5Connector.ServerTime('EURUSDrfd')
    
    while True:
        try:
            df_H1 = alligator.Df('EURUSDrfd', mt5.TIMEFRAME_H1)
            #df_H4 = alligator.Df('EURUSDrfd', mt5.TIMEFRAME_H4)
            isNewBar_H1, lastCheckedTime_H1 = alligator.IsNewBar(df_H1, lastCheckedTime_H1, mt5.TIMEFRAME_H1)
      
            #isNewBar_H4, lastCheckedTime_H4 = alligator.IsNewBar(df_H4, lastCheckedTime_H4, mt5.TIMEFRAME_H4)
            for timeFrame in timeFrames:
                    

                for pair in pairs:
                    currentTime = mt5Connector.ServerTime('EURUSDrfd')
                    currentPrice = mt5.symbol_info_tick(pair).bid
                    df = alligator.Df(pair, timeFrame)
                    checkFlat = AMA.checkFlat(df, pair, Settings.dictPairXvalue)
                    medianPrice,jaw,teeth,lips,openPrice = alligator.MainData(df) # Основные значения
                    jawShifted,teethShifted,lipsShifted = alligator.ShiftedData(jaw,teeth,lips,medianPrice) # Значения со сдвигом            
                    lastJaw,lastTeeth,lastLips,prelastLips = alligator.LastData(pair,jawShifted,teethShifted,lipsShifted) # Последние значения            
                    angle, candleDiff,lipsVsTeethDiff = alligator.SupportData(lastLips,prelastLips,pair,Settings.dictPairXvalue,lastTeeth) #Вспомогательные значения

                            
                    if currentTime >= nextLogTime: # Проверяем, нужно ли записывать время
                        logger.saveToExcel(pair, "ALLIGATOR_LOG", lastJaw, angle, f"{timeFrame}__{checkFlat["value"]}", Settings.filenameAlligator)

                    if checkFlat["value"] == True and checkPairTicket(pair) == False:
                        settings.dictPairTradingStop[pair] = 0
                
                    if checkFlat["value"] == False and settings.dictPairTradingStop[pair] == 0:
                        checkOpen(angle, pair, timeFrame) 
                    #if isNewBar_H4 and timeFrame == mt5.TIMEFRAME_H4:
                        #checkOpen(angle, pair, timeFrame)       
                        
                    #checkClose(currentPrice, openPrice, lastJaw, pair, timeFrame) 
                    
                    print(f"Пара: {pair} флэт: {checkFlat["value"]} угол: {checkFlat["angle"]} угол зубов:{angle} статус торговли: {settings.dictPairTradingStop[pair]}")
                    #Обновляем время следующей записи
                    
                
                
            print(f"AlligatorForMetals все в порядке, время:{mt5Connector.ServerTime('EURUSDrfd')}")
            nextLogTime = logger.getNextLogTime(currentTime)
        except Exception as e:
            print(f"Ошибка хуибка читай логи: {str(e)}")
            logger.saveErrorsToExcel("alligatorForMetalls", str(e), Settings.filenameErrors)
            continue
                
        time.sleep(5)
        

    
        
