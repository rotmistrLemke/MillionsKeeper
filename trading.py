import MetaTrader5 as mt5
import pandas as pd
from settings import TargetType, Dictionary

dict = Dictionary()

class Trading:

    def orderOpen(self, symbol, type, maxVolume, comment):
        kamaIdicator = f"{symbol}_KAMA"
        alligatorIdicator = f"{symbol}_Alligator"
        symbol_info = mt5.symbol_info(symbol) 
        if not symbol_info.visible:
            if not mt5.symbol_select(symbol,True):
                print("symbol_select({}}) failed, exit",symbol)     
        volume = maxVolume
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
     
    def orderClose(self, orderTicket, symbol):
        result = mt5.Close(symbol = symbol, ticket = orderTicket)
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

    def serverTime(self, symbol):
        tick = mt5.symbol_info_tick(symbol)
        return pd.to_datetime(tick.time, unit='s')
  
    def calculateStopLoss(self, symbol, profit, oldStopLossValue, volume):
        stopLossPoint = dict.symbolStopLossPoint.get(symbol, 200)
        newStopLossValue = profit - (stopLossPoint * volume * 100)
        if newStopLossValue > oldStopLossValue or oldStopLossValue == 0.0:
            return newStopLossValue

    def calculate_pip_value(self, symbol, volume, order_type):
        """
        Расчет стоимости одного пункта для валютной пары
        
        :param symbol: Название символа (например, "EURUSD")
        :param volume: Объем сделки в лотах
        :param order_type: Тип ордера (BUY или SELL)
        :return: Стоимость одного пункта в валюте депозита
        """
        try:
            # Получаем информацию о символе
            symbol_info = mt5.symbol_info(symbol)
            if symbol_info is None:
                print(f"Не удалось получить информацию о символе {symbol}")
                return 0
            
            # Получаем текущую цену
            if order_type == mt5.ORDER_TYPE_BUY:
                price = mt5.symbol_info_tick(symbol).ask
            else:
                price = mt5.symbol_info_tick(symbol).bid
            
            # Размер контракта (стандартно 100000 для валютных пар)
            contract_size = symbol_info.trade_contract_size
            
            # Стоимость пункта в валюте котировки
            pip_value = (contract_size *  symbol_info.point)
            
            # Если валюта прибыли отличается от валюты депозита
            profit_currency = symbol_info.currency_profit
            deposit_currency = symbol_info.currency_margin
            
            if profit_currency != deposit_currency:
                # Конвертируем в валюту депозита
                conversion_symbol = profit_currency + deposit_currency
                conversion_info = mt5.symbol_info(conversion_symbol)
                
                if conversion_info is not None:
                    conversion_rate = mt5.symbol_info_tick(conversion_symbol).ask
                    pip_value *= conversion_rate
                else:
                    # Пробуем обратную котировку
                    conversion_symbol = deposit_currency + profit_currency
                    conversion_info = mt5.symbol_info(conversion_symbol)
                    if conversion_info is not None:
                        conversion_rate = mt5.symbol_info_tick(conversion_symbol).bid
                        pip_value /= conversion_rate
            
            return pip_value
            
        except Exception as e:
            print(f"Ошибка расчета стоимости пункта: {e}")
            return 0
        
    def calculate_max_volume_with_margin_check(self, symbol, risk_percent, stop_loss_pips, order_type=None, margin_safety=1.2):
        """
        Расчет максимального объема ордера с проверкой маржинальных требований (120%+)
        
        :param symbol: Название символа
        :param risk_percent: Процент риска от депозита
        :param stop_loss_pips: Размер стоп-лосса в пунктах
        :param order_type: Тип ордера
        :param margin_safety: Коэффициент безопасности маржи (1.2 = 120%)
        :return: Максимальный объем в лотах
        """
        try:
            # Получаем информацию о счете
            account_info = mt5.account_info()
            if account_info is None:
                print("Не удалось получить информацию о счете")
                return 0
            
            balance = account_info.balance
            equity = account_info.equity
            free_margin = account_info.margin_free
            
            if balance <= 0:
                print("Баланс счета должен быть положительным")
                return 0
            
            print(f"Баланс: ₽{balance:.2f}")
            print(f"Свободная маржа: {free_margin:.2f} ₽")
            
            # Рассчитываем допустимый риск в деньгах
            risk_money = balance * (risk_percent / 100)
            print(f"Допустимый риск ({risk_percent}%): {risk_money:.2f} ₽")
            
            # Если тип ордера не указан, определяем его
            if order_type is None:
                order_type = mt5.ORDER_TYPE_BUY
            
            # Рассчитываем стоимость одного пункта
            pip_value_per_lot = self.calculate_pip_value(symbol, 0.01, order_type) * 100
            if pip_value_per_lot <= 0:
                print("Не удалось рассчитать стоимость пункта")
                return 0
            
            print(f"Стоимость 1 пункта для 1 лота: {pip_value_per_lot:.2f} ₽")
            
            # Рассчитываем стоимость стоп-лосса для 1 лота
            stop_loss_cost = pip_value_per_lot * stop_loss_pips
            print(f"Стоимость SL {stop_loss_pips} пунктов для 1 лота: {stop_loss_cost:.2f} ₽")
            
            if stop_loss_cost <= 0:
                print("Стоимость стоп-лосса должна быть положительной")
                return 0
            
            # Рассчитываем объем на основе риска
            volume_by_risk = risk_money / stop_loss_cost
            
            # Получаем текущую цену для расчета маржи
            if order_type == mt5.ORDER_TYPE_BUY:
                price = mt5.symbol_info_tick(symbol).ask
            else:
                price = mt5.symbol_info_tick(symbol).bid
            
            # Рассчитываем максимальный объем на основе маржи с учетом безопасности 120%
            margin_per_lot = mt5.order_calc_margin(order_type, symbol, 1.0, price)
            if margin_per_lot is None:
                print("Не удалось рассчитать маржу на 1 лот")
                return 0
            
            # Доступная маржа с учетом требования 120%
            available_margin = free_margin / margin_safety
            volume_by_margin = (available_margin / margin_per_lot) / (pip_value_per_lot / 100)
            
            print(f"Маржа на 1 лот: {margin_per_lot:.2f} ₽")
            print(f"Доступный объем по марже (с учетом {margin_safety*100}%): {volume_by_margin:.2f} лотов")
            
            # Берем минимальный объем из двух ограничений (риск и маржа)
            max_volume = min(volume_by_risk, volume_by_margin)
            
            # Ограничиваем объем минимальным и максимальным допустимым значением
            symbol_info = mt5.symbol_info(symbol)
            if symbol_info:
                max_volume = min(max_volume, symbol_info.volume_max)
                max_volume = max(max_volume, symbol_info.volume_min)
                
                # Округляем до шага объема
                if symbol_info.volume_step > 0:
                    max_volume = round(max_volume / symbol_info.volume_step) * symbol_info.volume_step
            
            # Проверяем финальные маржинальные требования
            final_margin_required = mt5.order_calc_margin(order_type, symbol, max_volume, price)
            margin_ratio = (free_margin / final_margin_required) if final_margin_required > 0 else 0
            
            print(f"Максимальный объем: {max_volume:.2f} лотов")
            print(f"Требуемая маржа: {final_margin_required:.2f} ₽")
            print(f"Коэффициент маржи: {margin_ratio:.2%}")
            
            if margin_ratio < margin_safety:
                print(f"⚠️  Внимание: коэффициент маржи ({margin_ratio:.2%}) ниже требуемого ({margin_safety:.2%})")
                # Уменьшаем объем до соблюдения требования
                max_volume_safe = free_margin / (margin_per_lot * margin_safety)
                if symbol_info:
                    max_volume_safe = min(max_volume_safe, symbol_info.volume_max)
                    max_volume_safe = max(max_volume_safe, symbol_info.volume_min)
                    if symbol_info.volume_step > 0:
                        max_volume_safe = round(max_volume_safe / symbol_info.volume_step) * symbol_info.volume_step
                
                print(f"Безопасный объем: {max_volume_safe:.2f} лотов")
                return max_volume_safe
            
            return max_volume
            
        except Exception as e:
            print(f"Ошибка расчета максимального объема: {e}")
            return 0

    def check_margin_with_sl(self, symbol, volume, order_type, stop_loss_pips, margin_safety=1.2):
        """
        Проверка маржинальных требований с учетом стоп-лосса (120%+)
        """
        try:
            account_info = mt5.account_info()
            if account_info is None:
                return False, 0
            
            free_margin = account_info.margin_free
            
            if order_type == mt5.ORDER_TYPE_BUY:
                price = mt5.symbol_info_tick(symbol).ask
                stop_price = price - (stop_loss_pips * mt5.symbol_info(symbol).point)
            else:
                price = mt5.symbol_info_tick(symbol).bid
                stop_price = price + (stop_loss_pips * mt5.symbol_info(symbol).point)
            
            # Рассчитываем требуемую маржу
            margin_required = mt5.order_calc_margin(order_type, symbol, volume, price)
            
            if margin_required is None:
                return False, 0
            
            # Рассчитываем потенциальные убытки
            pip_value = self.calculate_pip_value(symbol, volume, order_type)  * 100
            potential_loss = pip_value * stop_loss_pips * volume
            
            # Общая требуемая маржа с учетом потенциальных убытков
            total_required = margin_required + potential_loss
            
            # Коэффициент маржи с учетом безопасности
            margin_ratio = free_margin / total_required
            
            print(f"Свободная маржа: {free_margin:.2f} ₽")
            print(f"Требуемая маржа: {margin_required:.2f} ₽")
            print(f"Потенциальные убытки: {potential_loss:.2f} ₽")
            print(f"Общая потребность: {total_required:.2f} ₽")
            print(f"Коэффициент маржи: {margin_ratio:.2%}")
            
            return margin_ratio >= margin_safety, margin_ratio
            
        except Exception as e:
            print(f"Ошибка проверки маржи: {e}")
            return False, 0

    def calculate_safe_trade_with_margin(self, symbol, risk_percent, stop_loss_pips, order_type=mt5.ORDER_TYPE_BUY):
        """
        Комплексный расчет с учетом требования маржи 120%+
        """
        print(f"\n=== Безопасный расчет для {symbol} ===")
        
        # Рассчитываем максимальный объем с проверкой маржи
        max_volume = self.calculate_max_volume_with_margin_check(
            symbol, risk_percent, stop_loss_pips, order_type, margin_safety=1.2
        )
        
        if max_volume <= 0:
            print("Не удалось рассчитать безопасный объем")
            return 0
        
        # Дополнительная проверка маржи с учетом стоп-лосса
        margin_ok, margin_ratio = self.check_margin_with_sl(
            symbol, max_volume, order_type, stop_loss_pips, margin_safety=1.2
        )
        
        if margin_ok:
            print(f"✅ Безопасно можно открыть: {max_volume:.2f} лотов")
            print(f"✅ Коэффициент маржи: {margin_ratio:.2%}")
        else:
            print(f"❌ Небезопасно при объеме {max_volume:.2f} лотов")
            print(f"❌ Коэффициент маржи: {margin_ratio:.2%}")
            
            # Уменьшаем объем до безопасного уровня
            symbol_info = mt5.symbol_info(symbol)
            if symbol_info:
                min_volume = symbol_info.volume_min
                step = symbol_info.volume_step
                
                # Пробуем найти безопасный объем
                safe_volume = max_volume
                while safe_volume >= min_volume:
                    margin_ok, margin_ratio = self.check_margin_with_sl(
                        symbol, safe_volume, order_type, stop_loss_pips, margin_safety=1.2
                    )
                    if margin_ok:
                        print(f"✅ Безопасный объем: {safe_volume:.2f} лотов")
                        return safe_volume
                    safe_volume -= step
                
                print("❌ Не удалось найти безопасный объем")
        
        return max_volume
