from mt5Connector import MT5Connector
import MetaTrader5 as mt5
from appEnum import TargetType,IndicatorType
import time
from datetime import  timedelta
import math
import pandas as pd
import numpy as np
from decimal import Decimal

account = {"login":2000099548,"password":"VeeDM6A$E1","server":"AlfaForexRU-Real"}
mt5Connector = MT5Connector(account)
LOG_FILE = "logger.txt"  # Файл для записи
INTERVAL_MINUTES = 10  # Интервал записи (10 минут)

def get_server_time(pair):
    tick = mt5.symbol_info_tick(pair)
    return pd.to_datetime(tick.time, unit='s')

def get_next_log_time(current_time):
    next_time = current_time.replace(second=0, microsecond=0) + \
                timedelta(minutes=INTERVAL_MINUTES - (current_time.minute % INTERVAL_MINUTES))
    return next_time

dictPairXvalue = {
    "EURUSDrfd": 100,
    "NZDUSDrfd": 110,
    "EURGBPrfd": 90,
    "USDCHFrfd": 120,
    "USDJPYrfd": 245,
    "EURCHFrfd": 100,
    "GBPUSDrfd": 180,
    "USDCADrfd": 240,
    "EURJPYrfd": 265,
    "AUDCADrfd": 100,
    "AUDUSDrfd": 105,
    "AUDJPYrfd": 150,
    "AUDCHFrfd": 85,
    "CHFJPYrfd": 210,
    "EURAUDrfd": 175,
    "GBPCHFrfd": 135,
    "EURCADrfd": 210,
    "GBPCADrfd": 160,
    "XAUUSDrfd": 1005,
    "GBPJPYrfd": 195,
    "XAGUSDrfd": 1230,
    "USDSGDrfd": 135
    
}

dictLipsCandleDiff = {
    "EURUSDrfd": 100,
    "NZDUSDrfd": 110,
    "EURGBPrfd": 90,
    "USDCHFrfd": 120,
    "USDJPYrfd": 245,
    "EURCHFrfd": 100,
    "GBPUSDrfd": 180,
    "USDCADrfd": 240,
    "EURJPYrfd": 265,
    "AUDCADrfd": 100,
    "AUDUSDrfd": 60,
    "AUDJPYrfd": 50,
    "AUDCHFrfd": 85,
    "CHFJPYrfd": 210,
    "EURAUDrfd": 175,
    "GBPCHFrfd": 135,
    "EURCADrfd": 210,
    "GBPCADrfd": 40,
    "XAUUSDrfd": 1000,
    "GBPJPYrfd": 195,
    "XAGUSDrfd": 200,
    "USDSGDrfd": 135
    
}

dictLipsTeethDiff = {
    
    "XAUUSDrfd": 150,
    "XAGUSDrfd": 170,
    "AUDJPYrfd": 15,
    "USDSGDrfd": 15,
    "AUDUSDrfd": 15
}

def calculate_arctan(currentLipsValue, previousLipsValue, pair, pairXvalue, degrees=True):
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

def count_decimal_places(pair):
    
    num = Decimal(str(mt5.symbol_info(pair).point))
    return  abs(num.as_tuple().exponent)
    
def getAlligatorVsCurrentCandelDiff(pair, alligatorValue):
    """Возвращает разницу между текущей ценой и индикатором аллигатор по модулю."""
    return abs(alligatorValue - mt5.symbol_info_tick(pair).bid)/ mt5.symbol_info(pair).point

def getLipsVsTeethDiff(pair, lips, teeth):
    """Возвращает разницу между текущей ценой и индикатором аллигатор по модулю."""
    return abs(lips - teeth)/ mt5.symbol_info(pair).point

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

def checkOpen(jaw, teeth, lips, angle, candlediff, pair):
    if mt5Connector.symbolInPostions(pair,TargetType.LONG,IndicatorType.ALLIGATOR_MAIN) or mt5Connector.symbolInPostions(pair,TargetType.SHORT,IndicatorType.ALLIGATOR_MAIN):
        #Уже есть ордер по данной паре и данному индикатору
        return
    if lips > teeth and lips > jaw and angle >= 10 and candlediff <= dictLipsCandleDiff.get(pair, 35):
        mt5Connector.orderOpenForAlligayorMain(pair,TargetType.LONG,IndicatorType.ALLIGATOR_MAIN)
        with open(LOG_FILE, "a") as f:
            f.write(f"\nordder LONG open \npair: {pair}, jaw: {last_jaw}, teeth: {last_teeth}, lips: {last_lips}, angle: {angle}, CandleDiff: {candleDiff}, time:{get_server_time(pair)}")

    if lips < teeth and lips < jaw and angle <= -10 and candlediff <= dictLipsCandleDiff.get(pair, 35):
        mt5Connector.orderOpenForAlligayorMain(pair,TargetType.SHORT,IndicatorType.ALLIGATOR_MAIN)
        with open(LOG_FILE, "a") as f:
            f.write(f"\nordder SHORT open \npair: {pair}, jaw: {last_jaw}, teeth: {last_teeth}, lips: {last_lips}, angle: {angle}, CandleDiff: {candleDiff}, time:{get_server_time(pair)}")
    
