import numpy as np
import math
from decimal import Decimal
import pandas as pd
import MetaTrader5 as mt5
import talib
from settings import Dictionary
from market_data_cache import cache

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
        point = cache.get_symbol_info(symbol).point
        y = (currentLipsValue - previousLipsValue) / point
        angle_rad = math.atan2(y, pairXvalue/2)
        return int(f"{math.degrees(angle_rad):.0f}") if degrees else int(f"{angle_rad:.0f}")

    def CountDecimalPlace(self, symbol):
        num = Decimal(str(cache.get_symbol_info(symbol).point))
        return abs(num.as_tuple().exponent)

    def MainData(self, df):
        medianPrice = (df['high'] + df['low']) / 2
        openPrice = df['open'].iloc[-1]
        jaw = self.smma(medianPrice, 13)
        teeth = self.smma(medianPrice, 8)
        lips = self.smma(medianPrice, 5)
        return medianPrice, jaw, teeth, lips, openPrice

    def ShiftedData(self, jaw, teeth, lips, medianPrice):
        jaw = self.smma(medianPrice, 13)
        teeth = self.smma(medianPrice, 8)
        lips = self.smma(medianPrice, 5)
        jawShifted = jaw.shift(3)
        teethShifted = teeth.shift(1)
        lipsShifted = lips.shift(-1)
        return jawShifted, teethShifted, lipsShifted

    def LastData(self, symbol, jawShifted, teethShifted, lipsShifted):
        countDecimalPlace = self.CountDecimalPlace(symbol)
        lastJaw = float(f"{jawShifted.iloc[-2]:.{countDecimalPlace}f}")
        lastTeeth = float(f"{teethShifted.iloc[-2]:.{countDecimalPlace}f}")
        lastLips = float(f"{lipsShifted.iloc[-2]:.{countDecimalPlace}f}")
        prelastLips = float(f"{lipsShifted.iloc[-3]:.{countDecimalPlace}f}")
        return lastJaw, lastTeeth, lastLips, prelastLips

    def SupportData(self, lastLips, prelastLips, symbol, dictPairXvalue):
        angle = self.angle(lastLips, prelastLips, symbol, dictPairXvalue.get(symbol, 100))
        return angle

    def IsNewBar(self, df, lastCheckedTime, timeFrame):
        new_time = df['time'].iloc[0]
        if lastCheckedTime is None:
            print(f"Первая свеча {timeFrame}, запоминаем время")
            return True, new_time
        if new_time != lastCheckedTime:
            print(f"Обнаружена новая свеча {timeFrame}!")
            return True, new_time
        return False, lastCheckedTime

    def Df(self, symbol, timeFrame):
        """Получает DataFrame через кэш вместо прямого вызова MT5."""
        return cache.get_rates(symbol, timeFrame)

class AdaptiveMovingAverage:

    def checkFlat(self, df, symbol, dictPairXvalue, atr_value=None):
        close_prices = df['close'].values
        ama = talib.KAMA(close_prices, timeperiod=10)
        df = df.copy()
        df['AMA'] = ama
        last_two = df[['AMA']].tail(2)

        lastAma = last_two['AMA'].iloc[-1]
        prevAma = last_two['AMA'].iloc[-2]

        # Используем переданное значение ATR вместо повторного расчёта
        if atr_value is None:
            atr_obj = ATR()
            atr_series = atr_obj.calculate_atr(symbol, mt5.TIMEFRAME_H1)
            x = atr_series.iloc[-1]
        else:
            x = atr_value

        point = cache.get_symbol_info(symbol).point
        y = (lastAma - prevAma) / point
        angle_rad = math.atan2(y, x/2)
        angle = int(f"{math.degrees(angle_rad):.0f}")

        if angle > 4 or angle < -4:
            return {"value": False, "angle": angle}
        else:
            return {"value": True, "angle": angle}

