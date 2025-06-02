import numpy as np
from appEnum import IndicatorType,TargetType
import math
from decimal import Decimal
import pandas as pd
import MetaTrader5 as mt5


class ZeroIntersection:    
    def check(self, cciValues):
        if len(cciValues) < 2:
            return {"value": False}
                    
        current_value = cciValues[0]
        previous_value = cciValues[1]
        
        if current_value > 0 and current_value < 15 and previous_value < -10:
            return {"value": True, "target": TargetType.LONG}
        
        if current_value < 0 and current_value > -15 and previous_value > 10:
            return {"value": True, "target": TargetType.SHORT}
            
        return {"value": False}

class HundredIntersection:
    def check(self, cciValues):
        if len(cciValues) < 2:
            return {"value": False}
            
        current_value = cciValues[0]
        previous_value = cciValues[1]
        
        if current_value > 100 and current_value < 115 and previous_value < 90:
            return {"value": True, "target": TargetType.LONG}
        
        if current_value < -100 and current_value > -115 and previous_value > -90:
            return {"value": True, "target": TargetType.SHORT}
            
        return {"value": False}

class Extremum:    
    def __init__(self,settings):
        self.coefficientLimitCCI=settings["CCI_CoefficientLimit"]
        self.coefficientLimitStochastic= settings["Stochastic_CoefficientLimit"]
        self.CCI_ReferenceLimit = settings["CCI_ReferenceLimit"]
    def tryAngleCoefficient(self,current,prev):
        current = abs(current)
        prev = abs(prev)
        if current < prev:
            return (prev-current)/prev
        elif current > prev:
            return (current-prev)/current

    def cciReverse(self, cciValues, limit):
        if len(cciValues) < 2:
            return {"value": False}
            
        current_value = cciValues[0]
        previous_value = cciValues[1]
        coefficient = self.tryAngleCoefficient(current_value,previous_value)
        
        if current_value > limit and previous_value > current_value and coefficient>self.coefficientLimitCCI:
            return {"value": True, "target": TargetType.SHORT}
        
        if current_value < limit * -1 and previous_value < current_value and coefficient>self.coefficientLimitCCI:
            return {"value": True, "target": TargetType.LONG}
            
        return {"value": False}

    def stochasticReverse(self, stochasticValues):
        if len(stochasticValues) < 2:
            return {"value": False}
            
        current_value = stochasticValues[0]
        previous_value = stochasticValues[1]
        coefficient = self.tryAngleCoefficient(current_value,previous_value)

        if previous_value > current_value and coefficient > self.coefficientLimitStochastic:
            return {"value": True, "target": TargetType.SHORT}
        
        if previous_value < current_value and coefficient > self.coefficientLimitStochastic:
            return {"value": True, "target": TargetType.LONG}
            
        return {"value": False}

    def check(self, cciValues, stochasticValues):
        """Основной метод проверки условий"""
        cciReverse_result = self.cciReverse(cciValues, self.CCI_ReferenceLimit)
        stochasticReverse_result = self.stochasticReverse(stochasticValues)
        
        if cciReverse_result["value"] and stochasticReverse_result["value"]:
            if (cciReverse_result["target"] == TargetType.LONG and 
                stochasticReverse_result["target"] == TargetType.LONG):
                return {"value": True, "target": TargetType.LONG}
            
            if (cciReverse_result["target"] == TargetType.SHORT and 
                stochasticReverse_result["target"] == TargetType.SHORT):
                return {"value": True, "target": TargetType.SHORT}
        
        return {"value": False}
    
class Aligator:
    def __init__(self,mt5):
        self.mt5 = mt5    

    def checkOpen(self,jaw,teeth,lips,pair):
        if self.mt5.symbolInPostions(pair,TargetType.LONG,IndicatorType.ALLIGATOR) or mt5.symbolInPostions(pair,TargetType.SHORT,IndicatorType.ALLIGATOR):
            #Уже есть ордер по данной паре и данному индикатору
            return
        if lips > teeth and lips > jaw:
            self.mt5.orderOpenWithoutSLTP(pair,TargetType.LONG,IndicatorType.ALLIGATOR)
        if lips < teeth and lips < jaw:
            self.mt5.orderOpenWithoutSLTP(pair,TargetType.SHORT,IndicatorType.ALLIGATOR)        

    def checkClose(self,teeth,lips,pair):
        if lips > teeth:
            ticket = self.mt5.getTicket(pair,TargetType.SHORT,IndicatorType.ALLIGATOR)
            if ticket:
                self.mt5.orderClose(ticket,pair)
        if lips < teeth:
            ticket = self.mt5.getTicket(pair,TargetType.LONG,IndicatorType.ALLIGATOR)
            if ticket:
                self.mt5.orderClose(ticket,pair)
                
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
    
    def angle(self,currentLipsValue, previousLipsValue, pair, pairXvalue, degrees=True):
        """
        Вычисляет arctg(x) и возвращает угол в градусах или радианах.

        Параметры:
            x (float): Число, для которого вычисляется арктангенс.
            degrees (bool): Если True, возвращает угол в градусах, иначе в радианах.

        Возвращает:
            float: Угол в градусах или радианах.
        """
        x = (currentLipsValue - previousLipsValue) / mt5.symbol_info(pair).point
        angle_rad = math.atan2(x, pairXvalue/2)
        return math.degrees(angle_rad) if degrees else angle_rad
    
    def CountDecimalPlace(self, pair):    
        num = Decimal(str(mt5.symbol_info(pair).point))
        return  abs(num.as_tuple().exponent)
    
    def getAlligatorVsCurrentCandelDiff(self, pair, alligatorValue):
        """Возвращает разницу между текущей ценой и индикатором аллигатор по модулю."""
        return abs(alligatorValue - mt5.symbol_info_tick(pair).bid)/ mt5.symbol_info(pair).point
    
    def getLipsVsTeethDiff(self, pair, lips, teeth):
        """Возвращает разницу между текущей ценой и индикатором аллигатор по модулю."""
        return abs(lips - teeth)/ mt5.symbol_info(pair).point