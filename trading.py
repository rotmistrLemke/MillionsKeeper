import MetaTrader5 as mt5
import pandas as pd
from settings import TargetType, Dictionary
from indicators import ATR
import time
from market_data_cache import cache

dict = Dictionary()
atr = ATR()

class Trading:

    def orderOpen(self, symbol, type, maxVolume, comment, sl=0.0, tp=0.0):
        symbol_info = cache.get_symbol_info(symbol)
        if not symbol_info.visible:
            if not mt5.symbol_select(symbol, True):
                print("symbol_select({}}) failed, exit", symbol)
        volume = maxVolume
        deviation = 20
        price = mt5.symbol_info_tick(symbol).bid
        result = None
        if type == TargetType.LONG:
            request = {
                "action": mt5.TRADE_ACTION_DEAL,
                "symbol": symbol,
                "volume": volume,
                "type": mt5.ORDER_TYPE_BUY,
                "price": price,
                "deviation": deviation,
                "comment": str(comment),
                "type_time": mt5.ORDER_TIME_GTC,
                "type_filling": mt5.ORDER_FILLING_FOK,
            }
            if sl and sl > 0:
                request["sl"] = float(sl)
            if tp and tp > 0:
                request["tp"] = float(tp)
            result = mt5.order_send(request)
        if type == TargetType.SHORT:
            request = {
                "action": mt5.TRADE_ACTION_DEAL,
                "symbol": symbol,
                "volume": volume,
                "type": mt5.ORDER_TYPE_SELL,
                "price": price,
                "deviation": deviation,
                "comment": str(comment),
                "type_time": mt5.ORDER_TIME_GTC,
                "type_filling": mt5.ORDER_FILLING_FOK,
            }
            if sl and sl > 0:
                request["sl"] = float(sl)
            if tp and tp > 0:
                request["tp"] = float(tp)
            result = mt5.order_send(request)
        if not result:
            print(mt5.last_error())
        elif result.retcode != mt5.TRADE_RETCODE_DONE:
                print("4. order_send failed, retcode={}".format(result.retcode))
                print("   result", result)
        else:
            dict.symbolTradingStatus[symbol] = 1
            print(f"Пара {symbol} Ордер {result.order} цена {result.price} статус торговли: {dict.symbolTradingStatus[symbol]}")

        return {"order": result.order, "price": result.price, "symbol": symbol, "targetType": type}

    def orderClose(self, orderTicket, symbol):
        result = mt5.Close(symbol=symbol, ticket=orderTicket)
        if not result:
            print(mt5.last_error())
            return False
        print(f"Пара {symbol} Ордер {orderTicket} успешно снят")
        return True

    def getPositions(self):
        """Использует кэш вместо прямого вызова MT5."""
        return cache.get_positions()

    def symbolInPostions(self, symbol, typeOrder):
        positions = self.getPositions()
        for position in positions:
            if position.symbol == symbol and position.type == typeOrder:
                return True
        return False

    def serverTime(self, symbol):
        tick = mt5.symbol_info_tick(symbol)
        return pd.to_datetime(tick.time, unit='s')

    def calculateStopLoss(self, symbol, profit, atr, oldStopLossValue, volume):
        symbol_info = cache.get_symbol_info(symbol)

        if symbol_info is None:
            print(f"Не удалось получить информацию о символе {symbol}")
            return 0

        if profit > (2 * atr / symbol_info.point) * volume:
            newStopLossValue = profit - ((atr / symbol_info.point) * volume)
        elif profit > (atr / symbol_info.point) * volume:
            newStopLossValue = 0
        else:
            newStopLossValue = profit - ((2 * atr / symbol_info.point) * volume)

        if isinstance(oldStopLossValue, tuple):
            oldStopLossValue = oldStopLossValue[0] if oldStopLossValue else 0.0

        if isinstance(newStopLossValue, tuple):
            newStopLossValue = newStopLossValue[0] if newStopLossValue else 0.0

        newStopLossValue = float(newStopLossValue)
        oldStopLossValue = float(oldStopLossValue)

        if newStopLossValue > oldStopLossValue or oldStopLossValue == 0.0:
            dict.symbolStopLossValue[symbol] = newStopLossValue
            return newStopLossValue
        else:
            return oldStopLossValue

    def calculateStopLossOld(symbol, priceCurrent, orderType):
        atr_value = atr.calculate_atr(symbol, mt5.TIMEFRAME_H1)

        if orderType == TargetType.LONG:
            stopLoss = priceCurrent - (2 * atr_value.iloc[-1])

        if orderType == TargetType.SHORT:
            stopLoss = priceCurrent + (2 * atr_value.iloc[-1])

        return stopLoss

    def setStopLoss(ticket, new_sl, oldSl, orderType):
        """Оптимизировано: устранено дублирование LONG/SHORT веток."""
        should_update = False
        if orderType == TargetType.LONG and (new_sl > oldSl or oldSl == 0.0):
            should_update = True
        elif orderType == TargetType.SHORT and (new_sl < oldSl or oldSl == 0.0):
            should_update = True

        if not should_update:
            return False

        request = {
            "action": mt5.TRADE_ACTION_SLTP,
            "position": ticket,
            "sl": new_sl
        }

        result = mt5.order_send(request)  # type: ignore

        if result.retcode == mt5.TRADE_RETCODE_DONE:
            print(f"Ордер {ticket} успешно изменён.")
            return True
        else:
            print(f"Ошибка изменения ордера {ticket}. Код ошибки:", result.retcode)
            return False

    def calculatePipValue(self, symbol, volume, order_type):
        try:
            symbol_info = cache.get_symbol_info(symbol)
            if symbol_info is None:
                print(f"Не удалось получить информацию о символе {symbol}")
                return 0

            if order_type == mt5.ORDER_TYPE_BUY:
                price = mt5.symbol_info_tick(symbol).ask
            else:
                price = mt5.symbol_info_tick(symbol).bid

            contract_size = symbol_info.trade_contract_size
            pip_value = (symbol_info.point * contract_size * volume)

            profit_currency = symbol_info.currency_profit
            deposit_currency = symbol_info.currency_margin

            if profit_currency != deposit_currency:
                conversion_symbol = profit_currency + deposit_currency + 'rfd'
                conversion_info = mt5.symbol_info(conversion_symbol)

                if conversion_info is not None:
                    conversion_rate = mt5.symbol_info_tick(conversion_symbol).ask
                    pip_value *= conversion_rate
                else:
                    conversion_symbol = deposit_currency + profit_currency + 'rfd'
                    conversion_info = mt5.symbol_info(conversion_symbol)
                    if conversion_info is not None:
                        conversion_rate = mt5.symbol_info_tick(conversion_symbol).bid
                        pip_value /= conversion_rate

            return pip_value

        except Exception as e:
            print(f"Ошибка расчета стоимости пункта: {e}")
            return 0

    def calculateMaxVolumeWithMarginCheck(self, symbol, risk_percent, stop_loss_pips, order_type=None, margin_safety=1.1, max_retries=3):
        for attempt in range(max_retries):
            try:
                account_info = cache.get_account_info()
                if account_info is None:
                    print(f"Попытка {attempt + 1}/{max_retries}: Не удалось получить информацию о счете")
                    if attempt < max_retries - 1:
                        time.sleep(1)
                        continue
                    return 0

                active_symbols = [s for s in dict.symbolTradingStatus.keys()
                                if dict.symbolTradingStatus.get(s, 0) < 3]
                orders = self.getPositions()

                balance = account_info.balance
                equity = account_info.equity

                divisor = len(active_symbols) - len(orders)
                if divisor <= 0:
                    divisor = 1

                free_margin = account_info.margin_free / divisor

                if balance <= 0:
                    print(f"Попытка {attempt + 1}/{max_retries}: Баланс счета должен быть положительным")
                    if attempt < max_retries - 1:
                        time.sleep(1)
                        continue
                    return 0

                print(f"Баланс: {balance:.2f} $")
                print(f"Свободная маржа: {free_margin:.2f} $")

                risk_money = balance * (risk_percent / 100)
                print(f"Допустимый риск ({risk_percent}%): {risk_money:.2f} $")

                if order_type is None:
                    order_type = mt5.ORDER_TYPE_BUY

                pip_value_per_lot = self.calculatePipValue(symbol, 1, order_type)
                if pip_value_per_lot <= 0:
                    print(f"Попытка {attempt + 1}/{max_retries}: Не удалось рассчитать стоимость пункта")
                    if attempt < max_retries - 1:
                        time.sleep(1)
                        continue
                    return 0

                print(f"Стоимость 1 пункта для 1 лота: {pip_value_per_lot:.2f} $")

                stop_loss_cost = pip_value_per_lot * stop_loss_pips
                print(f"Стоимость SL {stop_loss_pips} пунктов для 1 лота: {stop_loss_cost:.2f} $")

                if stop_loss_cost <= 0:
                    print(f"Попытка {attempt + 1}/{max_retries}: Стоимость стоп-лосса должна быть положительной")
                    if attempt < max_retries - 1:
                        time.sleep(1)
                        continue
                    return 0

                volume_by_risk = risk_money / stop_loss_cost

                if order_type == mt5.ORDER_TYPE_BUY:
                    price = mt5.symbol_info_tick(symbol).ask
                else:
                    price = mt5.symbol_info_tick(symbol).bid

                margin_per_lot = mt5.order_calc_margin(order_type, symbol, 1.0, price)
                if margin_per_lot is None:
                    print(f"Попытка {attempt + 1}/{max_retries}: Не удалось рассчитать маржу на 1 лот")
                    if attempt < max_retries - 1:
                        time.sleep(1)
                        continue
                    return 0

                available_margin = free_margin / margin_safety
                volume_by_margin = available_margin / margin_per_lot

                print(f"Маржа на 1 лот: {margin_per_lot:.2f} $")
                print(f"Доступный объем по марже (с учетом {margin_safety*100}%): {volume_by_margin:.2f} лотов")

                max_volume = min(volume_by_risk, volume_by_margin)

                symbol_info = cache.get_symbol_info(symbol)
                if symbol_info:
                    max_volume = min(max_volume, symbol_info.volume_max)
                    max_volume = max(max_volume, symbol_info.volume_min)

                    if symbol_info.volume_step > 0:
                        max_volume = round(max_volume / symbol_info.volume_step) * symbol_info.volume_step

                final_margin_required = mt5.order_calc_margin(order_type, symbol, max_volume, price)
                margin_ratio = (free_margin / final_margin_required) if final_margin_required > 0 else 0

                print(f"Максимальный объем: {max_volume:.2f} лотов")
                print(f"Требуемая маржа: {final_margin_required:.2f} $")
                print(f"Коэффициент маржи: {margin_ratio:.2%}")

                if margin_ratio < margin_safety:
                    print(f"Внимание: коэффициент маржи ({margin_ratio:.2%}) ниже требуемого ({margin_safety:.2%})")
                    max_volume_safe = free_margin / (margin_per_lot * margin_safety)
                    if symbol_info:
                        max_volume_safe = min(max_volume_safe, symbol_info.volume_max)
                        max_volume_safe = max(max_volume_safe, symbol_info.volume_min)
                        if symbol_info.volume_step > 0:
                            max_volume_safe = round(max_volume_safe / symbol_info.volume_step) * symbol_info.volume_step

                    print(f"Безопасный объем: {max_volume_safe:.2f} лотов")
                    return max_volume_safe

                return max_volume

            except ZeroDivisionError as e:
                print(f"Попытка {attempt + 1}/{max_retries}: Ошибка деления на ноль: {e}")
                if attempt < max_retries - 1:
                    time.sleep(2)
                    continue
                return 0

            except Exception as e:
                print(f"Попытка {attempt + 1}/{max_retries}: Ошибка расчета максимального объема: {e}")
                if attempt < max_retries - 1:
                    time.sleep(2)
                    continue
                return 0

        return 0

    def checkMarginWithStopLoss(self, symbol, volume, order_type, stop_loss_pips, margin_safety=1.2):
        try:
            account_info = cache.get_account_info()
            if account_info is None:
                return False, 0

            free_margin = account_info.margin_free
            symbol_info = cache.get_symbol_info(symbol)

            if order_type == mt5.ORDER_TYPE_BUY:
                price = mt5.symbol_info_tick(symbol).ask
            else:
                price = mt5.symbol_info_tick(symbol).bid

            margin_required = mt5.order_calc_margin(order_type, symbol, volume, price)

            if margin_required is None:
                return False, 0

            pip_value = self.calculatePipValue(symbol, volume, order_type)
            potential_loss = pip_value * stop_loss_pips * volume

            total_required = margin_required + potential_loss
            margin_ratio = free_margin / total_required

            print(f"Свободная маржа: {free_margin:.2f} $")
            print(f"Требуемая маржа: {margin_required:.2f} $")
            print(f"Потенциальные убытки: {potential_loss:.2f} $")
            print(f"Общая потребность: {total_required:.2f} $")
            print(f"Коэффициент маржи: {margin_ratio:.2%}")

            return margin_ratio >= margin_safety, margin_ratio

        except Exception as e:
            print(f"Ошибка проверки маржи: {e}")
            return False, 0

    def calculateSafeTradeWithMargin(self, symbol, risk_percent, stop_loss_pips, order_type=mt5.ORDER_TYPE_BUY):
        print(f"\n=== Безопасный расчет для {symbol} ===")

        max_volume = self.calculateMaxVolumeWithMarginCheck(
            symbol, risk_percent, stop_loss_pips, order_type, margin_safety=1.2
        )

        if max_volume <= 0:
            print("Не удалось рассчитать безопасный объем")
            return 0

        margin_ok, margin_ratio = self.checkMarginWithStopLoss(
            symbol, max_volume, order_type, stop_loss_pips, margin_safety=1.2
        )

        if margin_ok:
            print(f"Безопасно можно открыть: {max_volume:.2f} лотов")
            print(f"Коэффициент маржи: {margin_ratio:.2%}")
        else:
            print(f"Небезопасно при объеме {max_volume:.2f} лотов")
            print(f"Коэффициент маржи: {margin_ratio:.2%}")

            symbol_info = cache.get_symbol_info(symbol)
            if symbol_info:
                min_volume = symbol_info.volume_min
                step = symbol_info.volume_step

                safe_volume = max_volume
                while safe_volume >= min_volume:
                    margin_ok, margin_ratio = self.checkMarginWithStopLoss(
                        symbol, safe_volume, order_type, stop_loss_pips, margin_safety=1.2
                    )
                    if margin_ok:
                        print(f"Безопасный объем: {safe_volume:.2f} лотов")
                        return safe_volume
                    safe_volume -= step

                print("Не удалось найти безопасный объем")

        return max_volume

    def calculateMaxMinValue(self, priceOpen, orderType, symbol, timeframe, volume):
        try:
            rates = mt5.copy_rates_from_pos(symbol, timeframe, 0, 2)
            if rates is None or len(rates) < 2:
                print(f"Не удалось получить данные для {symbol}")
                return None

            current_candle = rates[0]
            previous_candle = rates[1]

            tick = mt5.symbol_info_tick(symbol)
            if tick is None:
                return current_candle['high'], current_candle['low']

            current_ask = tick.ask
            current_bid = tick.bid
            current_price = max(current_ask, current_bid)
            current_low_price = min(current_ask, current_bid)

            current_high = max(
                current_candle['open'],
                current_candle['high'],
                current_price
            )

            current_low = min(
                current_candle['open'],
                current_candle['low'],
                current_low_price
            )

            if orderType == TargetType.LONG:
                maxMinValue = (current_high - priceOpen) * volume
                return maxMinValue

            if orderType == TargetType.SHORT:
                maxMinValue = (priceOpen - current_low) * volume
                return maxMinValue

        except Exception as e:
            print(f"Ошибка получения high текущей свечи: {e}")
            return None
