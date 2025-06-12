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
 
 
    def getCandles(self, symbol, timeFrame, candleCount):
        
        try:
            rates = mt5.copy_rates_from_pos(symbol, timeFrame, 0, candleCount)
            if rates is None:
                print(f"Не удалось получить данные для {symbol}")
                return None
                
            df = pd.DataFrame(rates)
            df['time'] = pd.to_datetime(df['time'], unit='s').dt.strftime('%Y-%m-%d %H:%M:%S')
            
            # Рассчитываем дополнительные показатели
            df['price_change'] = df['close'].diff()
            df['volume_ma'] = df['tick_volume'].rolling(window=20).mean()
            df['volume_ratio'] = df['tick_volume'] / df['volume_ma']
            
            # Формируем компактный набор данных для анализа
            return df[['time', 'open', 'high', 'low', 'close', 'tick_volume', 'volume_ma', 'volume_ratio']].to_dict('records')
        
        except Exception as e:
            print(f"Ошибка при получении данных для {symbol}: {str(e)}")
            return None       
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


    def CCI(self, period=14):
            """Рассчитывает CCI"""
            if self.df is None:
                print("Ошибка вычисления CCI")
                return None
            tp = (self.df['high'] + self.df['low'] + self.df['close']) / 3
            sma = tp.rolling(window=period).mean()
            mean_deviation = tp.rolling(window=period).apply(
                lambda x: np.mean(np.abs(x - np.mean(x)))
            )
            cci = ((tp - sma) / (0.015 * mean_deviation)).round(2)
            result = list(reversed(pd.Series(cci).dropna().tolist()))
            return result
        
    def Stochastic(self):
        """Рассчитывает стохастический осциллятор"""
        if self.df is None:
            print("Ошибка вычисления Stochastic")
            return None
        k_period = 5
        d_period = 3
        slowing = 3
        highs = self.df['high'].rolling(window=k_period).max()
        lows = self.df['low'].rolling(window=k_period).min()
        
        k = pd.Series(index=self.df.index)
        for i in range(slowing-1, len(self.df)):
            sum_low = sum(self.df['close'][i-slowing+1:i+1] - lows[i-slowing+1:i+1])
            sum_high = sum(highs[i-slowing+1:i+1] - lows[i-slowing+1:i+1])
            if sum_high == 0:
                k[i] = 100.0
            else:
                k[i] = (sum_low / sum_high) * 100
        
        d = k.rolling(window=d_period).mean().round(2)
        
        result_df = pd.DataFrame({
            'Stochastic_K': k.round(2),
            'Stochastic_D': d
        }).dropna()
        
        # Преобразуем в список словарей для вывода
        signal = []
        main = []
        for idx in reversed(result_df.index):
            signal.append(float(result_df.loc[idx, 'Stochastic_D']))
            main.append(float(result_df.loc[idx, 'Stochastic_K']))
        
        return signal,main
        
   
    def getData(self, symbol, count):
        if self.authorized:            
            if self.getHistoricalData(symbol,mt5.TIMEFRAME_H4,count):
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
                "price": price,
                #"sl": price - stopLoss * point,
                #"tp": price + takeProfit * point,
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
                #"sl": price + stopLoss * point,
                #"tp": price - takeProfit * point,
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
    
    def orderOpenByAI(self,symbol,type,comment,takeProfit,stopLoss):
        symbol_info = mt5.symbol_info(symbol) 
        if not symbol_info.visible:
            if not mt5.symbol_select(symbol,True):
                print("symbol_select({}}) failed, exit",symbol)        
        volume = 0.01
        deviation = 20
        price = mt5.symbol_info_tick(symbol).ask
        result = None
        if type == TargetType.LONG:            
            result = mt5.order_send({
                "action": mt5.TRADE_ACTION_DEAL,
                "symbol": symbol,
                "volume": volume,
                "type": mt5.ORDER_TYPE_BUY,
                "price": price,
                "sl": stopLoss,
                "tp": takeProfit,
                "deviation": deviation,
                "comment": str(comment),
                "type_time": mt5.ORDER_TIME_GTC,
                "type_filling": mt5.ORDER_FILLING_FOK
            })
        if type == TargetType.SHORT:            
            result = mt5.order_send({
                "action": mt5.TRADE_ACTION_DEAL,
                "symbol": symbol,
                "volume": volume,
                "type": mt5.ORDER_TYPE_SELL,
                "price": price,
                "sl": stopLoss,
                "tp": takeProfit,
                "deviation": deviation,
                "comment": str(comment),
                "type_time": mt5.ORDER_TIME_GTC,
                "type_filling": mt5.ORDER_FILLING_FOK
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
        volume = 0.5
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
    
    def orderOpenStoplimit(self,symbol,type,comment,price,takeProfit,stopLoss):
        symbol_info = mt5.symbol_info(symbol) 
        if not symbol_info.visible:
            if not mt5.symbol_select(symbol,True):
                print("symbol_select({}}) failed, exit",symbol)        
        volume = 0.01
        deviation = 20
        price = mt5.symbol_info_tick(symbol).ask
        result = None
        if type == TargetType.LONG:            
            result = mt5.order_send({
                "action": mt5.TRADE_ACTION_PENDING,
                "symbol": symbol,
                "volume": volume,
                "type": mt5.ORDER_TYPE_BUY_LIMIT,
                "sl": stopLoss,
                "tp": takeProfit,
                "price": price,                
                "deviation": deviation,
                "comment": str(comment),
                "type_time": mt5.ORDER_TIME_GTC,
                "type_filling": mt5.ORDER_FILLING_FOK,
            })
        if type == TargetType.SHORT:            
            result = mt5.order_send({
                "action": mt5.TRADE_ACTION_PENDING,
                "symbol": symbol,
                "volume": volume,
                "type": mt5.ORDER_TYPE_SELL_LIMIT,
                "sl": stopLoss,
                "tp": takeProfit,
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
        goods = [symbol.name for symbol in symbols if (symbol.spread <= spread and symbol.spread != 0 and symbol.name[0] != '#' and symbol.name[0] != 'X')  ]
        return goods
    
    def ServerTime(self, pair):
        tick = mt5.symbol_info_tick(pair)
        return pd.to_datetime(tick.time, unit='s')