class BullsBearsPower:
    def get_bulls_bears_power(self, symbol, timeframe, period=13, bars=100):
        try:
            df = cache.get_rates(symbol, timeframe, bars + period)
            if df is None:
                print(f"Не удалось получить данные для {symbol}")
                return None, None

            df = df.copy()
            df['ema'] = df['close'].ewm(span=period, adjust=False).mean()
            df['bulls_power'] = df['high'] - df['ema']
            df['bears_power'] = df['low'] - df['ema']

            current_bulls = df['bulls_power'].iloc[-1]
            current_bears = df['bears_power'].iloc[-1]

            return current_bulls, current_bears

        except Exception as e:
            print(f"Ошибка расчета Bulls/Bears Power: {e}")
            return None, None

class MACD:
    def calculate_macd_manual(self, symbol, timeframe, fast_ema=12, slow_ema=26, signal_period=9):
        try:
            data_length = slow_ema + signal_period + 10
            df = cache.get_rates(symbol, timeframe, 100)
            if df is None or len(df) < data_length:
                print(f"Недостаточно данных для расчета MACD {symbol}")
                return None, None, None

            closes = df['close'].tolist()

            def calculate_ema(prices, period):
                alpha = 2 / (period + 1)
                ema = [prices[0]]
                for i in range(1, len(prices)):
                    ema_value = alpha * prices[i] + (1 - alpha) * ema[i-1]
                    ema.append(ema_value)
                return ema

            ema_fast = calculate_ema(closes, fast_ema)
            ema_slow = calculate_ema(closes, slow_ema)

            macd_line = [ema_fast[i] - ema_slow[i] for i in range(len(closes))]
            signal_line_vals = calculate_ema(macd_line, signal_period)

            signal_line = signal_line_vals[-1]
            hist_line = macd_line[-1]
            prev_hist_line = macd_line[-2]

            return hist_line, prev_hist_line, signal_line

        except Exception as e:
            print(f"Ошибка ручного расчета MACD: {e}")
            return None, None, None

    def MACD_signal(self, hist_line, prev_hist_line, signal_line):
        if hist_line > 0 and hist_line > prev_hist_line and hist_line > signal_line:
            return {'signal': 'BUY', 'hist_line': hist_line, 'prev_hist_line': prev_hist_line, 'signal_line': signal_line}
        elif hist_line < 0 and hist_line < prev_hist_line and hist_line < signal_line:
             return {'signal': 'SELL', 'hist_line': hist_line, 'prev_hist_line': prev_hist_line, 'signal_line': signal_line}
        else:
             return {'signal': 'NO_SIGNAL', 'hist_line': hist_line, 'prev_hist_line': prev_hist_line, 'signal_line': signal_line}

