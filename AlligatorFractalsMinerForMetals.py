import datetime
from Support.mt5Connector import MT5Connector
from Support.appEnum import TargetType,IndicatorType, Settings
import time
import pandas as pd
import MetaTrader5 as mt5
from Support.anilizer import Alligator, AdaptiveMovingAverage
from logs.logger import Logger
from Support.account import Account

account = Account.accountDemo2
mt5Connector = MT5Connector(account)
alligator = Alligator()
logger = Logger()
settings = Settings()
AMA = AdaptiveMovingAverage()
X_VALUE_DICT = Settings.onlyMetalsM5
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

def checkOpen(pair, upFractal, downFractal, currentPrice):    
    serverTime = mt5Connector.ServerTime(pair)
    ticketShortSave = mt5Connector.symbolInPostions(pair,TargetType.SHORT,f"{IndicatorType.test}")
    ticketLongSave = mt5Connector.symbolInPostions(pair,TargetType.LONG,f"{IndicatorType.test}")

    if ticketShortSave or ticketLongSave:
        #Уже есть ордер по данной паре и данному индикатору
        return
    
    if currentPrice > upFractal:
        mt5Connector.orderOpenForAlligatorMain(pair, TargetType.LONG, f"{IndicatorType.test}")
        print(f"\n{"-" * 50}, \ntime:{serverTime} \npair: {pair} \nangle: {angle} \ncomment: Ордер LONG выставлен по условию, \n{"-" * 50}")
        #logger.saveToExcel(pair, "OPEN_LONG", 0, angle, "Ордер LONG выставлен по условию", Settings.filenameAlligator)
            
    if currentPrice < downFractal:        
        mt5Connector.orderOpenForAlligatorMain(pair, TargetType.SHORT, f"{IndicatorType.test}")
        print(f"\n{"-" * 50} \ntime:{serverTime} \npair: {pair} \nangle: {angle} \ncomment: Ордер SHORT выставлен по условию, \n{"-" * 50}")
        #logger.saveToExcel(pair, "OPEN_SHORT", 0,  angle, "Ордер SHORT выставлен по условию", Settings.filenameAlligator)

def checkClose(currentPrice, openPrice, jaw, pair):
    serverTime = mt5Connector.ServerTime(pair)
    
    if currentPrice > jaw > openPrice:
        
        ticket = mt5Connector.getTicket(pair,TargetType.SHORT,f"{IndicatorType.test}")
        
        if ticket:
            
            mt5Connector.orderClose(ticket, pair)
            print(f"\n{"-" * 50} \ntime:{serverTime} \npair: {pair} \ncurrentPrice: {currentPrice} \nteeth: {jaw} \nopenPrice: {openPrice} \ncomment: Ордер SHORT снят \n{"-" * 50}")
            logger.saveToExcel(pair, "CLOSE_SHORT",jaw, angle,  "Ордер SHORT снят", Settings.filenameAlligator)
            
    if currentPrice < jaw < openPrice:
        
        ticket = mt5Connector.getTicket(pair,TargetType.LONG,f"{IndicatorType.test}")
        
        if ticket:
            
            mt5Connector.orderClose(ticket, pair)
            print(f"\n{"-" * 50} \ntime:{serverTime} \npair: {pair} \ncurrentPrice: {currentPrice} \nteeth: {jaw} \nopenPrice: {openPrice} \ncomment: Ордер LONG снят \n{"-" * 50}")
            logger.saveToExcel(pair, "CLOSE_LONG",jaw, angle,  "Ордер LONG снят", Settings.filenameAlligator)


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

    pairs = X_VALUE_DICT.keys()
    timeFrame = mt5.TIMEFRAME_M5
    nextLogTime = logger.getNextLogTime(mt5Connector.ServerTime('XAUUSDrfd'))
    currentTime = mt5Connector.ServerTime('XAUUSDrfd')

    # Словарь для хранения предыдущих статусов
    previous_statuses = {pair: settings.dictPairTradingStop.get(pair, 0) for pair in pairs}
    
    while True:
        try:
            if not isTradingAllowed():
                print("Сейчас торговля запрещена (23:40-02:00 ежедневно или пятница 23:40 - понедельник 03:00)")
                time.sleep(60)  # Проверяем каждую минуту
                continue

            df = alligator.Df('XAUUSDrfd', timeFrame)
            isNewBar, lastCheckedTime = alligator.IsNewBar(df, lastCheckedTime, timeFrame)

            # Фильтруем пары: только те, у которых статус <= 3
            active_pairs = [pair for pair in pairs if settings.dictPairTradingStop.get(pair, 0) < 3]

            for pair in active_pairs:
                currentTime = mt5Connector.ServerTime('XAUUSDrfd')
                currentPrice = mt5.symbol_info_tick(pair).bid
                df = alligator.Df(pair, timeFrame)
                checkFlat = AMA.checkFlat(df, pair, X_VALUE_DICT)
                medianPrice,jaw,teeth,lips,openPrice = alligator.MainData(df) # Основные значения
                jawShifted,teethShifted,lipsShifted = alligator.ShiftedDataNew(jaw,teeth,lips,medianPrice) # Значения со сдвигом            
                lastJaw,lastTeeth,lastLips,prelastLips = alligator.LastData(pair,jawShifted,teethShifted,lipsShifted) # Последние значения   
                upper_fractal, lower_fractal = alligator.get_filtered_fractals(pair, timeFrame, lipsShifted, jawShifted)         
                angle, candleDiff,lipsVsTeethDiff = alligator.SupportData(lastLips, prelastLips, pair, X_VALUE_DICT, lastTeeth) #Вспомогательные значения
                high, low = getPreviousCandleHighLow(pair, timeFrame)

                # Сохраняем предыдущий статус
                previous_status = previous_statuses.get(pair, 0)
                current_status = settings.dictPairTradingStop.get(pair, 0)
                    
                if checkFlat["value"] == True:
                    settings.dictPairTradingStop[pair] = 0
                    current_status = 0
                    
                # Проверяем изменение статуса и отправляем сообщение
                if current_status != previous_status:
                    # Обновляем предыдущий статус
                    previous_statuses[pair] = current_status
                
                if checkFlat["value"] == False and settings.dictPairTradingStop[pair] == 0:

                    checkOpen( pair, upper_fractal['price'], lower_fractal['price'], currentPrice)
                checkClose(currentPrice, openPrice, lastJaw, pair) 


                    
                print(f"Пара: {pair} флэт: {checkFlat["value"]} угол: {checkFlat["angle"]} угол зубов:{angle} статус торговли: {settings.dictPairTradingStop[pair]}")
                #Обновляем время следующей записи

            print(f"AlligatorForMetals все в порядке, время:{mt5Connector.ServerTime('XAUUSDrfd')}")
        except Exception as e:
            print(f"Ошибка хуибка читай логи: {str(e)}")
            #logger.saveErrorsToExcel("alligatorForMetalls", str(e), Settings.filenameErrors)
                
        time.sleep(1)
        

    
        
