import MetaTrader5 as mt5
import pandas as pd
from ta.trend import AroonIndicator


def get_aroon_from_mt5(symbol, timeframe, period=14, num_bars=1000):
    if not mt5.initialize():
        print("Ошибка подключения к MT5")
        return None
    
    # Получаем данные (убедитесь, что timeframe корректен, например, mt5.TIMEFRAME_H1)
    rates = mt5.copy_rates_from_pos(symbol, timeframe, 0, num_bars)
    mt5.shutdown()
    
    if rates is None:
        print("Не удалось получить данные")
        return None
    
    df = pd.DataFrame(rates)
    df['time'] = pd.to_datetime(df['time'], unit='s')
    
    
 
   # Вычисление индикатора Aroon
    aroon_indicator = AroonIndicator(high=df['high'], low=df['low'], window=14)
    df['aroon_up'] = aroon_indicator.aroon_up()    # Линия Aroon Up (0-100)
    df['aroon_down'] = aroon_indicator.aroon_down()  # Линия Aroon Down (0-100)

    return df[['time', 'aroon_up', 'aroon_down']]

    


# Пример использования
df_aroon = get_aroon_from_mt5("XAUUSDrfd", mt5.TIMEFRAME_H1)
print(df_aroon.tail())