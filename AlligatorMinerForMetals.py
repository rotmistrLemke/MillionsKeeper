import datetime
from Support.mt5Connector import MT5Connector
from Support.appEnum import TargetType,IndicatorType, Settings
import time
import pandas as pd
import MetaTrader5 as mt5
from Support.anilizer import Alligator, AdaptiveMovingAverage
from logs.logger import Logger
from Support.account import Account

account = Account.accountDemo
mt5Connector = MT5Connector(account)
alligator = Alligator()
logger = Logger()
settings = Settings()
AMA = AdaptiveMovingAverage()
lastCheckedTime = None
checkFlat = None

def isTradingAllowed():
    now = datetime.datetime.now()
    current_time = now.time()
    current_weekday = now.weekday()  # 0-понедельник, 6-воскресенье
    
    # Проверка ежедневного запрета (23:40-02:00)
    daily_off_period = (
        datetime.time(23, 40) <= current_time or 
        current_time < datetime.time(2, 0))
    
    # Проверка пятничного запрета (23:40 пятницы - 02:00 понедельника)
    friday_off_period = (
        current_weekday == 4 and current_time >= datetime.time(23, 40)) or (
        current_weekday == 5) or (
        current_weekday == 6) or (
        current_weekday == 0 and current_time < datetime.time(3, 0))
    
    return not (daily_off_period or friday_off_period)


def checkOpenStrengthLine(angle, pair):    
    serverTime = mt5Connector.ServerTime(pair)
    point = mt5.symbol_info(pair).point        
    price = mt5.symbol_info_tick(pair).ask
    stopLossPoint = settings.dictPairTrailingStopValue.get(pair, 200)
    stopLossLongStrength = price - stopLossPoint * point
    stopLossShortStrength = price + stopLossPoint * point
    ticketShortStrength = mt5Connector.symbolInPostions(pair,TargetType.SHORT,f"{IndicatorType.ALLIGATOR_METALLS}")
    ticketLongStrength = mt5Connector.symbolInPostions(pair,TargetType.LONG,f"{IndicatorType.ALLIGATOR_METALLS}")

    if ticketShortStrength or ticketLongStrength:
        #Уже есть ордер по данной паре и данному индикатору
        return
    
    if angle > 15:
        mt5Connector.orderOpenForAlligator(pair, TargetType.LONG, f"{IndicatorType.ALLIGATOR_METALLS}", 0.20, stopLossLongStrength)
        print(f"\n{"-" * 50}, \ntime:{serverTime} \npair: {pair} \nangle: {angle} \ncomment: Ордер LONG выставлен по условию, \n{"-" * 50}")
        #logger.saveToExcel(pair, "OPEN_LONG", 0, angle, "Ордер LONG выставлен по условию", Settings.filenameAlligator)
            
    if angle < -15:        
        mt5Connector.orderOpenForAlligator(pair, TargetType.SHORT, f"{IndicatorType.ALLIGATOR_METALLS}", 0.20, stopLossShortStrength)
        print(f"\n{"-" * 50} \ntime:{serverTime} \npair: {pair} \nangle: {angle} \ncomment: Ордер SHORT выставлен по условию, \n{"-" * 50}")
        #logger.saveToExcel(pair, "OPEN_SHORT", 0,  angle, "Ордер SHORT выставлен по условию", Settings.filenameAlligator)

def checkOpenSaveLine(angle, pair, high,low):    
    serverTime = mt5Connector.ServerTime(pair)
    stopLossShortSave = high + (50 * mt5.symbol_info(pair).point)
    stopLossLongSave = low - (50 * mt5.symbol_info(pair).point)
    ticketShortSave = mt5Connector.symbolInPostions(pair,TargetType.SHORT,f"{IndicatorType.test}")
    ticketLongSave = mt5Connector.symbolInPostions(pair,TargetType.LONG,f"{IndicatorType.test}")

    if ticketShortSave or ticketLongSave:
        #Уже есть ордер по данной паре и данному индикатору
        return
    
    if angle > 15:
        mt5Connector.orderOpenForAlligator(pair, TargetType.LONG, f"{IndicatorType.test}", 0.05, stopLossLongSave)
        print(f"\n{"-" * 50}, \ntime:{serverTime} \npair: {pair} \nangle: {angle} \ncomment: Ордер LONG выставлен по условию, \n{"-" * 50}")
        #logger.saveToExcel(pair, "OPEN_LONG", 0, angle, "Ордер LONG выставлен по условию", Settings.filenameAlligator)
            
    if angle < -15:        
        mt5Connector.orderOpenForAlligator(pair, TargetType.SHORT, f"{IndicatorType.test}", 0.05, stopLossShortSave)
        print(f"\n{"-" * 50} \ntime:{serverTime} \npair: {pair} \nangle: {angle} \ncomment: Ордер SHORT выставлен по условию, \n{"-" * 50}")
        #logger.saveToExcel(pair, "OPEN_SHORT", 0,  angle, "Ордер SHORT выставлен по условию", Settings.filenameAlligator)

def checkPairTicket(pair):
        
    ticketShort = mt5Connector.getTicket(pair,TargetType.SHORT,f"{IndicatorType.ALLIGATOR_METALLS}")
    ticketLong = mt5Connector.getTicket(pair,TargetType.LONG,f"{IndicatorType.ALLIGATOR_METALLS}")
        
    if ticketShort or ticketLong:
        return True
    else:
        return False

