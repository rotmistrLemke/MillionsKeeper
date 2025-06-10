from mt5Connector import MT5Connector
from appEnum import TargetType,IndicatorType, Settings
import time
import pandas as pd
import MetaTrader5 as mt5
from anilizer import Alligator
from logger import Logger

account = {"login":2000099548,"password":"VeeDM6A$E1","server":"AlfaForexRU-Real"}
mt5Connector = MT5Connector(account)
alligator = Alligator()
logger = Logger()
settings = Settings()
lastCheckedTime = None


def checkOpen(angle, pair):    
    serverTime = mt5Connector.ServerTime(pair)
    if mt5Connector.symbolInPostions(pair,TargetType.LONG,IndicatorType.ALLIGATOR_MAIN) or mt5Connector.symbolInPostions(pair,TargetType.SHORT,IndicatorType.ALLIGATOR_MAIN):
        #Уже есть ордер по данной паре и данному индикатору
        return
    
    if angle > 15:
        mt5Connector.orderOpenForAlligatorMain(pair,TargetType.LONG,IndicatorType.ALLIGATOR_MAIN)
        print(f"\n{"-" * 50}, \ntime:{serverTime} \npair: {pair} \nangle: {angle} \ncomment: Ордер LONG выставлен по условию, \n{"-" * 50}")
        alligator.saveToExcel(pair, "OPEN_LONG", 0, angle, "Ордер LONG выставлен по условию")
            
    if angle < -15:        
        mt5Connector.orderOpenForAlligatorMain(pair,TargetType.SHORT,IndicatorType.ALLIGATOR_MAIN)
        print(f"\n{"-" * 50} \ntime:{serverTime} \npair: {pair} \nangle: {angle} \ncomment: Ордер SHORT выставлен по условию, \n{"-" * 50}")
        alligator.saveToExcel(pair, "OPEN_SHORT", 0,  angle, "Ордер SHORT выставлен по условию")
            
def checkClose(currentPrice, openPrice, teeth, pair):
    serverTime = mt5Connector.ServerTime(pair)
    
    if currentPrice > teeth > openPrice:
        
        ticket = mt5Connector.getTicket(pair,TargetType.SHORT,IndicatorType.ALLIGATOR_MAIN)
        
        if ticket:
            
            mt5Connector.orderClose(ticket,pair)
            print(f"\n{"-" * 50} \ntime:{serverTime} \npair: {pair} \ncurrentPrice: {currentPrice} \nteeth: {teeth} \nopenPrice: {openPrice} \ncomment: Ордер SHORT снят \n{"-" * 50}")
            alligator.saveToExcel(pair, "CLOSE_SHORT",teeth, angle,  "Ордер SHORT снят")
            
    if currentPrice < teeth < openPrice:
        
        ticket = mt5Connector.getTicket(pair,TargetType.LONG,IndicatorType.ALLIGATOR_MAIN)
        
        if ticket:
            
            mt5Connector.orderClose(ticket,pair)
            print(f"\n{"-" * 50} \ntime:{serverTime} \npair: {pair} \ncurrentPrice: {currentPrice} \nteeth: {teeth} \nopenPrice: {openPrice} \ncomment: Ордер LONG снят \n{"-" * 50}")
            alligator.saveToExcel(pair, "CLOSE_LONG",teeth, angle,  "Ордер LONG снят")
          

            
def IsNewBar(pair,df):
    new_time = df['time'].iloc[0]
    if lastCheckedTime[pair] == None:
        lastCheckedTime[pair] = new_time
        return False
    if new_time != lastCheckedTime[pair]:
            lastCheckedTime[pair] = new_time
            print("Обнаружена новая свеча!")
            return True
    return False

def Df(pair):
    bars = mt5.copy_rates_from_pos(pair, mt5.TIMEFRAME_H1, 0, 500)
    if bars is None:
        print("Не удалось получить данные:", mt5.last_error())
    df = pd.DataFrame(bars)
    return df

if __name__ == '__main__':

    pairs = Settings.dictPairXvalue.keys()
    last_log_time = None
    nextLogTime = logger.getNextLogTime(mt5Connector.ServerTime('EURUSDrfd'))
    prev_bar_time = None
    currentTime = mt5Connector.ServerTime('EURUSDrfd')
    
    while True:
        df = alligator.Df('EURUSDrfd')
        isNewBar, lastCheckedTime = alligator.IsNewBar(df, lastCheckedTime)    
        for pair in pairs:
            currentTime = mt5Connector.ServerTime('EURUSDrfd')
            currentPrice = mt5.symbol_info_tick(pair).ask
            df = alligator.Df(pair)
            medianPrice,jaw,teeth,lips,openPrice = alligator.MainData(df) # Основные значения
            jawShifted,teethShifted,lipsShifted = alligator.ShiftedData(jaw,teeth,lips,medianPrice) # Значения со сдвигом            
            lastJaw,lastTeeth,lastLips,prelastLips = alligator.LastData(pair,jawShifted,teethShifted,lipsShifted) # Последние значения            
            angle,candleDiff,lipsVsTeethDiff = alligator.SupportData(lastLips,prelastLips,pair,Settings.dictPairXvalue,lastTeeth) #Вспомогательные значения

                     
            if currentTime >= nextLogTime: # Проверяем, нужно ли записывать время
                alligator.saveToExcel(pair, "ALLIGATOR_LOG", lastTeeth, angle, "")

        
            if isNewBar:
                checkOpen(angle,pair)    
                
            checkClose(currentPrice, openPrice, lastTeeth, pair) 
            #Обновляем время следующей записи
               
          
           
        print(f"Все в порядке, время:{mt5Connector.ServerTime('EURUSDrfd')}")
        nextLogTime = logger.getNextLogTime(currentTime)
        time.sleep(40)
        

    
        
