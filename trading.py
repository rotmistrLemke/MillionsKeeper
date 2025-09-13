import MetaTrader5 as mt5
import pandas as pd
from settings import TargetType, Dictionary

dict = Dictionary()

class Trading:

    def orderOpen(self,symbol,type,comment):
        kamaIdicator = f"{symbol}_KAMA"
        alligatorIdicator = f"{symbol}_Alligator"
        symbol_info = mt5.symbol_info(symbol) 
        if not symbol_info.visible:
            if not mt5.symbol_select(symbol,True):
                print("symbol_select({}}) failed, exit",symbol)     
        volume = 0.04
        deviation = 20
        point = mt5.symbol_info(symbol).point
        price = mt5.symbol_info_tick(symbol).bid
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
            dict.symbolTradingStatus[symbol] = 2 
            dict.indicatorStatus[kamaIdicator] = 1
            dict.indicatorStatus[alligatorIdicator] = 1 
            print(f"Пара {symbol} Ордер {result.order} цена {result.price} статус торговли: {dict.symbolTradingStatus[symbol]}")
        
        return {"order":result.order,"price":result.price,"symbol":symbol,"targetType":type}
     
    def orderClose(self,orderTicket,symbol):
        result = mt5.Close(symbol=symbol,ticket=orderTicket)
        if not result:
            print(mt5.last_error())         
        else:   
            print(f"Пара {symbol} Ордер {orderTicket} успешно снят")        
      
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

    def ServerTime(self, symbol):
        tick = mt5.symbol_info_tick(symbol)
        return pd.to_datetime(tick.time, unit='s')

    
    def calculateStopLoss(self, symbol, priceCurrent, orderType):
        trailingStopValue = dict.dictPairTrailingStopValue.get(symbol, 200)
        if orderType == TargetType.LONG:
            stopLoss = priceCurrent - (trailingStopValue * mt5.symbol_info(symbol).point)         # type: ignore
        
        if orderType == TargetType.SHORT:
            stopLoss = priceCurrent + (trailingStopValue * mt5.symbol_info(symbol).point) # type: ignore

        return stopLoss # type: ignore

    def setStopLoss(self, ticket, new_sl , oldSl, orderType):

        if (orderType == TargetType.LONG and new_sl > oldSl) or  oldSl == 0.0:
            # Подготавливаем структуру для изменения
            request = {
                "action": mt5.TRADE_ACTION_SLTP,
                "position": ticket,
                "sl": new_sl
            }

            # Отправляем запрос на изменение
            result = mt5.order_send(request) # type: ignore
            
            if result.retcode == mt5.TRADE_RETCODE_DONE:
                print(f"Ордер {ticket} успешно изменён.")
                return True
            else:
                print(f"Ошибка изменения ордера {ticket}. Код ошибки:", result.retcode)
                return False
        elif (orderType == TargetType.SHORT and new_sl < oldSl) or  oldSl == 0.0:
            # Подготавливаем структуру для изменения
            request = {
                "action": mt5.TRADE_ACTION_SLTP,
                "position": ticket,
                "sl": new_sl
            }

            # Отправляем запрос на изменение
            result = mt5.order_send(request) # type: ignore
            
            if result.retcode == mt5.TRADE_RETCODE_DONE:
                print(f"Ордер {ticket} успешно изменён.")
                return True
            else:
                print(f"Ошибка изменения ордера {ticket}. Код ошибки:", result.retcode)
                return False
