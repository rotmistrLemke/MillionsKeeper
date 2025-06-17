import MetaTrader5 as mt5
import pandas as pd
import numpy as np

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
    
    # Проверка на пропуски в данных
    if df.isnull().values.any():
        df = df.dropna()
    
    # Корректный расчет Aroon
    def calculate_aroon(high, low, period):
        aroon_up = []
        aroon_down = []
        for i in range(len(high)):
            if i < period:
                aroon_up.append(np.nan)
                aroon_down.append(np.nan)
            else:
                window_high = high[i-period:i]
                window_low = low[i-period:i]
                days_since_high = period - np.argmax(window_high) 
                days_since_low = period - np.argmin(window_low) 
                aroon_up.append(100 * (period - days_since_high) / period)
                aroon_down.append(100 * (period - days_since_low) / period)
        return aroon_up, aroon_down
    
    df['Aroon_Up'], df['Aroon_Down'] = calculate_aroon(df['high'].values, df['low'].values, period)
    return df[['time', 'Aroon_Up', 'Aroon_Down']].dropna()

# Пример использования
df_aroon = get_aroon_from_mt5("XAUUSDrfd", mt5.TIMEFRAME_H1)
print(df_aroon.tail())