def setStopLoss(pair, high, low):
        
    ticketShort = mt5Connector.getTicket(pair,TargetType.SHORT,f"{IndicatorType.test}")
    ticketLong = mt5Connector.getTicket(pair,TargetType.LONG,f"{IndicatorType.test}")
      
    if ticketShort:
        stopLoss = high + (50 * mt5.symbol_info(pair).point)
        request = {
            "action": mt5.TRADE_ACTION_SLTP,
            "position": ticketShort,
            "sl": stopLoss
        }

        # Отправляем запрос на изменение
        result = mt5.order_send(request)
        
        if result.retcode == mt5.TRADE_RETCODE_DONE:
            print(f"Ордер {ticketShort} успешно изменён.")
            return True
        else:
            print(f"Ошибка изменения ордера {ticketShort}. Код ошибки:", result.retcode)
            mt5Connector.orderClose(ticketShort, pair)

    if ticketLong:
            stopLoss = low - (50 * mt5.symbol_info(pair).point)
            request = {
                "action": mt5.TRADE_ACTION_SLTP,
                "position": ticketLong,
                "sl": stopLoss
            }

            # Отправляем запрос на изменение
            result = mt5.order_send(request)
            
            if result.retcode == mt5.TRADE_RETCODE_DONE:
                print(f"Ордер {ticketLong} успешно изменён.")
                return True
            else:
                print(f"Ошибка изменения ордера {ticketLong}. Код ошибки:", result.retcode)
                mt5Connector.orderClose(ticketLong, pair)
    else:
        return False

def getPreviousCandleHighLow(pair, timeframe, shift=1):
    """
    Возвращает максимум (High) предыдущей свечи.

    Параметры:
        symbol (str):   Название символа (например, "EURUSD").
        timeframe (int): Таймфрейм (например, mt5.TIMEFRAME_H1).
        shift (int):    Смещение (1 = предыдущая свеча, 2 = две свечи назад и т.д.).

    Возвращает:
        float: Значение High предыдущей свечи или None в случае ошибки.
    """

    
    # Получаем нужное количество свечей (shift + 1, чтобы учесть текущую свечу)
    rates = mt5.copy_rates_from_pos(pair, timeframe, 0, shift + 1)
    
    if rates is None or len(rates) < shift + 1:
        print(f"Не удалось получить данные для {pair} на таймфрейме {timeframe}")
        return None
    
    # Возвращаем High предыдущей свечи (shift=1 → rates[-2])
    return rates[-1 - shift]['high'], rates[-1 - shift]['low']

if __name__ == '__main__':

    pairs = Settings.onlyMetalsH1.keys()
    timeFrame = mt5.TIMEFRAME_M1
    nextLogTime = logger.getNextLogTime(mt5Connector.ServerTime('XAUUSDrfd'))
    currentTime = mt5Connector.ServerTime('XAUUSDrfd')
    
    while True:
        try:
            if not isTradingAllowed():
                print("Сейчас торговля запрещена (23:40-02:00 ежедневно или пятница 23:40 - понедельник 03:00)")
                time.sleep(60)  # Проверяем каждую минуту
                continue

            df = alligator.Df('XAUUSDrfd', timeFrame)
            isNewBar, lastCheckedTime = alligator.IsNewBar(df, lastCheckedTime, timeFrame)
            for pair in pairs:
                currentTime = mt5Connector.ServerTime('XAUUSDrfd')
                currentPrice = mt5.symbol_info_tick(pair).bid
                df = alligator.Df(pair, timeFrame)
                checkFlat = AMA.checkFlat(df, pair, Settings.onlyMetalsM1)
                medianPrice,jaw,teeth,lips,openPrice = alligator.MainData(df) # Основные значения
                jawShifted,teethShifted,lipsShifted = alligator.ShiftedData(jaw,teeth,lips,medianPrice) # Значения со сдвигом            
                lastJaw,lastTeeth,lastLips,prelastLips = alligator.LastData(pair,jawShifted,teethShifted,lipsShifted) # Последние значения            
                angle, candleDiff,lipsVsTeethDiff = alligator.SupportData(lastLips,prelastLips,pair,Settings.onlyMetalsM1,lastTeeth) #Вспомогательные значения
                high, low = getPreviousCandleHighLow(pair, timeFrame)
                            
                if checkFlat["value"] == True and settings.dictPairTradingStop[pair] != 2:
                    settings.dictPairTradingStop[pair] = 0
                
                if checkFlat["value"] == False and settings.dictPairTradingStop[pair] == 0:
                    #checkOpenStrengthLine(angle, pair)
                    checkOpenSaveLine(angle, pair, high, low)

                if isNewBar:
                    setStopLoss(pair, high, low)
                    settings.dictPairTradingStop[pair] = 1
                    
                print(f"Пара: {pair} флэт: {checkFlat["value"]} угол: {checkFlat["angle"]} угол зубов:{angle} статус торговли: {settings.dictPairTradingStop[pair]}")
                #Обновляем время следующей записи

            print(f"AlligatorForMetals все в порядке, время:{mt5Connector.ServerTime('XAUUSDrfd')}")
        except Exception as e:
            print(f"Ошибка хуибка читай логи: {str(e)}")
            logger.saveErrorsToExcel("alligatorForMetalls", str(e), Settings.filenameErrors)
            continue
                
        time.sleep(5)
        

    
        
