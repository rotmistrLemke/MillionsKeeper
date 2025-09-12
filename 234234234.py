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


def calculate_pip_value(symbol, volume, order_type):
    """
    Расчет стоимости одного пункта для валютной пары
    
    :param symbol: Название символа (например, "EURUSD")
    :param volume: Объем сделки в лотах
    :param order_type: Тип ордера (BUY или SELL)
    :return: Стоимость одного пункта в валюте депозита
    """
    try:
        # Получаем информацию о символе
        symbol_info = mt5.symbol_info(symbol)
        if symbol_info is None:
            print(f"Не удалось получить информацию о символе {symbol}")
            return 0
        
        # Получаем текущую цену
        if order_type == mt5.ORDER_TYPE_BUY:
            price = mt5.symbol_info_tick(symbol).ask
        else:
            price = mt5.symbol_info_tick(symbol).bid
        
        # Размер контракта (стандартно 100000 для валютных пар)
        contract_size = symbol_info.trade_contract_size
        
        # Стоимость пункта в валюте котировки
        pip_value = (symbol_info.point * contract_size * volume)
        
        # Если валюта прибыли отличается от валюты депозита
        profit_currency = symbol_info.currency_profit
        deposit_currency = symbol_info.currency_margin
        
        if profit_currency != deposit_currency:
            # Конвертируем в валюту депозита
            conversion_symbol = profit_currency + deposit_currency
            conversion_info = mt5.symbol_info(conversion_symbol)
            
            if conversion_info is not None:
                conversion_rate = mt5.symbol_info_tick(conversion_symbol).ask
                pip_value *= conversion_rate
            else:
                # Пробуем обратную котировку
                conversion_symbol = deposit_currency + profit_currency
                conversion_info = mt5.symbol_info(conversion_symbol)
                if conversion_info is not None:
                    conversion_rate = mt5.symbol_info_tick(conversion_symbol).bid
                    pip_value /= conversion_rate
        
        return pip_value
        
    except Exception as e:
        print(f"Ошибка расчета стоимости пункта: {e}")
        return 0
    
calculate_pip_value("XAUUSDrfd", 0.01, 0)