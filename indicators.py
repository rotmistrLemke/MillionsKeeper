import numpy as np
import math
from decimal import Decimal
import pandas as pd
import MetaTrader5 as mt5
import talib
   
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
      
    