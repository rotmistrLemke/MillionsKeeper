import time
import pandas as pd
from mt5Connector import MT5Connector
import MetaTrader5 as mt5


account = {"login":2000099548,"password":"VeeDM6A$E1","server":"AlfaForexRU-Real"}
mt5Connector = MT5Connector(account)

# Получение всех открытых ордеров
orders = mt5Connector.getPositions()

def calculateStopLoss(profit, volume, pair, priceOpen, orderType):
    if orderType == 0:
        stopLoss = priceOpen + (((profit / volume) * mt5.symbol_info(pair).point) / 3)
        
    else:
        stopLoss = priceOpen - (((profit / volume) * mt5.symbol_info(pair).point) / 3)
    return stopLoss



def setStopLoss(ticket, new_sl , oldSl, orderType):

    if orderType == 0 and new_sl > oldSl:
        # Подготавливаем структуру для изменения
        request = {
            "action": mt5.TRADE_ACTION_SLTP,
            "position": ticket,
            "sl": new_sl
        }

        # Отправляем запрос на изменение
        result = mt5.order_send(request)
        
        if result.retcode == mt5.TRADE_RETCODE_DONE:
            print(f"Ордер {ticket} успешно изменён.")
            return True
        else:
            print(f"Ошибка изменения ордера {ticket}. Код ошибки:", result.retcode)
            return False
    elif (orderType == 1 and new_sl < oldSl) or  oldSl == 0.0:
        # Подготавливаем структуру для изменения
        request = {
            "action": mt5.TRADE_ACTION_SLTP,
            "position": ticket,
            "sl": new_sl
        }

        # Отправляем запрос на изменение
        result = mt5.order_send(request)
        
        if result.retcode == mt5.TRADE_RETCODE_DONE:
            print(f"Ордер {ticket} успешно изменён.")
            return True
        else:
            print(f"Ошибка изменения ордера {ticket}. Код ошибки:", result.retcode)
            return False

if orders is None:
    print("Ошибка получения ордеров: ", mt5.last_error())
elif len(orders) == 0:
    print("Нет открытых ордеров.")
else:
    # Преобразуем в DataFrame для удобного вывода
    while True:
        # Фильтруем ордера с комментарием "4"
        filtered_orders = []
        for order in orders:
            order_dict = order._asdict()
            comment = order_dict.get("comment", "")
            profit = order_dict.get("profit", 0)
            volume = order_dict.get("volume", 0)
            ticketId = order_dict.get("ticket", 0)
            symbol = order_dict.get("symbol", 0)
            priceOpen = order_dict.get("price_open", 0),
            orderType = order_dict.get("type", 0),
            stopLoss = order_dict.get("sl", 0)
            if str(comment) == "4" and profit > volume * 100:  # Проверяем комментарий
                setStopLoss(ticketId, calculateStopLoss(profit, volume, symbol, order_dict.get("price_open", 0), order_dict.get("type", 0)), stopLoss, order_dict.get("type", 0))
                filtered_orders.append(order_dict)
        
        if not filtered_orders:
            print("Нет ордеров с комментарием '4'.")
        else:
            # Выводим отфильтрованные ордера в DataFrame
            orders_df = pd.DataFrame(filtered_orders)
            print("\n" + "="*50)
            print("Ордера с комментарием '4':")
            print(orders_df[['ticket', 'symbol', 'type', 'volume', 'price_open', 'sl', 'tp', 'time', 'comment', 'profit']])
            print("="*50 + "\n")
        orders = mt5Connector.getPositions()
        time.sleep(10)

