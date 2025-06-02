import MetaTrader5 as mt5
import pandas as pd
import numpy as np
from enum import Enum
from appEnum import TargetType
from stock_indicators import indicators
from stock_indicators import Quote
from datetime import datetime




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
     
    
    def Alligator(self, jaw_period=13, teeth_period=8, lips_period=5, jaw_shift=5, teeth_shift=3, lips_shift=1):
        """Рассчитывает индикатор Alligator"""
        if self.df is None:
            print("Ошибка вычисления Alligator")
            return None
        
        # Преобразуем DataFrame в формат, подходящий для stock-indicators
        quotes = [
            Quote(
                datetime.fromtimestamp(d),  # Convert Unix timestamp to datetime
                o,h,l,c,v
            ) 
            for d,o,h,l,c,v 
            in zip(
                self.df['time'], 
                self.df['open'], 
                self.df['high'], 
                self.df['low'], 
                self.df['close'], 
                self.df['tick_volume']
            )
        ]
        
        # Рассчитываем Alligator
        from stock_indicators.indicators.common.enums import MAType
        results = indicators.get_alligator(
            quotes,
            jaw_periods=jaw_period,
            jaw_offset=jaw_shift,
            teeth_periods=teeth_period,
            teeth_offset=teeth_shift,
            lips_periods=lips_period,
            lips_offset=lips_shift,
        )
        
        # Преобразуем результаты в удобный формат
        jaw = []
        teeth = []
        lips = []
        
        for result in results:
            if result.jaw is not None and result.teeth is not None and result.lips is not None:
                jaw.append(result.jaw)
                teeth.append(result.teeth)
                lips.append(result.lips)
        
        jaw = list(reversed(jaw))
        teeth = list(reversed(teeth))
        lips = list(reversed(lips))
        # Возвращаем результаты в обратном порядке (как в других методах)
        return jaw,teeth,lips
   
    def getData(self, symbol, count):
        if self.authorized:            
            if self.getHistoricalData(symbol,mt5.TIMEFRAME_H1,count):
                cci = self.CCI()
                signal,main = self.Stochastic()
                jaw,teeth,lips = self.Alligator()

                return jaw,teeth,lips,cci,signal,main
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
