import numpy as np
import math
from decimal import Decimal
import pandas as pd
import MetaTrader5 as mt5
import talib
from settings import Dictionary

dict = Dictionary()

class Alligator:

    def smma(self, data, period):
        smma_values = []
        for i in range(len(data)):
            if i < period:
                smma_values.append(np.nan)
            elif i == period:
                smma_values.append(data[i-period:i].mean())
            else:
                smma_values.append((smma_values[-1] * (period - 1) + data[i]) / period)
        return pd.Series(smma_values)
    
    def angle(self, currentLipsValue, previousLipsValue, symbol, pairXvalue, degrees=True):
        """
        Вычисляет arctg(x) и возвращает угол в градусах или радианах.

        Параметры:
            x (float): Число, для которого вычисляется арктангенс.
            degrees (bool): Если True, возвращает угол в градусах, иначе в радианах.

        Возвращает:
            float: Угол в градусах или радианах.
        """
        x = (currentLipsValue - previousLipsValue) / mt5.symbol_info(symbol).point
        angle_rad = math.atan2(x, pairXvalue/2)
        return int(f"{math.degrees(angle_rad):.0f}") if degrees else int(f"{angle_rad:.0f}")
    
    def CountDecimalPlace(self,symbol):    
        num = Decimal(str(mt5.symbol_info(symbol).point))
        return  abs(num.as_tuple().exponent)
    
    def MainData(self, df):
        medianPrice = (df['high'] + df['low']) / 2  # Медианная цена (HL/2)
        openPrice = df['open'].iloc[-1]
        # Рассчитываем линии Аллигатора
        jaw = self.smma(medianPrice, 13)  # Челюсти (13)
        teeth = self.smma(medianPrice, 8)   # Зубы (8)
        lips = self.smma(medianPrice, 5)    # Губы (5)
        return medianPrice,jaw,teeth,lips,openPrice

    def ShiftedData(self, jaw, teeth, lips, medianPrice):
        # Рассчитываем линии Аллигатора
        jaw = self.smma(medianPrice, 13)  # Челюсти (13)
        teeth = self.smma(medianPrice, 8)   # Зубы (8)
        lips = self.smma(medianPrice, 5)    # Губы (5)
        # Смещаем линии  (бары 3, 1, -1)
        jawShifted = jaw.shift(3)
        teethShifted = teeth.shift(1)
        lipsShifted = lips.shift(-1)

        return jawShifted,teethShifted,lipsShifted      
    
    def LastData(self,symbol,jawShifted,teethShifted,lipsShifted): 
        countDecimalPlace = self.CountDecimalPlace(symbol)
        lastJaw = float(f"{jawShifted.iloc[-2]:.{countDecimalPlace}f}")
        lastTeeth =  float(f"{teethShifted.iloc[-2]:.{countDecimalPlace}f}")
        lastLips = float(f"{lipsShifted.iloc[-2]:.{countDecimalPlace}f}")
        prelastLips = float(f"{lipsShifted.iloc[-3]:.{countDecimalPlace}f}")
        return lastJaw,lastTeeth,lastLips,prelastLips
    
    def SupportData(self, lastLips, prelastLips, symbol, dictPairXvalue):
        angle = self.angle(lastLips,prelastLips,symbol,dictPairXvalue.get(symbol, 100))
        return angle

    def IsNewBar(self, df, lastCheckedTime, timeFrame):
        new_time = df['time'].iloc[0]
        if lastCheckedTime is None:
            print(f"Первая свеча {timeFrame}, запоминаем время")
            return True, new_time  # Возвращаем флаг новой свечи и новое время
        if new_time != lastCheckedTime:
            print(f"Обнаружена новая свеча {timeFrame}!")
            return True, new_time  # Возвращаем True и новое время
        return False, lastCheckedTime  # Возвращаем False и старое время

    def Df(self, symbol, timeFrame):
        bars = mt5.copy_rates_from_pos(symbol, timeFrame, 0, 500)
        if bars is None:
            print("Не удалось получить данные:", mt5.last_error())
        df = pd.DataFrame(bars)
       
        df['time'] = pd.to_datetime(df['time'], unit='s')
        return df

