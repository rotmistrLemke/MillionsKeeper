from Support.mt5Connector import MT5Connector
from Support.appEnum import TargetType,IndicatorType, Settings
from Support.logger import Logger
from Support.anilizer import Extremum
import time

account = {"login":2000099548,"password":"VeeDM6A$E1","server":"AlfaForexRU-Real"}
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

if __name__ == '__main__':
    pairs = Settings.dictPairXvalue.keys()
    nextLogTime = logger.getNextLogTime(mt5Connector.ServerTime('EURUSDrfd'))
    currentTime = mt5Connector.ServerTime('EURUSDrfd')
    
    while True:  
        pairs = Settings.dictPairXvalue.keys()
        for pair in pairs:

            currentTime = mt5Connector.ServerTime('EURUSDrfd') 
            cci,signal,main = mt5Connector.getData(pair,30)                        
            resultExtremum = extremum.checkForEnter(cci, signal,pair)
            ExtremumDisplay(resultExtremum, cci, pair, resultExtremum["cciAngle"], resultExtremum["stochAngle"])   
            
            if currentTime >= nextLogTime: # Проверяем, нужно ли записывать время
                logger.saveToExcel(pair, "CCI_STOCH_LOG", resultExtremum["cciAngle"], resultExtremum["stochAngle"], "", Settings.filenameCCIStoch)
            
        
        
        nextLogTime = logger.getNextLogTime(currentTime)   
        print(f"CCI_Stochastic все в порядке, время:{mt5Connector.ServerTime('EURUSDrfd')}")        
        time.sleep(40)