class MovingAverage:

    def sma(self, data, period):
        return data.rolling(window=period).mean()

    def ema(self, data, period, adjust=False):
        return data.ewm(span=period, adjust=adjust).mean()

    def wma(self, data, period):
        weights = np.arange(1, period + 1)
        return data.rolling(window=period).apply(lambda x: np.dot(x, weights) / weights.sum(), raw=True)

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

    def calculate_ma(self, data, period, ma_type='SMA'):
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

    def _get_angles(self, fast_ma, slow_ma, symbol, atr_value=None):
        """Вспомогательный метод для расчёта углов MA. Устраняет дублирование между ma_cross_signal и ma_critical_angle."""
        if len(fast_ma) < 2 or len(slow_ma) < 2:
            return None

        current_fast = fast_ma.iloc[-1]
        previous_fast = fast_ma.iloc[-2]
        current_slow = slow_ma.iloc[-1]
        previous_slow = slow_ma.iloc[-2]

        if pd.isna(current_fast) or pd.isna(previous_fast) or pd.isna(current_slow) or pd.isna(previous_slow):
            return None

        # Используем переданное значение ATR вместо создания нового объекта
        if atr_value is None:
            atr_obj = ATR()
            atr_series = atr_obj.calculate_atr(symbol, mt5.TIMEFRAME_H1)
            x = atr_series.iloc[-1] / cache.get_symbol_info(symbol).point
        else:
            val = atr_value.iloc[-1] if isinstance(atr_value, pd.Series) else atr_value
            x = val / cache.get_symbol_info(symbol).point

        alligator = Alligator()
        angle_fast = alligator.angle(current_fast, previous_fast, symbol, x)
        angle_slow = alligator.angle(current_slow, previous_slow, symbol, x)

        return {
            'current_fast': current_fast,
            'previous_fast': previous_fast,
            'current_slow': current_slow,
            'previous_slow': previous_slow,
            'angle_fast': angle_fast,
            'angle_slow': angle_slow
        }

    def ma_cross_signal(self, fast_ma, slow_ma, symbol, atr_value=None):
        no_signal = {'signal': 'NO_SIGNAL', 'strength': 0, 'current_fast': 0, 'current_slow': 0, 'angle_fast': 0, 'angle_slow': 0}

        angles = self._get_angles(fast_ma, slow_ma, symbol, atr_value)
        if angles is None:
            return no_signal

        condition_diff_buy = angles['current_fast'] > angles['current_slow'] and angles['previous_fast'] < angles['previous_slow']
        condition_diff_sell = angles['current_fast'] < angles['current_slow'] and angles['previous_fast'] > angles['previous_slow']

        result = {
            'strength': abs(angles['current_fast'] - angles['current_slow']),
            'current_fast': angles['current_fast'],
            'current_slow': angles['current_slow'],
            'angle_fast': angles['angle_fast'],
            'angle_slow': angles['angle_slow']
        }

        if condition_diff_buy:
            result['signal'] = 'BUY'
        elif condition_diff_sell:
            result['signal'] = 'SELL'
        else:
            result['signal'] = 'NO_SIGNAL'

        return result

    def ma_critical_angle(self, fast_ma, slow_ma, symbol, atr_value=None):
        no_signal = {'signal': 'NO_SIGNAL', 'strength': 0, 'current_fast': 0, 'current_slow': 0, 'angle_fast': 0, 'angle_slow': 0}

        angles = self._get_angles(fast_ma, slow_ma, symbol, atr_value)
        if angles is None:
            return no_signal

        result = {
            'strength': abs(angles['current_fast'] - angles['current_slow']),
            'current_fast': angles['current_fast'],
            'current_slow': angles['current_slow'],
            'angle_fast': angles['angle_fast'],
            'angle_slow': angles['angle_slow']
        }

        if angles['angle_fast'] > 65:
            result['signal'] = 'BUY'
        elif angles['angle_fast'] < -65:
            result['signal'] = 'SELL'
        else:
            result['signal'] = 'NO_SIGNAL'

        return result

    def ma_simple_signal(self, fast_ma, slow_ma):
        if len(fast_ma) < 2 or len(slow_ma) < 2:
            return {'signal': 'NO_SIGNAL', 'strength': 0, 'current_fast': 0, 'current_slow': 0, 'angle_fast': 0, 'angle_slow': 0}

        current_fast = fast_ma.iloc[-1]
        current_slow = slow_ma.iloc[-1]

        if pd.isna(current_fast) or pd.isna(current_slow):
            return {'signal': 'NO_SIGNAL', 'strength': 0, 'current_fast': 0, 'current_slow': 0, 'angle_fast': 0, 'angle_slow': 0}

        result = {
            'strength': abs(current_fast - current_slow),
            'current_fast': current_fast,
            'current_slow': current_slow
        }

        if current_fast > current_slow:
            result['signal'] = 'BUY'
        elif current_fast < current_slow:
            result['signal'] = 'SELL'
        else:
            result['signal'] = 'NO_SIGNAL'

        return result

    def get_ma_for_symbol(self, symbol, timeframe, period, ma_type='EMA', price_type='close', bars=100):
        try:
            df = cache.get_rates(symbol, timeframe, bars + period)
            if df is None:
                print(f"Не удалось получить данные для {symbol}")
                return None

            if price_type == 'open':
                price_data = df['open']
            elif price_type == 'high':
                price_data = df['high']
            elif price_type == 'low':
                price_data = df['low']
            else:
                price_data = df['close']

            ma_values = self.calculate_ma(price_data, period, ma_type)
            return ma_values

        except Exception as e:
            print(f"Ошибка расчета скользящей средней для {symbol}: {e}")
            return None