class AdaptiveMovingAverage:
    
    def checkFlat(self, df, symbol, dictPairXvalue):

        close_prices = df['close'].values
        # Расчет AMA (период 10, fast=2, slow=30)
        ama = talib.KAMA(close_prices, timeperiod=10)  # KAMA (Kaufman's AMA) — альтернатива AMA
        # Добавление AMA в DataFrame
        df['AMA'] = ama
        last_two = df[['AMA']].tail(2)
        
        lastAma = last_two['AMA'].iloc[-1]
        prevAma = last_two['AMA'].iloc[-2]
        pairXvalue = dictPairXvalue.get(symbol, 100)
        
        x = (lastAma - prevAma) / mt5.symbol_info(symbol).point
        angle_rad = math.atan2(x, pairXvalue/2)
        angle = int(f"{math.degrees(angle_rad):.0f}") if math.degrees else int(f"{angle_rad:.0f}")
        
        if angle > 4 or angle < -4:
            return {"value": False, "angle": angle}
        else:
            return {"value": True, "angle": angle}
      
class BullsBearsPower:
    def get_bulls_bears_power(self, symbol, timeframe, period=13, bars=100):
        """
        Ручной расчет Bulls Power и Bears Power
        Bulls Power = High - EMA(Close, period)
        Bears Power = Low - EMA(Close, period)
        """
        try:
            # Получаем данные цен
            rates = mt5.copy_rates_from_pos(symbol, timeframe, 0, bars + period)
            if rates is None:
                print(f"Не удалось получить данные для {symbol}")
                return None, None
            
            # Создаем DataFrame
            df = pd.DataFrame(rates)
            df['time'] = pd.to_datetime(df['time'], unit='s')
            
            # Рассчитываем EMA
            df['ema'] = df['close'].ewm(span=period, adjust=False).mean()
            
            # Рассчитываем индикаторы
            df['bulls_power'] = df['high'] - df['ema']
            df['bears_power'] = df['low'] - df['ema']
            
            # Берем последние значения
            current_bulls = df['bulls_power'].iloc[-1]
            current_bears = df['bears_power'].iloc[-1]
            
            # Предыдущие значения для анализа тренда
            prev_bulls = df['bulls_power'].iloc[-2]
            prev_bears = df['bears_power'].iloc[-2]
            
            return current_bulls, current_bears
            
        except Exception as e:
            print(f"Ошибка расчета Bulls/Bears Power: {e}")
            return None, None

class MACD:
    def calculate_macd_manual(self, symbol, timeframe, fast_ema=15, slow_ema=21, signal_period=1):
        """
        Ручной расчет MACD по формулам
        MACD = EMA(fast) - EMA(slow)
        Signal = EMA(MACD, signal_period)
        Histogram = MACD - Signal
        """
        try:
            # Получаем достаточное количество данных
            data_length = slow_ema + signal_period + 10
            rates = mt5.copy_rates_from_pos(symbol, timeframe, 0, 100)
            if rates is None or len(rates) < data_length:
                print(f"Недостаточно данных для расчета MACD {symbol}")
                return None, None, None
            
            # Извлекаем цены закрытия
            closes = [rate['close'] for rate in rates]
            
            # Функция для расчета EMA
            def calculate_ema(prices, period):
                alpha = 2 / (period + 1)
                ema = [prices[0]]
                
                for i in range(1, len(prices)):
                    ema_value = alpha * prices[i] + (1 - alpha) * ema[i-1]
                    ema.append(ema_value)
                
                return ema
            
            # Рассчитываем быструю и медленную EMA
            ema_fast = calculate_ema(closes, fast_ema)
            ema_slow = calculate_ema(closes, slow_ema)
            
            # Рассчитываем MACD линию
            macd_line = []
            for i in range(len(closes)):
                macd_value = ema_fast[i] - ema_slow[i]
                macd_line.append(macd_value)
            
            # Рассчитываем сигнальную линию (EMA от MACD)
            signal_line = calculate_ema(macd_line, signal_period)
            
            # Рассчитываем гистограмму
            histogram = []
            for i in range(len(closes)):
                hist_value = macd_line[i] - signal_line[i]
                histogram.append(hist_value)
            
            # Текущие значения
            current_macd = macd_line[99]
            prev_macd = signal_line[98]
            prev2_macd = signal_line[97]
            
            print(f"Ручной MACD {symbol}: Current={current_macd:.5f}, Preview={prev_macd:.5f}")
            return current_macd, prev_macd, prev2_macd
            
        except Exception as e:
            print(f"Ошибка ручного расчета MACD: {e}")
            return None, None, None
        
