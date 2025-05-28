import MetaTrader5 as mt5
import pandas as pd
import numpy as np

# Настройки
symbol = "EURUSDrfd"
timeframe = mt5.TIMEFRAME_H1  # Таймфрейм (M5, H1, D1 и т.д.)
num_bars = 500  # Количество баров для расчета

# Инициализация MT5
if not mt5.initialize():
    print("Ошибка инициализации MT5:", mt5.last_error())
    quit()

# Получаем данные цен (медианные цены HL/2)
bars = mt5.copy_rates_from_pos(symbol, timeframe, 0, num_bars)
if bars is None:
    print("Не удалось получить данные:", mt5.last_error())

df = pd.DataFrame(bars)
df['median_price'] = (df['high'] + df['low']) / 2  # Медианная цена (HL/2)

# Функция для SMMA (Smoothed Moving Average)
def smma(data, period):
    smma_values = []
    for i in range(len(data)):
        if i < period:
            smma_values.append(np.nan)
        elif i == period:
            smma_values.append(data[i-period:i].mean())
        else:
            smma_values.append((smma_values[-1] * (period - 1) + data[i]) / period)
    return smma_values

# Рассчитываем линии Аллигатора
df['jaw'] = smma(df['median_price'], 13)  # Челюсти (13)
df['teeth'] = smma(df['median_price'], 8)   # Зубы (8)
df['lips'] = smma(df['median_price'], 5)    # Губы (5)

# Смещаем линии вперед (бары +8, +5, +3)
df['jaw_shifted'] = df['jaw'].shift(3)
df['teeth_shifted'] = df['teeth'].shift(1)
df['lips_shifted'] = df['lips'].shift(-1)

# Последние значения
last_jaw = df['jaw_shifted'].iloc[-2]
last_teeth = df['teeth_shifted'].iloc[-2]
last_lips = df['lips_shifted'].iloc[-2]

print(f"Последние значения Аллигатора ({symbol} {timeframe}):")
print(f"Челюсти (Jaw, 13/8): {last_jaw:.5f}")
print(f"Зубы (Teeth, 8/5): {last_teeth:.5f}")
print(f"Губы (Lips, 5/3): {last_lips:.5f}")


