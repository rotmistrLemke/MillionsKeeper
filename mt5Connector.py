import MetaTrader5 as mt5
import pandas as pd
import numpy as np
from enum import Enum
from appEnum import TargetType, Settings
from stock_indicators import indicators
from stock_indicators import Quote
from datetime import datetime
from anilizer import Alligator

class MT5Connector:
    def __init__(self,account):
        self.rates = None
        self.df = None        
        if not mt5.initialize():
            print("Ошибка инициализации:", mt5.last_error())
            quit()        
        try:
            self.authorized = mt5.login(
                login=account["login"],
                password=account["password"],
                server=account["server"]
            )
        except Exception as e:
            print(f"Ошибка авторизации: {str(e)}")    
       
    def getHistoricalData(self, symbol, timeframe, count):
        """Получает исторические данные из MT5"""
        try:
            self.rates = mt5.copy_rates_from_pos(
                symbol,
                timeframe,
                0,
                count
            )
            self.df = pd.DataFrame(self.rates)
            return True
        except Exception as e:
            print(f"Ошибка при получении данных: {str(e)}")
            return False
    
    def alligatorData(self, pair):
        bars = mt5.copy_rates_from_pos(pair, mt5.TIMEFRAME_H1, 0, 500)
        if bars is None:
            print("Не удалось получить данные:", mt5.last_error())

        df = pd.DataFrame(bars)
        medianPrice = (df['high'] + df['low']) / 2  # Медианная цена (HL/2)
            
        # Рассчитываем линии Аллигатора
        jaw = Alligator.smma(medianPrice, 13)  # Челюсти (13)
        teeth = Alligator.smma(medianPrice, 8)   # Зубы (8)
        lips = Alligator.smma(medianPrice, 5)    # Губы (5)

        # Смещаем линии  (бары 3, 1, -1)
        jawShifted = jaw.shift(3)
        teethShifted = teeth.shift(1)
        lipsShifted = lips.shift(-1)
            
        # Последние значения
        countDecimalPlace = Alligator.CountDecimalPlace(pair)
        lastJaw = float(f"{jawShifted.iloc[-2]:.{countDecimalPlace}f}")
        lastTeeth =  float(f"{teethShifted.iloc[-2]:.{countDecimalPlace}f}")
        lastLips = float(f"{lipsShifted.iloc[-2]:.{countDecimalPlace}f}")
        prelastLips = float(f"{lipsShifted.iloc[-3]:.{countDecimalPlace}f}")
        angle = int(f"{Alligator.angle(lastLips,prelastLips,pair,Settings.dictPairXvalue.get(pair, 100)):.0f}")
        candleDiff = int(f"{Alligator.getAlligatorVsCurrentCandelDiff(pair,lastLips):.0f}")
        lipsVsTeethDiff = int(f"{Alligator.getLipsVsTeethDiff(pair, lastLips, lastTeeth):.0f}")
        
        return lastJaw, lastTeeth, lastLips, angle, candleDiff, lipsVsTeethDiff
   
    def getData(self, symbol, count):
        if self.authorized:            
            if self.getHistoricalData(symbol,mt5.TIMEFRAME_H1,count):
                cci = self.CCI()
                signal,main = self.Stochastic()

                return cci,signal,main
            else:
                print("Ошибка при получении данных")
        else:
            print("Ошибка авторизации")

    def orderOpen(self,symbol,type,comment,takeProfit,stopLoss):
        symbol_info = mt5.symbol_info(symbol) 
        if not symbol_info.visible:
            if not mt5.symbol_select(symbol,True):
                print("symbol_select({}}) failed, exit",symbol)        
        volume = 1.0
        deviation = 20
        point = mt5.symbol_info(symbol).point
        price = mt5.symbol_info_tick(symbol).ask
        result = None
        if type == TargetType.LONG:            
            result = mt5.order_send({
                "action": mt5.TRADE_ACTION_DEAL,
                "symbol": symbol,
                "volume": volume,
                "type": mt5.ORDER_TYPE_BUY,
                "price": price,
                "sl": price - stopLoss * point,
                "tp": price + takeProfit * point,
                "deviation": deviation,
                "comment": str(comment),
                "type_time": mt5.ORDER_TIME_GTC,
                "type_filling": mt5.ORDER_FILLING_FOK,
            })
        if type == TargetType.SHORT:            
            result = mt5.order_send({
                "action": mt5.TRADE_ACTION_DEAL,
                "symbol": symbol,
                "volume": volume,
                "type": mt5.ORDER_TYPE_SELL,
                "price": price,
                "sl": price + stopLoss * point,
                "tp": price - takeProfit * point,
                "deviation": deviation,
                "comment": str(comment),
                "type_time": mt5.ORDER_TIME_GTC,
                "type_filling": mt5.ORDER_FILLING_FOK,
            })
        if not result:
            print(mt5.last_error()) 

        elif result.retcode != mt5.TRADE_RETCODE_DONE:
                print("4. order_send failed, retcode={}".format(result.retcode))
                print("   result",result) 
        else:   
            print(f"Пара {symbol} Ордер {result.order} цена {result.price}")
        return {"order":result.order,"price":result.price,"symbol":symbol,"targetType":type}
    
    def orderOpenForAlligatorMain(self,symbol,type,comment):
        symbol_info = mt5.symbol_info(symbol) 
        if symbol == 'XAGUSDrfd':
            stopLossPoint = 6000
        else:
            stopLossPoint = 300
        if not symbol_info.visible:
            if not mt5.symbol_select(symbol,True):
                print("symbol_select({}}) failed, exit",symbol)        
        volume = 0.01
        deviation = 20
        point = mt5.symbol_info(symbol).point
        price = mt5.symbol_info_tick(symbol).ask
        result = None
        if type == TargetType.LONG:            
            result = mt5.order_send({
                "action": mt5.TRADE_ACTION_DEAL,
                "symbol": symbol,
                "volume": volume,
                "type": mt5.ORDER_TYPE_BUY,
                #"sl": price - stopLossPoint * point,
                "price": price,                
                "deviation": deviation,
                "comment": str(comment),
                "type_time": mt5.ORDER_TIME_GTC,
                "type_filling": mt5.ORDER_FILLING_FOK,
            })
        if type == TargetType.SHORT:            
            result = mt5.order_send({
                "action": mt5.TRADE_ACTION_DEAL,
                "symbol": symbol,
                "volume": volume,
                "type": mt5.ORDER_TYPE_SELL,
                #"sl": price + stopLossPoint * point,
                "price": price,                
                "deviation": deviation,
                "comment": str(comment),
                "type_time": mt5.ORDER_TIME_GTC,
                "type_filling": mt5.ORDER_FILLING_FOK,
            })
        if not result:
            print(mt5.last_error()) 

        elif result.retcode != mt5.TRADE_RETCODE_DONE:
                print("4. order_send failed, retcode={}".format(result.retcode))
                print("   result",result) 
        else:   
            print(f"Пара {symbol} Ордер {result.order} цена {result.price}")
        return {"order":result.order,"price":result.price,"symbol":symbol,"targetType":type}
    
    def orderOpenStoplimit(self,symbol,type,comment,stoplimit,expiration):
        symbol_info = mt5.symbol_info(symbol) 
        if symbol == 'XAGUSDrfd':
            stopLossPoint = 6000
        else:
            stopLossPoint = 300
        if not symbol_info.visible:
            if not mt5.symbol_select(symbol,True):
                print("symbol_select({}}) failed, exit",symbol)        
        volume = 0.01
        deviation = 20
        point = mt5.symbol_info(symbol).point
        price = mt5.symbol_info_tick(symbol).ask
        result = None
        if type == TargetType.LONG:            
            result = mt5.order_send({
                "action": mt5.TRADE_ACTION_DEAL,
                "symbol": symbol,
                "volume": volume,
                "type": mt5.ORDER_TYPE_BUY,
                "stoplimit": stoplimit,
                "expiration":expiration,
                #"sl": price - stopLossPoint * point,
                "price": price,                
                "deviation": deviation,
                "comment": str(comment),
                "type_time": mt5.ORDER_TIME_GTC,
                "type_filling": mt5.ORDER_FILLING_FOK,
            })
        if type == TargetType.SHORT:            
            result = mt5.order_send({
                "action": mt5.TRADE_ACTION_DEAL,
                "symbol": symbol,
                "volume": volume,
                "type": mt5.ORDER_TYPE_SELL,
                #"sl": price + stopLossPoint * point,
                "price": price,                
                "deviation": deviation,
                "comment": str(comment),
                "type_time": mt5.ORDER_TIME_GTC,
                "type_filling": mt5.ORDER_FILLING_FOK,
            })
        if not result:
            print(mt5.last_error()) 

        elif result.retcode != mt5.TRADE_RETCODE_DONE:
                print("4. order_send failed, retcode={}".format(result.retcode))
                print("   result",result) 
        else:   
            print(f"Пара {symbol} Ордер {result.order} цена {result.price}")
        return {"order":result.order,"price":result.price,"symbol":symbol,"targetType":type}
    
    def orderClose(self,orderTicket,symbol):
        result = mt5.Close(symbol=symbol,ticket=orderTicket)
        if not result:
            print(mt5.last_error())         
        else:   
            print(f"Пара {symbol} Ордер {orderTicket} успешно снят")        
        
    def getTicket(self,symbol,typeOrder,indicatorType):
        positions = self.getPositions()
        currentPositions = list(filter(lambda position: position.symbol == symbol and position.type == typeOrder and position.comment == str(indicatorType), positions))
        if len(currentPositions) > 0:
            return currentPositions[0].ticket
        return None
        
    def getPositions(self):
        orders = mt5.positions_get()
        if orders is None:
            print("No orders, error code={}".format(mt5.last_error()))       
       
        return orders

    def symbolInPostions(self,symbol,typeOrder,indicatorType):
        positions = self.getPositions()          
        currentPositions = list(filter(lambda position: position.symbol == symbol and position.type == typeOrder and position.comment == str(indicatorType), positions))  
        if (currentPositions):
            return True
        else:
            return False   
        
    def getSymbols(self,spread):
        symbols=mt5.symbols_get()
        goods = [symbol.name for symbol in symbols if (symbol.spread <= spread and symbol.spread != 0 and symbol.name[0] != '#') or symbol.name=='XAGUSDrfd'  ]
        return goods
    
    def ServerTime(self, pair):
        tick = mt5.symbol_info_tick(pair)
        return pd.to_datetime(tick.time, unit='s')