class MovingAverage:
    """
    Класс для расчета различных типов скользящих средних
    """
    
    def sma(self, data, period):
        """
        Простая скользящая средняя (Simple Moving Average)
        
        Параметры:
            data: массив цен
            period: период скользящей средней
            
        Возвращает:
            pd.Series: значения SMA
        """
        return data.rolling(window=period).mean()
    
    def ema(self, data, period, adjust=False):
        """
        Экспоненциальная скользящая средняя (Exponential Moving Average)
        
        Параметры:
            data: массив цен
            period: период скользящей средней
            adjust: использовать ли корректировку (False для стандартного расчета)
            
        Возвращает:
            pd.Series: значения EMA
        """
        return data.ewm(span=period, adjust=adjust).mean()
    
    def wma(self, data, period):
        """
        Взвешенная скользящая средняя (Weighted Moving Average)
        
        Параметры:
            data: массив цен
            period: период скользящей средней
            
        Возвращает:
            pd.Series: значения WMA
        """
        weights = np.arange(1, period + 1)
        return data.rolling(window=period).apply(lambda x: np.dot(x, weights) / weights.sum(), raw=True)
    
    def smma(self, data, period):
        """
        Сглаженная скользящая средняя (Smoothed Moving Average)
        Используется в индикаторе Аллигатора
        """
        smma_values = []
        for i in range(len(data)):
            if i < period:
                smma_values.append(np.nan)
            elif i == period:
                smma_values.append(data[i-period:i].mean())
            else:
                smma_values.append((smma_values[-1] * (period - 1) + data[i]) / period)
        return pd.Series(smma_values)
    
    def calculate_ma(self, data, period, ma_type='SMA'):
        """
        Универсальный метод для расчета скользящих средних
        
        Параметры:
            data: массив цен
            period: период скользящей средней
            ma_type: тип скользящей средней ('SMA', 'EMA', 'WMA', 'SMMA')
            
        Возвращает:
            pd.Series: значения выбранной скользящей средней
        """
        ma_type = ma_type.upper()
        
        if ma_type == 'SMA':
            return self.sma(data, period)
        elif ma_type == 'EMA':
            return self.ema(data, period)
        elif ma_type == 'WMA':
            return self.wma(data, period)
        elif ma_type == 'SMMA':
            return self.smma(data, period)
        else:
            raise ValueError(f"Неизвестный тип скользящей средней: {ma_type}")
    
    def ma_cross_signal(self, fast_ma, slow_ma, symbol):
        """
        Определение сигналов пересечения скользящих средних
        
        Параметры:
            fast_ma: быстрая скользящая средняя
            slow_ma: медленная скользящая средняя
            
        Возвращает:
            dict: сигналы и информация о пересечении
        """
        if len(fast_ma) < 2 or len(slow_ma) < 2:
            return {'signal': 'NO_SIGNAL', 'strength': 0, 'current_fast': 0, 'current_slow': 0, 'angle_fast': 0, 'angle_slow': 0}
        
        current_fast = fast_ma.iloc[-1]
        previous_fast = fast_ma.iloc[-2]
        alligator = Alligator()
        angle_fast = alligator.angle(current_fast, previous_fast, symbol, dict.symbolXvalueH1[symbol])
        current_slow = slow_ma.iloc[-1]
        previous_slow = slow_ma.iloc[-2]
        angle_slow = alligator.angle(current_slow, previous_slow, symbol, dict.symbolXvalueH1[symbol])
        
        # Проверка на наличие NaN значений
        if pd.isna(current_fast) or pd.isna(previous_fast) or pd.isna(current_slow) or pd.isna(previous_slow):
            return {'signal': 'NO_SIGNAL', 'strength': 0, 'current_fast': 0, 'current_slow': 0, 'angle_fast': 0, 'angle_slow': 0}
        
        condition_diff_buy = current_fast > current_slow and previous_fast < previous_slow
        condition_diff_sell = current_fast < current_slow and previous_fast > previous_slow

        # Определение сигнала
        if condition_diff_buy:
            return {
                'signal': 'BUY',
                'strength': abs(current_fast - current_slow),
                'current_fast': current_fast,
                'current_slow': current_slow,
                'angle_fast': angle_fast,
                'angle_slow': angle_slow
            }
        elif condition_diff_sell:
            return {
                'signal': 'SELL', 
                'strength': abs(current_fast - current_slow),
                'current_fast': current_fast,
                'current_slow': current_slow,
                'angle_fast': angle_fast,
                'angle_slow': angle_slow
            }
        else:
            return {
                'signal': 'NO_SIGNAL',
                'strength': abs(current_fast - current_slow),
                'current_fast': current_fast,
                'current_slow': current_slow,
                'angle_fast': angle_fast,
                'angle_slow': angle_slow}
    
    def ma_critical_angle(self, fast_ma, slow_ma, symbol):
        """
        Определение сигналов резких углов средних скользящих
        
        Параметры:
            fast_ma: быстрая скользящая средняя
            slow_ma: медленная скользящая средняя
            
        Возвращает:
            dict: сигналы и информация о пересечении
        """
        if len(fast_ma) < 2 or len(slow_ma) < 2:
            return {'signal': 'NO_SIGNAL', 'strength': 0, 'current_fast': 0, 'current_slow': 0, 'angle_fast': 0, 'angle_slow': 0}
        
        current_fast = fast_ma.iloc[-1]
        previous_fast = fast_ma.iloc[-2]
        alligator = Alligator()
        angle_fast = alligator.angle(current_fast, previous_fast, symbol, dict.symbolXvalueH1[symbol])
        current_slow = slow_ma.iloc[-1]
        previous_slow = slow_ma.iloc[-2]
        angle_slow = alligator.angle(current_slow, previous_slow, symbol, dict.symbolXvalueH1[symbol])
        
        # Проверка на наличие NaN значений
        if pd.isna(current_fast) or pd.isna(previous_fast) or pd.isna(current_slow) or pd.isna(previous_slow):
            return {'signal': 'NO_SIGNAL', 'strength': 0, 'current_fast': 0, 'current_slow': 0, 'angle_fast': 0, 'angle_slow': 0}
        
        condition_angle_buy = angle_fast > 65
        condition_angle_sell = angle_fast < -65

        # Определение сигнала
        if condition_angle_buy:
            return {
                'signal': 'BUY',
                'strength': abs(current_fast - current_slow),
                'current_fast': current_fast,
                'current_slow': current_slow,
                'angle_fast': angle_fast,
                'angle_slow': angle_slow
            }
        elif condition_angle_sell:
            return {
                'signal': 'SELL', 
                'strength': abs(current_fast - current_slow),
                'current_fast': current_fast,
                'current_slow': current_slow,
                'angle_fast': angle_fast,
                'angle_slow': angle_slow
            }
        else:
            return {
                'signal': 'NO_SIGNAL',
                'strength': abs(current_fast - current_slow),
                'current_fast': current_fast,
                'current_slow': current_slow,
                'angle_fast': angle_fast,
                'angle_slow': angle_slow}
   
    def get_ma_for_symbol(self, symbol, timeframe, period, ma_type='EMA', price_type='close', bars=100):
        """
        Получение скользящей средней для символа
        
        Параметры:
            symbol: торговый символ
            timeframe: таймфрейм
            period: период скользящей средней
            ma_type: тип скользящей средней
            price_type: тип цены ('open', 'high', 'low', 'close')
            bars: количество баров
            
        Возвращает:
            pd.Series: значения скользящей средней
        """
        try:
            # Получаем данные
            rates = mt5.copy_rates_from_pos(symbol, timeframe, 0, bars + period)
            if rates is None:
                print(f"Не удалось получить данные для {symbol}")
                return None
            
            # Создаем DataFrame
            df = pd.DataFrame(rates)
            df['time'] = pd.to_datetime(df['time'], unit='s')
            
            # Выбираем тип цены
            if price_type == 'open':
                price_data = df['open']
            elif price_type == 'high':
                price_data = df['high']
            elif price_type == 'low':
                price_data = df['low']
            else:  # close по умолчанию
                price_data = df['close']
            
            # Рассчитываем скользящую среднюю
            ma_values = self.calculate_ma(price_data, period, ma_type)
            
            return ma_values
            
        except Exception as e:
            print(f"Ошибка расчета скользящей средней для {symbol}: {e}")
            return None
        
