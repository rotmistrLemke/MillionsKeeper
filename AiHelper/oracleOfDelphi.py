import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))  
import MetaTrader5 as mt5
import json
import time
from mt5Connector import MT5Connector
from settings import Settings
from openAIConnector import OpenAIConnector

# Конфигурация


mt5Connector = MT5Connector(Settings.account)
openAIConnector = OpenAIConnector()

symbols = Settings.dictPairXvalue.keys()
timeFrame = mt5.TIMEFRAME_H1
timeFrameH4 = mt5.TIMEFRAME_H4



def parseTradeSignal(jsonStr):
    try:
        signal = json.loads(jsonStr)
        requiredKeys = ['orderType', 'positionType', 'entryPoint', 'stopLoss', 
                         'takeProfit', 'signalPower', 'keySupport', 'keyResistance',
                         'trendAnalysis', 'volumeAnalysis', 'summary']
        
        if all(key in signal for key in requiredKeys):
            # Обработка чисел - округление до 5 знаков
            for key in ['entryPoint', 'stopLoss', 'takeProfit']:
                signal[key] = round(float(signal[key]), 5)
            
            # Обработка массивов поддержки/сопротивления
            for key in ['keySupport', 'keyResistance']:
                signal[key] = [round(float(x), 5) for x in signal[key]]
                
            # Декодирование строк
            for key in ['trendAnalysis', 'volumeAnalysis', 'summary']:
                if isinstance(signal[key], str):
                    # Если строка в Unicode, декодируем
                    signal[key] = signal[key].encode().decode('UTF-8')
                    
            return signal
        else:
            print("Некорректный формат ответа")
            return None
    except (json.JSONDecodeError, ValueError, TypeError) as e:
        print(f"Ошибка парсинга JSON: {str(e)}")
        return None

def executeTrade(signal):
    if signal and signal.get('signalPower', 0) >= 3:
        print(f"Исполняем ордер: {signal['positionType']} {signal['orderType']} @ {signal['entryPoint']:.5f}")
        # Здесь ваша логика исполнения через MT5 API
        # Пример:
        # order_request = {
        #     "action": mt5.TRADE_ACTION_DEAL,
        #     "symbol": SYMBOL.rstrip('rfd'),  # Убираем суффикс
        #     "volume": 0.1,
        #     "type": mt5.ORDER_TYPE_BUY if signal['positionType'] == "BUY" else mt5.ORDER_TYPE_SELL,
        #     "price": signal['entryPoint'],
        #     "sl": signal['stopLoss'],
        #     "tp": signal['takeProfit'],
        #     "comment": "AI Signal",
        # }
        # mt5.order_send(order_request)

def main():
    while True:
        try:
            for symbol in symbols:
                #print(f"\n[{time.ctime()}] Запуск анализа {symbol}")
                candles = mt5Connector.getCandles(symbol, timeFrame, Settings.candleCount)
                candlesH4 = mt5Connector.getCandles(symbol, timeFrameH4, Settings.candleCount)
                cci,signal,main = mt5Connector.getData(symbol,30)
                
                if candlesH4:

                    analysisJsonOpenAI = OpenAIConnector.analyzeWithOpenAI(symbol, candlesH4, cci).content

                    
                    if analysisJsonOpenAI:
                        print(f"[{time.ctime()}] Ответ от OpenAI получен:")
                        signalOpenAI = parseTradeSignal(analysisJsonOpenAI)
                        
                        if signalOpenAI:
                            # Красивый вывод с декодированными строками
                            print(json.dumps(signalOpenAI, indent=2, ensure_ascii=False))
                            if mt5Connector.symbolInPostions(symbol,signalOpenAI['positionType'],"openAI"):
                                print("Уже размещен заказ на данную пару")
                                continue
                            if signalOpenAI and signalOpenAI.get('signalPower', 0) >= 3:
                                
                                if signalOpenAI['orderType'] == "Market":
                                    mt5Connector.orderOpenByAI(symbol,signalOpenAI['positionType'],"openAI",signalOpenAI['takeProfit'],signalOpenAI['stopLoss'])
                                
                                if signalOpenAI['orderType'] == "Limit":
                                    mt5Connector.orderOpenStoplimit(symbol,signalOpenAI['positionType'],"openAI",signalOpenAI['entryPoint'],signalOpenAI['takeProfit'],signalOpenAI['stopLoss'])
    
        except Exception as e:
            print(f"Критическая ошибка: {str(e)}")
        
        print(f"[{time.ctime()}] Следующий анализ через 10 минут...")
        time.sleep(600)

if __name__ == "__main__":
    main()