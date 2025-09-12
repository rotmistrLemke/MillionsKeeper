import pandas as pd
from Support.mt5Connector import MT5Connector
from Support.appEnum import TargetType,IndicatorType, Settings
from logs.logger import Logger
import MetaTrader5 as mt5
from Support.anilizer import Extremum
import time
from Support.account import Account

account = Account.accountDemo
mt5Connector = MT5Connector(account)
logger = Logger()
settings = {
    "CCI_ReferenceLimitForEnter" : 60
}
logger = Logger()
extremum = Extremum(settings)

def ExtremumDisplay(result, cciValues, pair, cciAngle, stochAngle) :
    if not result["value"]:  
        return
    if(mt5Connector.symbolInPostions(pair,result["target"],IndicatorType.EXTREMUM_REVERSE)):
        print("Уже размещен заказ на данную пару")
        return  
    
    if result["target"] == TargetType.LONG:       
        print(f"{pair}\nПерепроданность, лонгуем\nЗначение: {cciValues[0]}")
        response = mt5Connector.orderOpen(pair,TargetType.LONG,IndicatorType.EXTREMUM_REVERSE,100,700)
        logger.saveToExcel(pair, "CCI_STOCH_OPEN_BUY", cciAngle, stochAngle, "", Settings.filenameCCIStoch)
        print(f"{pair}\nПерепроданность, ставлю ордер на лонг\nОрдер: {response["order"]}")

    if result["target"] == TargetType.SHORT:                
        print(f"{pair}\nПерекупленность, шортим\nЗначение: {cciValues[0]}")   
        response = mt5Connector.orderOpen(pair,TargetType.SHORT,IndicatorType.EXTREMUM_REVERSE,100,700)
        logger.saveToExcel(pair, "CCI_STOCH_OPEN_SHORT", cciAngle, stochAngle, "", Settings.filenameCCIStoch)
        print(f"{pair}\nПерекупленность, ставлю ордер на шорт\nОрдер: {response["order"]}")   

def symbolData(pair, timeframe):
    bars = mt5.copy_rates_from_pos(pair, timeframe, 0, 500)
    if bars is None:
        print("Не удалось получить данные:", mt5.last_error())
    data = pd.DataFrame(bars)
    return data

if __name__ == '__main__':
    pairs = Settings.dictPairXvalue.keys()
    nextLogTime = logger.getNextLogTime(mt5Connector.ServerTime('EURUSDrfd'))
    timeFrame = mt5.TIMEFRAME_H1
    currentTime = mt5Connector.ServerTime('EURUSDrfd')
    
    while True: 
        try: 
            pairs = Settings.dictPairXvalue.keys()
            for pair in pairs:

                currentTime = mt5Connector.ServerTime('EURUSDrfd')
                data = symbolData(pair, timeFrame) 
                checkFlat = extremum.checkFlat(data, pair, Settings.dictPairXvalue)
                cci, signal, main = mt5Connector.getData(pair,30)                        
                resultExtremum = extremum.checkForEnter(cci, signal, pair, checkFlat["value"])
                ExtremumDisplay(resultExtremum, cci, pair, resultExtremum["cciAngle"], resultExtremum["stochAngle"])   
                
                if currentTime >= nextLogTime: # Проверяем, нужно ли записывать время
                    logger.saveToExcel(pair, "CCI_STOCH_LOG", resultExtremum["cciAngle"], resultExtremum["stochAngle"], "", Settings.filenameCCIStoch)
                
            
            
            nextLogTime = logger.getNextLogTime(currentTime)   
            print(f"CCI_Stochastic все в порядке, время:{mt5Connector.ServerTime('EURUSDrfd')}")       
        except Exception as e:
            print(f"Ошибка хуибка читай логи: {str(e)}")
            logger.saveErrorsToExcel("cciStochastic", str(e), Settings.filenameErrors) 
            continue 
        time.sleep(40)