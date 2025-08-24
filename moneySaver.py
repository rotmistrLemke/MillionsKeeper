import time
import pandas as pd
from Support.mt5Connector import MT5Connector
import MetaTrader5 as mt5
from Support.appEnum import TargetType, Settings
from Support.anilizer import Extremum, Alligator
from logs.logger import Logger
from Support.account import Account

account = Account.accountReal
mt5Connector = MT5Connector(account)
logger = Logger()
alligator = Alligator()
settings = {
    "CCI_ReferenceLimitForEnter" : 60
}
extremum = Extremum(settings)
settingsTrue = Settings()

# Получение всех открытых ордеров
orders = mt5Connector.getPositions()

def calculateStopLoss(pair, priceCurrent, orderType):
    trailingStopValue = settingsTrue.dictPairTrailingStopValue.get(pair, 200)
    if orderType == TargetType.LONG:
        stopLoss = priceCurrent - (trailingStopValue * mt5.symbol_info(pair).point)         # type: ignore
    
    if orderType == TargetType.SHORT:
        stopLoss = priceCurrent + (trailingStopValue * mt5.symbol_info(pair).point) # type: ignore

    return stopLoss # type: ignore



def setStopLoss(ticket, new_sl , oldSl, orderType):

    if (orderType == TargetType.LONG and new_sl > oldSl) or  oldSl == 0.0:
        # Подготавливаем структуру для изменения
        request = {
            "action": mt5.TRADE_ACTION_SLTP,
            "position": ticket,
            "sl": new_sl
        }

        # Отправляем запрос на изменение
        result = mt5.order_send(request) # type: ignore
        
        if result.retcode == mt5.TRADE_RETCODE_DONE:
            print(f"Ордер {ticket} успешно изменён.")
            return True
        else:
            print(f"Ошибка изменения ордера {ticket}. Код ошибки:", result.retcode)
            return False
    elif (orderType == TargetType.SHORT and new_sl < oldSl) or  oldSl == 0.0:
        # Подготавливаем структуру для изменения
        request = {
            "action": mt5.TRADE_ACTION_SLTP,
            "position": ticket,
            "sl": new_sl
        }

        # Отправляем запрос на изменение
        result = mt5.order_send(request) # type: ignore
        
        if result.retcode == mt5.TRADE_RETCODE_DONE:
            print(f"Ордер {ticket} успешно изменён.")
            return True
        else:
            print(f"Ошибка изменения ордера {ticket}. Код ошибки:", result.retcode)
            return False

if orders is None:
    print("Ошибка получения ордеров: ", mt5.last_error()) # type: ignore
else:
    # Преобразуем в DataFrame для удобного вывода
    while True:
        try:
            orders = mt5Connector.getPositions()
            # Фильтруем ордера с комментарием "4"
            filtered_orders_4 = []
            filtered_orders_6 = []
            cciFIlteredOrders = []

            if len(orders) == 0:
                print("Нет открытых ордеров.")
            else:
                for order in orders:
                    order_dict = order._asdict()
                    comment = order_dict.get("comment", "")
                    profit = order_dict.get("profit", 0)
                    volume = order_dict.get("volume", 0)
                    ticketId = order_dict.get("ticket", 0)
                    symbol = order_dict.get("symbol", 0)
                    priceCurrent = order_dict.get("price_current", 0),
                    orderType = order_dict.get("type", 0),
                    stopLoss = order_dict.get("sl", 0)
                    contractSize = mt5.symbol_info(symbol).trade_contract_size
                    point =  mt5.symbol_info(symbol).point
                    mainStopLossBorder = (70 *  volume) 
                    metallsStopLossBorder = (500)
                    
                    if str(comment) == "4" and profit >= mainStopLossBorder:  # Проверяем комментарий
                        setStopLoss(ticketId, calculateStopLoss( symbol, order_dict.get("price_current", 0), order_dict.get("type", 0)), stopLoss, order_dict.get("type", 0))
                        filtered_orders_4.append(order_dict)

                    if str(comment) == "4_16385":  # Проверяем комментарий
                        '''
                        if profit > 2000:
                             mt5Connector.orderClose(ticketId,symbol)
                             settingsTrue.dictPairTradingStop[symbol] = 1
                             '''

                        setStopLoss(ticketId, calculateStopLoss( symbol, order_dict.get("price_current", 0), order_dict.get("type", 0)), stopLoss, order_dict.get("type", 0))
                        filtered_orders_6.append(order_dict)
                    
                    if str(comment) == "2" :
                        cci,signal,main = mt5Connector.getData(symbol,30)                        
                        result = extremum.checkForClose(cci)
                        
                        if result["value"] == False:
                            mt5Connector.orderClose(ticketId,symbol)
                            logger.saveToExcel(symbol, "CCI_STOCH_CLOSE", 0, 0, result["cciValue"], Settings.filenameCCIStoch)
                                            
                        cciFIlteredOrders.append(order_dict)
                
                if not filtered_orders_4:
                    print("Нет ордеров с комментарием '4'.")
                else:
                    # Выводим отфильтрованные ордера в DataFrame
                    orders_df = pd.DataFrame(filtered_orders_4)
                    print("\n" + "="*50)
                    print("Ордера с комментарием '4':")
                    print(orders_df[['ticket', 'symbol', 'type', 'volume', 'price_open', 'sl', 'tp', 'time', 'comment', 'profit']])
                    print("="*50 + "\n")

                if not filtered_orders_6:
                    print("Нет ордеров с комментарием '6'.")
                else:
                    # Выводим отфильтрованные ордера в DataFrame
                    orders_df = pd.DataFrame(filtered_orders_6)
                    print("\n" + "="*50)
                    print("Ордера с комментарием '6':")
                    print(orders_df[['ticket', 'symbol', 'type', 'volume', 'price_open', 'sl', 'tp', 'time', 'comment', 'profit']])
                    print("="*50 + "\n")
                    
                if not cciFIlteredOrders:
                    print("Нет ордеров с комментарием '2'.")
                else:
                    # Выводим отфильтрованные ордера в DataFrame
                    orders_df = pd.DataFrame(cciFIlteredOrders)
                    print("\n" + "="*50)
                    print("Ордера с комментарием '2':")
                    print(orders_df[['ticket', 'symbol', 'type', 'volume', 'price_open', 'sl', 'tp', 'time', 'comment', 'profit']])
                    print("="*50 + "\n")
                    
                orders = mt5Connector.getPositions()
        except Exception as e:
            print(f"Ошибка хуибка читай логи: {str(e)}")
            #logger.saveErrorsToExcel("moneySaver", str(e), Settings.filenameErrors)
            continue
        time.sleep(2)

