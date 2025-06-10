from mt5Connector import MT5Connector
from appEnum import TargetType,IndicatorType, Settings
from logger import Logger
from anilizer import Extremum
import time

account = {"login":2000096507,"password":"x$Kz8CD7XB","server":"AlfaForexRU-Real"}
mt5Connector = MT5Connector(account)
settings = {
    "CCI_ReferenceLimit" : 60,
    "CCI_CoefficientLimit" : 0.3,    
    "Stochastic_CoefficientLimit" : 0.1
}
logger = Logger()
extremum = Extremum(settings)

async def ExtremumDisplay(result, cciValues, pair) :
    if not result["value"]:  
        return
    if(mt5Connector.symbolInPostions(pair,result["target"],IndicatorType.EXTREMUM_REVERSE)):
        print("Уже размещен заказ на данную пару")
        return  
    
    if result["target"] == TargetType.LONG:       
        print(f"{pair}\nПерепроданность, лонгуем\nЗначение: {cciValues[0]}")
        response = mt5Connector.orderOpen(pair,TargetType.LONG,IndicatorType.EXTREMUM_REVERSE,100,700)
        print(f"{pair}\nПерепроданность, ставлю ордер на лонг\nОрдер: {response["order"]}") 
        
    if result["target"] == TargetType.SHORT:                
        print(f"{pair}\nПерекупленность, шортим\nЗначение: {cciValues[0]}")   
        response = mt5Connector.orderOpen(pair,TargetType.SHORT,IndicatorType.EXTREMUM_REVERSE,100,700)
        print(f"{pair}\nПерекупленность, ставлю ордер на шорт\nОрдер: {response["order"]}")   

if __name__ == '__main__':
    pairs = Settings.dictPairXvalue.keys()
    last_log_time = None
    nextLogTime = logger.getNextLogTime(mt5Connector.ServerTime('EURUSDrfd'))
    prev_bar_time = None
    currentTime = mt5Connector.ServerTime('EURUSDrfd')
    
    while True:  
        pairs = mt5Connector.getSymbols(50)
        for pair in pairs:
            if "#JNJ" in pair:
                continue
            print(f"\nПроверка пары CCI: {pair}")
            cci,signal,main = mt5Connector.getData(pair,30)                        
            resultExtremum = extremum.check(cci, signal)
            # ExtremumDisplay(resultExtremum, cci, pair)            
        time.sleep(5)