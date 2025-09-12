import MetaTrader5 as mt5
from datetime import datetime, timedelta

# Правильное подключение с указанием сервера
account = 2000108835
password = "f53E6v#Bss"
server = "AlfaForexRU-Real"  # Замените на правильное имя сервера
NOW = datetime.now() + timedelta(hours=3)
 
# установим подключение к терминалу MetaTrader 5
if not mt5.initialize():
    print("initialize() failed, error code =",mt5.last_error())
    quit()

authorized=mt5.login(login=account, password=password, server=server)  # пароль будет взят из базы терминала, если указано помнить данные для подключения
if authorized:
    print("connected to account #{}".format(account))
else:
    print("failed to connect at account #{}, error code: {}".format(account, mt5.last_error()))

def calculate_order_margin(symbol, order_type, volume, price=0.0):
    """
    Расчет требуемой маржи для ордера
    
    :param symbol: Название символа (например, "XAUUSD")
    :param order_type: Тип ордера (mt5.ORDER_TYPE_BUY или mt5.ORDER_TYPE_SELL)
    :param volume: Объем сделки в лотах
    :param price: Цена открытия (0.0 для текущей цены)
    :return: Требуемая маржа в валюте депозита
    """
    try:
        # Получаем текущие цены если не указана конкретная
        if price == 0.0:
            tick = mt5.symbol_info_tick(symbol)
            if order_type == mt5.ORDER_TYPE_BUY:
                price = tick.ask
            else:
                price = tick.bid
        
       # Правильные константы для MT5 Python
        # Вместо ORDER_ACTION_DEAL используем тип ордера напрямую
        margin = mt5.order_calc_margin(
            order_type,  # тип ордера
            symbol,
            volume,
            price
        )
        
        if margin is None:
            error = mt5.last_error()
            print(f"Ошибка расчета маржи для {symbol}: {error}")
            return 0
        
        return margin
        
        
    except Exception as e:
        print(f"Ошибка при расчете маржи: {e}")
        return 0
    
calculate_order_margin("XAUUSDrfd", 0, 0.04)