class ATR:

    def calculate_atr(self, symbol, timeframe, bars=50):
        """Оптимизировано: запрашивает 50 баров вместо 500."""
        df = cache.get_rates(symbol, timeframe, bars)
        if df is None:
            return None
        high = df['high']
        low = df['low']
        close = df['close']
        prev_close = close.shift(1)
        tr = pd.concat([
            (high - low).abs(),
            (high - prev_close).abs(),
            (low - prev_close).abs()
        ], axis=1).max(axis=1)

        return tr.rolling(14).mean()

class ADX:

    def ExponentialMA(self, i, period, prev_value, values):
        if i == 0:
            return prev_value
        else:
            ema = (values[i] - prev_value) * 2 / (period + 1) + prev_value
            return ema

    def ADX(self, high, low, close, adx_period):
        pdi = [0] * len(high)
        ndi = [0] * len(high)
        adx = [0] * len(high)
        tmp_buffer = [0] * len(high)

        raw_plus_di = [0] * len(high)
        raw_minus_di = [0] * len(high)

        for i in range(1, len(high)):
            high_price = high[i]
            prev_high = high[i-1]
            low_price = low[i]
            prev_low = low[i-1]
            prev_close = close[i-1]

            tmp_pos = high_price - prev_high
            tmp_neg = prev_low - low_price

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

            tr = max(high_price - low_price, abs(high_price - prev_close), abs(low_price - prev_close))

            raw_plus_di[i] = 100 * tmp_pos / tr if tr != 0 else 0
            raw_minus_di[i] = 100 * tmp_neg / tr if tr != 0 else 0

            pdi[i] = self.ExponentialMA(i, adx_period, pdi[i-1], raw_plus_di)
            ndi[i] = self.ExponentialMA(i, adx_period, ndi[i-1], raw_minus_di)

            tmp = pdi[i] + ndi[i]
            tmp_buffer[i] = 100 * abs((pdi[i] - ndi[i]) / tmp) if tmp != 0 else 0

        for i in range(1, len(high)):
            adx[i] = self.ExponentialMA(i, adx_period, adx[i-1], tmp_buffer)

        return adx, pdi, ndi

    def ADX_signal(self, adx, pdi, ndi):
        if adx > 25 and pdi > ndi:
            return {'signal': 'BUY'}
        elif adx > 25 and ndi > pdi:
            return {'signal': 'SELL'}
        else:
            return {'signal': 'NO_SIGNAL'}

class RSI:
    def get_rsi_talib(self, symbol, timeframe, period=14, bars=100):
        """Оптимизировано: запрашивает 100 баров вместо 1000."""
        try:
            df = cache.get_rates(symbol, timeframe, bars)
            if df is None:
                return None

            df = df.copy()
            close_prices = np.array(df['close'], dtype=float)
            df['RSI'] = talib.RSI(close_prices, timeperiod=period)

            return df

        except Exception as e:
            print(f"Ошибка: {e}")
            return None

    def RSI_signal(self, rsi, prev_rsi, prev2_rsi):
        if 70 > rsi > 50 and rsi > prev_rsi and prev_rsi > prev2_rsi:
            return {'signal': 'BUY', 'prev_rsi': prev_rsi, 'rsi': rsi, 'prev2_rsi': prev2_rsi}
        elif 50 > rsi > 30 and rsi < prev_rsi and prev_rsi < prev2_rsi:
            return {'signal': 'SELL', 'prev_rsi': prev_rsi, 'rsi': rsi, 'prev2_rsi': prev2_rsi}
        else:
            return {'signal': 'NO_SIGNAL', 'prev_rsi': prev_rsi, 'rsi': rsi, 'prev2_rsi': prev2_rsi}

    def rsi_leave_extremum(self, rsi, prev_rsi):
        if (prev_rsi > 70 and rsi < 68) or (prev_rsi < 30 and rsi > 32):
            return True
        else:
            return False