class ATR:
  
    def calculate_atr(self, symbol, timeframe):
        rates = mt5.copy_rates_from_pos(symbol, timeframe, 0, 500)
        df = pd.DataFrame(rates)
        high = df['high']
        low = df['low']
        close = df['close']
        prev_close = close.shift(1)
        tr = pd.concat([
        (high - low).abs(),
        (high - prev_close).abs(),
        (low - prev_close).abs()
        ],axis=1).max(axis=1)

        return tr.rolling(14).mean()
    
class ADX:

    def ExponentialMA(self, i, period, prev_value, values):
        if i == 0:
            return prev_value
        else:
            ema = (values[i] - prev_value) * 2 / (period + 1) + prev_value
            return ema
    
    def ADX(self, high, low, close, adx_period):
        """Расчет ADX с возвратом +DI и -DI"""
        # Инициализация массивов
        pdi = [0] * len(high)
        ndi = [0] * len(high)
        adx = [0] * len(high)
        tmp_buffer = [0] * len(high)
        
        # Временные массивы для несглаженных значений DI
        raw_plus_di = [0] * len(high)
        raw_minus_di = [0] * len(high)
        
        # Итерация по данным
        for i in range(1, len(high)):
            # Получаем цены
            high_price = high[i]
            prev_high = high[i-1]
            low_price = low[i]
            prev_low = low[i-1]
            prev_close = close[i-1]
            
            # Расчет направленного движения
            tmp_pos = high_price - prev_high
            tmp_neg = prev_low - low_price
            
            # Логика направленного движения
            if tmp_pos < 0:
                tmp_pos = 0
            if tmp_neg < 0:
                tmp_neg = 0
                
            if tmp_pos > tmp_neg:
                tmp_neg = 0
            else:
                if tmp_pos < tmp_neg:
                    tmp_pos = 0
                else:
                    tmp_pos = 0
                    tmp_neg = 0
            
            # Расчет True Range
            tr = max(high_price - low_price, abs(high_price - prev_close), abs(low_price - prev_close))
            
            # Расчет несглаженных DI значений
            raw_plus_di[i] = 100 * tmp_pos / tr if tr != 0 else 0
            raw_minus_di[i] = 100 * tmp_neg / tr if tr != 0 else 0
            
            # Сглаживание DI с помощью EMA
            pdi[i] = self.ExponentialMA(i, adx_period, pdi[i-1], raw_plus_di)
            ndi[i] = self.ExponentialMA(i, adx_period, ndi[i-1], raw_minus_di)
            
            # Расчет DX
            tmp = pdi[i] + ndi[i]
            tmp_buffer[i] = 100 * abs((pdi[i] - ndi[i]) / tmp) if tmp != 0 else 0
        
        # Расчет ADX (сглаженный DX)
        for i in range(1, len(high)):
            adx[i] = self.ExponentialMA(i, adx_period, adx[i-1], tmp_buffer)
        
        # Возвращаем ADX, +DI, -DI
        return adx, pdi, ndi
    
class RSI:
    def get_rsi_talib(self, symbol, timeframe, period=14, bars=1000):
        """
        RSI через TA-Lib
        """
        if not mt5.initialize():
            print("Ошибка инициализации MT5")
            return None
        
        try:
            rates = mt5.copy_rates_from_pos(symbol, timeframe, 0, bars)
            df = pd.DataFrame(rates)
            df['time'] = pd.to_datetime(df['time'], unit='s')
            
            # Конвертируем в numpy array
            close_prices = np.array(df['close'], dtype=float)
            
            # Расчет RSI через TA-Lib
            df['RSI'] = talib.RSI(close_prices, timeperiod=period)
            
            return df
            
        except Exception as e:
            print(f"Ошибка: {e}")
            return None