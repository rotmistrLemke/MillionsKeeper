from Support.mt5Connector import MT5Connector
from Support.appEnum import Settings
import time
import talib
import MetaTrader5 as mt5
from Support.anilizer import Alligator
from logs.logger import Logger
from Support.account import Account

account = Account.accountReal
mt5Connector = MT5Connector(account)
alligator = Alligator()
logger = Logger()
settings = Settings()
lastCheckedTime_H1 = None
lastCheckedTime_H4 = None
period = 14  # Стандартный период Aroon


if __name__ == '__main__':

    pairs = Settings.onlyMetalsH1.keys()
    timeFrames = [mt5.TIMEFRAME_M1, mt5.TIMEFRAME_M5]
    nextLogTime = logger.getNextLogTime(mt5Connector.ServerTime('XAUUSDrfd'))
    currentTime = mt5Connector.ServerTime('XAUUSDrfd')
    
    while True:
        df_H1 = alligator.Df('XAUUSDrfd', mt5.TIMEFRAME_M1)
        df_H4 = alligator.Df('XAUUSDrfd', mt5.TIMEFRAME_M5)
        isNewBar_H1, lastCheckedTime_H1 = alligator.IsNewBar(df_H1, lastCheckedTime_H1, mt5.TIMEFRAME_M1)
        isNewBar_H4, lastCheckedTime_H4 = alligator.IsNewBar(df_H4, lastCheckedTime_H4, mt5.TIMEFRAME_M5)
        for timeFrame in timeFrames:
                
            for pair in pairs:
                currentTime = mt5Connector.ServerTime('XAUUSDrfd')
                currentPrice = mt5.symbol_info_tick(pair).bid
                df = alligator.Df(pair, timeFrame)
                # Расчет Aroon вручную
                df['Aroon_Up'], df['Aroon_Down'] = talib.AROON(df['high'], df['low'], timeperiod=14)
                

                        
                if currentTime >= nextLogTime: # Проверяем, нужно ли записывать время
                    logger.saveToExcel(pair, "ALLIGATOR_LOG", "", "", f"{timeFrame}", Settings.filenameAlligator)

                                
                if isNewBar_H1 and timeFrame == mt5.TIMEFRAME_M1:
                    print(df[['time', 'Aroon_Up', 'Aroon_Down']].tail()) 
                if isNewBar_H4 and timeFrame == mt5.TIMEFRAME_M5:
                    print(df[['time', 'Aroon_Up', 'Aroon_Down']].tail())       
                    
                #checkClose(currentPrice, openPrice, lastJaw, pair, timeFrame) 
                #Обновляем время следующей записи
                
            
            
        print(f"AlligatorForMetals все в порядке, время:{mt5Connector.ServerTime('XAUUSDrfd')}")
        nextLogTime = logger.getNextLogTime(currentTime)
            
        time.sleep(40)
        
        

    
        
