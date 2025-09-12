import time
import pandas as pd
from Support.mt5Connector import MT5Connector
import MetaTrader5 as mt5
from Support.appEnum import TargetType, Settings
from Support.account import Account

account = Account.accountDemo
mt5Connector = MT5Connector(account)
settings = Settings()

# Получение всех открытых ордеров
orders = mt5Connector.getPositions()

def calculateStopLoss(pair, priceCurrent, orderType):
    trailingStopValue = settings.dictPairTrailingStopValue.get(pair, 200)
    if orderType == TargetType.LONG:
        stopLoss = priceCurrent - (trailingStopValue * mt5.symbol_info(pair).point)         # type: ignore
        stopLoss = priceCurrent - (trailingStopValue * mt5.symbol_info(pair).point)         # type: ignore
    
    if orderType == TargetType.SHORT:
        stopLoss = priceCurrent + (trailingStopValue * mt5.symbol_info(pair).point) # type: ignore
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
        result = mt5.order_send(request) # type: ignore
        
        if result.retcode == mt5.TRADE_RETCODE_DONE:
            print(f"Ордер {ticket} успешно изменён.")
            return True
        else:
            print(f"Ошибка изменения ордера {ticket}. Код ошибки:", result.retcode)
            return False

if orders is None:
    print("Ошибка получения ордеров: ", mt5.last_error()) # type: ignore
    print("Ошибка получения ордеров: ", mt5.last_error()) # type: ignore
else:
    # Преобразуем в DataFrame для удобного вывода
    while True:
        try:
            orders = mt5Connector.getPositions()
            # Фильтруем ордера с комментарием "4"
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
                    
                    if str(comment) == "4_16385":  # Проверяем комментарий

                        if profit > 10:
                             mt5Connector.orderClose(ticketId,symbol)
                             settings.dictPairTradingStop[symbol] = 1

                        setStopLoss(ticketId, calculateStopLoss( symbol, order_dict.get("price_current", 0), order_dict.get("type", 0)), stopLoss, order_dict.get("type", 0))
                        
        except Exception as e:
            print(f"Ошибка хуибка читай логи: {str(e)}")
            continue
        time.sleep(2)

