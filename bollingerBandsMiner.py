import time
import talib
import pandas as pd
import MetaTrader5 as mt5
from Support.mt5Connector import MT5Connector
from Support.anilizer import Alligator, AdaptiveMovingAverage
from Support.appEnum import TargetType,IndicatorType, Settings
from logs.logger import Logger
from Support.account import Account

account = Account.accountReal
mt5Connector = MT5Connector(account)
symbol = "XAUUSDrfd"
alligator = Alligator()
logger = Logger()
settings = Settings()
AMA = AdaptiveMovingAverage()


def checkOpen(currentPrice, upper, lower, pair, timeFrame):    
    serverTime = mt5Connector.ServerTime(pair)
    if mt5Connector.symbolInPostions(pair,TargetType.LONG,f"{IndicatorType.BOLLINGER_BANDS}_{timeFrame}") or mt5Connector.symbolInPostions(pair,TargetType.SHORT,f"{IndicatorType.BOLLINGER_BANDS}_{timeFrame}"):
        #Уже есть ордер по данной паре и данному индикатору
        return
    
    if currentPrice <= lower:
        mt5Connector.orderOpenForBB(pair, TargetType.LONG, f"{IndicatorType.BOLLINGER_BANDS}_{timeFrame}")
        print(f"\n{"-" * 50}, \ntime:{serverTime} \npair: {pair} \ncurrentPrice: {currentPrice} \ncomment: Ордер LONG выставлен по условию, \n{"-" * 50}")
        logger.saveBBToExcel(pair, "OPEN_LONG", currentPrice, lower, 0, 0, "", Settings.filenameBollingerBands)
            
    if currentPrice >= upper:        
        mt5Connector.orderOpenForBB(pair, TargetType.SHORT, f"{IndicatorType.BOLLINGER_BANDS}_{timeFrame}")
        print(f"\n{"-" * 50} \ntime:{serverTime} \npair: {pair} \ncurrentPrice: {currentPrice} \ncomment: Ордер SHORT выставлен по условию, \n{"-" * 50}")
        logger.saveBBToExcel(pair, "OPEN_SHORT", currentPrice, 0, 0, upper, "", Settings.filenameBollingerBands)
          
def checkClose(currentPrice, middle, pair, timeFrame):
    serverTime = mt5Connector.ServerTime(pair)
    
    if currentPrice < middle:
        
        ticket = mt5Connector.getTicket(pair,TargetType.SHORT,f"{IndicatorType.BOLLINGER_BANDS}_{timeFrame}")
        
        if ticket:
            
            mt5Connector.orderClose(ticket, pair)
            print(f"\n{"-" * 50} \ntime:{serverTime} \npair: {pair} \ncurrentPrice: {currentPrice} \ncomment: Ордер SHORT снят \n{"-" * 50}")
            logger.saveBBToExcel(pair, "CLOSE_SHORT",currentPrice, 0, middle, 0,  "Ордер SHORT снят", 0, Settings.filenameAlligator)
            
    if currentPrice > middle:
        
        ticket = mt5Connector.getTicket(pair,TargetType.LONG,f"{IndicatorType.BOLLINGER_BANDS}_{timeFrame}")
        
        if ticket:
            
            mt5Connector.orderClose(ticket, pair)
            print(f"\n{"-" * 50} \ntime:{serverTime} \npair: {pair} \ncurrentPrice: {currentPrice} \ncomment: Ордер LONG снят \n{"-" * 50}")
            logger.saveBBToExcel(pair, "CLOSE_LONG",currentPrice, 0, middle, 0,  "Ордер LONG снят", 0, Settings.filenameAlligator)

def symbolData(pair, timeframe):
    bars = mt5.copy_rates_from_pos(pair, timeframe, 0, 500)
    if bars is None:
        print("Не удалось получить данные:", mt5.last_error())
    data = pd.DataFrame(bars)
    return data

def getBBData(data):

    close_prices = data['close'].values

    # Расчет Bollinger Bands
    upper, middle, lower = talib.BBANDS(
    close_prices,
    timeperiod=20,      # стандартный период
    nbdevup=2,         # верхнее отклонение (2σ)
    nbdevdn=2,         # нижнее отклонение (2σ)
    matype=0           # тип MA: 0 = SMA (по умолчанию)
    )

    #   Добавление в DataFrame
    data['BB_Upper'] = upper
    data['BB_Middle'] = middle
    data['BB_Lower'] = lower
    
    lastValues = data[['BB_Lower','BB_Middle','BB_Upper']].tail(1)
        
    lastLower = lastValues['BB_Lower'].iloc[-1]
    lastMiddle = lastValues['BB_Middle'].iloc[-1]
    lastUpper = lastValues['BB_Upper'].iloc[-1]
    
    return lastLower, lastMiddle, lastUpper

if __name__ == '__main__':

    pairs = Settings.onlyMetalsH1.keys()
    timeFrames = [mt5.TIMEFRAME_H1]
    nextLogTime = logger.getNextLogTime(mt5Connector.ServerTime('XAUUSDrfd'))
    currentTime = mt5Connector.ServerTime('XAUUSDrfd')
    
    while True:
        try:
            for timeFrame in timeFrames:
                    
                for pair in pairs:
                    currentTime = mt5Connector.ServerTime('XAUUSDrfd')
                    currentPrice = mt5.symbol_info_tick(pair).ask
                    data = symbolData(pair, timeFrame)
                    checkFlat = AMA.checkFlat(data, pair, Settings.dictPairXvalue)
                    lastLower, lastMiddle, lastUpper = getBBData(data)
                                                
                    if currentTime >= nextLogTime: # Проверяем, нужно ли записывать время
                        logger.saveBBToExcel(pair, "LOG", currentPrice, lastLower, lastMiddle, lastUpper, "", checkFlat["angle"], Settings.filenameBollingerBands)

                
                    if checkFlat["value"] == True:
                        checkOpen(currentPrice, lastUpper, lastLower, pair, timeFrame) 
                        checkClose(currentPrice, lastMiddle, pair, timeFrame) 
                        
                    print(f"Пара: {pair} флэт: {checkFlat["value"]} угол: {checkFlat["angle"]}")
                    #Обновляем время следующей записи
                    
                
                
            print(f"BollingerBands все в порядке, время:{mt5Connector.ServerTime('XAUUSDrfd')}")
            nextLogTime = logger.getNextLogTime(currentTime)
        except Exception as e:
            print(f"Ошибка хуибка читай логи: {str(e)}")
            logger.saveErrorsToExcel("BollingerBands", str(e), Settings.filenameErrors)
            continue
                
        time.sleep(5)