def checkClose(teeth,lips, angle, lipsVsTeethDiff, pair):
    if (lips < teeth and angle > 5 and lipsVsTeethDiff <= dictLipsTeethDiff.get(pair, 10)) or (lips > teeth):
        ticket = mt5Connector.getTicket(pair,TargetType.SHORT,IndicatorType.ALLIGATOR_MAIN)
        if ticket:
            mt5Connector.orderClose(ticket,pair)
            with open(LOG_FILE, "a") as f:
                f.write(f"\nordder SHORT closed \npair: {pair}, jaw: {last_jaw}, teeth: {last_teeth}, lips: {last_lips}, angle: {angle}, LipsVsTeethDiff: {lipsVsTeethDiff}, time:{get_server_time(pair)}")

    if (lips > teeth and angle < -5 and lipsVsTeethDiff <= dictLipsTeethDiff.get(pair, 10)) or (lips < teeth):
        ticket = mt5Connector.getTicket(pair,TargetType.LONG,IndicatorType.ALLIGATOR_MAIN)
        if ticket:
            mt5Connector.orderClose(ticket, pair)
            with open(LOG_FILE, "a") as f:
                f.write(f"\nordder LONG closed \npair: {pair}, jaw: {last_jaw}, teeth: {last_teeth}, lips: {last_lips}, angle: {angle}, LipsVsTeethDiff: {lipsVsTeethDiff}, time:{get_server_time(pair)}")


if __name__ == '__main__':
    #pairs = mt5Connector.getSymbols(50)
    pairs = dictPairXvalue.keys()
    last_log_time = None
    next_log_time = get_next_log_time(get_server_time('EURUSDrfd'))
    prev_bar_time = None
    
    while True:
        
        for pair in pairs:
            mt5Connector.getHistoricalData(pair,mt5.TIMEFRAME_H1,500)
            
            # Получаем данные цен (медианные цены HL/2)
            bars = mt5.copy_rates_from_pos(pair, mt5.TIMEFRAME_H1, 0, 500)
            if bars is None:
                print("Не удалось получить данные:", mt5.last_error())

            df = pd.DataFrame(bars)
            df['median_price'] = (df['high'] + df['low']) / 2  # Медианная цена (HL/2)

            
            # Рассчитываем линии Аллигатора
            df['jaw'] = smma(df['median_price'], 13)  # Челюсти (13)
            df['teeth'] = smma(df['median_price'], 8)   # Зубы (8)
            df['lips'] = smma(df['median_price'], 5)    # Губы (5)

            # Смещаем линии  (бары 3, 1, -1)
            df['jaw_shifted'] = df['jaw'].shift(3)
            df['teeth_shifted'] = df['teeth'].shift(1)
            df['lips_shifted'] = df['lips'].shift(-1)


            
            # Последние значения
            last_jaw = float(f"{df['jaw_shifted'].iloc[-2]:.{count_decimal_places(pair)}f}")
            last_teeth =  float(f"{df['teeth_shifted'].iloc[-2]:.{count_decimal_places(pair)}f}")
            last_lips = float(f"{df['lips_shifted'].iloc[-2]:.{count_decimal_places(pair)}f}")
            prelast_lips = float(f"{df['lips_shifted'].iloc[-3]:.{count_decimal_places(pair)}f}")
            angle = int(f"{calculate_arctan(last_lips,prelast_lips,pair,dictPairXvalue.get(pair, 100)):.0f}")
            candleDiff = int(f"{getAlligatorVsCurrentCandelDiff(pair,last_lips):.0f}")
            lipsVsTeethDiff = int(f"{getLipsVsTeethDiff(pair, last_lips, last_teeth):.0f}")
            
            current_time = get_server_time(pair)
        
            # Проверяем, нужно ли записывать время
            if current_time >= next_log_time:
                with open(LOG_FILE, "a") as f:
                    f.write(f"\npair: {pair}, jaw: {last_jaw}, teeth: {last_teeth}, lips: {last_lips}, angle: {angle}, CandleDiff: {candleDiff}, LipsVsTeethDiff: {lipsVsTeethDiff}, time:{get_server_time(pair)}")
            
            
           
            
            print(f"\npair: {pair}, jaw: {last_jaw}, teeth: {last_teeth}, lips: {last_lips}, angle: {angle}, CandleDiff: {candleDiff}, LipsVsTeethDiff: {lipsVsTeethDiff}, time:{get_server_time(pair)}")
            checkOpen(last_jaw, last_teeth, last_lips, angle, candleDiff, pair)    
            checkClose(last_teeth, last_lips, angle, lipsVsTeethDiff, pair)    
        # Обновляем время следующей записи

        next_log_time = get_next_log_time(current_time)
        time.sleep(10)

    
        
