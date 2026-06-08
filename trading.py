import MetaTrader5 as mt5
import pandas as pd
from settings import TargetType, Dictionary
from trading_status import status
from indicators import ATR
import time
from market_data_cache import cache

dict = Dictionary()
atr = ATR()

class Trading:

    def orderOpen(self, symbol, type, maxVolume, comment, sl=0.0, tp=0.0, magic=0):
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
            if magic and int(magic) > 0:
                request["magic"] = int(magic)
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
            if magic and int(magic) > 0:
                request["magic"] = int(magic)
            result = mt5.order_send(request)
        if not result:
            print(mt5.last_error())
            return {"order": None, "price": None, "symbol": symbol, "targetType": type}
        if result.retcode != mt5.TRADE_RETCODE_DONE:
            print("4. order_send failed, retcode={}".format(result.retcode))
            print("   result", result)
        else:
            status.mark_open(symbol)
            print(f"Пара {symbol} Ордер {result.order} цена {result.price} статус торговли: {status.status_of(symbol)}")

        return {"order": result.order, "price": result.price, "symbol": symbol, "targetType": type}

    def orderClose(self, orderTicket, symbol, comment=""):
        """Закрытие через order_send, чтобы сохранить произвольный comment
        в MT5-истории (для отражения причины закрытия)."""
        positions = mt5.positions_get(ticket=orderTicket)
        if not positions:
            print(f"orderClose: позиция {orderTicket} не найдена")
            return False
        pos = positions[0]
        tick = mt5.symbol_info_tick(symbol)
        if tick is None:
            print(f"orderClose: нет котировки для {symbol}")
            return False
        close_type = mt5.ORDER_TYPE_SELL if pos.type == mt5.ORDER_TYPE_BUY else mt5.ORDER_TYPE_BUY
        price = tick.bid if close_type == mt5.ORDER_TYPE_SELL else tick.ask
        request = {
            "action":       mt5.TRADE_ACTION_DEAL,
            "symbol":       symbol,
            "volume":       pos.volume,
            "type":         close_type,
            "position":     pos.ticket,
            "price":        price,
            "deviation":    20,
            "magic":        int(getattr(pos, "magic", 0) or 0),
            "comment":      (comment or "")[:31],  # MT5 лимит ~31 символ
            "type_time":    mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_FOK,
        }
        result = mt5.order_send(request)
        if not result:
            print(mt5.last_error())
            return False
        if result.retcode != mt5.TRADE_RETCODE_DONE:
            print(f"orderClose failed retcode={result.retcode}")
            return False
        print(f"Пара {symbol} Ордер {orderTicket} закрыт ({comment or '—'})")
        return True

    def modifySL(self, ticket: int, symbol: str, new_sl: float,
                 new_tp: float | None = None) -> bool:
        """Изменяет SL (и опционально TP) открытой позиции.
        Учитывает trade_stops_level — если новый SL ближе к цене, чем
        брокер разрешает, возвращает False без вызова order_send.
        """
        positions = mt5.positions_get(ticket=ticket)
        if not positions:
            return False
        pos = positions[0]
        tick = mt5.symbol_info_tick(symbol)
        info = cache.get_symbol_info(symbol)
        if tick is None or info is None:
            return False
        point = float(getattr(info, 'point', 0.0) or 0.0)
        min_dist = float(getattr(info, 'trade_stops_level', 0) or 0) * point
        # Минимальная дистанция от текущей цены (bid для BUY, ask для SELL)
        ref_price = tick.bid if pos.type == mt5.ORDER_TYPE_BUY else tick.ask
        if pos.type == mt5.ORDER_TYPE_BUY and new_sl >= ref_price - min_dist:
            return False
        if pos.type == mt5.ORDER_TYPE_SELL and new_sl <= ref_price + min_dist:
            return False
        digits = int(getattr(info, 'digits', 5) or 5)
        request = {
            "action":   mt5.TRADE_ACTION_SLTP,
            "symbol":   symbol,
            "position": ticket,
            "sl":       round(float(new_sl), digits),
            "tp":       round(float(new_tp), digits) if new_tp else float(pos.tp or 0.0),
        }
        result = mt5.order_send(request)
        if not result or result.retcode != mt5.TRADE_RETCODE_DONE:
            return False
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

                active_symbols = status.active_symbols()
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
            potential_loss = pip_value * stop_loss_pips

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
