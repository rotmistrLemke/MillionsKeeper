import time
from datetime import datetime
from telegram import Update, ReplyKeyboardMarkup, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler
import asyncio
import threading
import MetaTrader5 as mt5
import datetime
from account import Account
from indicators import AdaptiveMovingAverage, Alligator, BullsBearsPower, MACD, MovingAverage, ADX, RSI, ATR
from trading import Trading
from settings import TargetType, IndicatorType, Dictionary
from logs.logger import Logger
from authenticator import MT5Auth
from history import History

# Конфигурация бота
TOKEN = Account.token
CHAT_ID = None  # Будет заполнено после /start
# Белый список разрешенных пользователей
ALLOWED_USERS = {
    "320526655": "Pavel Bogatyrev",  # Замените на ваш реальный Chat ID
    # "987654321": "Другой пользователь",  # Можно добавить других
}

account = Account.account
auth = MT5Auth(account)
auth.login()
trading = Trading()
history = History()
alligator = Alligator()
bbp = BullsBearsPower()
logger = Logger()
dict = Dictionary()
AMA = AdaptiveMovingAverage()
X_VALUE_DICT = Dictionary.symbolTradingStatus
lastCheckedTime = None
checkFlat = None
TIME_FRAME = mt5.TIMEFRAME_H1
macd = MACD()
atr = ATR()
adx = ADX()
rsi = RSI()
ma = MovingAverage()




class TradingBot:
    def __init__(self, trading, dict, alligator, ama):
        self.mt5 = trading
        self.dict = dict
        self.alligator = alligator
        self.ama = ama
        self.lastCheckedTime = None
        self.checkFlat = None
        self.bot_running = True
        self.application = None
        self.loop = asyncio.new_event_loop() 
        self.allowed_users = ALLOWED_USERS  

    def ensure_mt5_connection(self):
        """Проверяет и восстанавливает соединение с MT5"""
        try:
            if not mt5.initialize():
                print("MT5 не инициализирован, пытаемся переподключиться...")
                if self.connection_retries < self.max_retries:
                    self.connection_retries += 1
                    auth.login()
                    time.sleep(2)
                    return mt5.initialize()
                else:
                    print("Достигнуто максимальное количество попыток подключения")
                    return False
            
            # Проверяем активность соединения
            if not mt5.terminal_info():
                print("Соединение с MT5 разорвано, переподключаемся...")
                mt5.shutdown()
                time.sleep(1)
                auth.login()
                time.sleep(2)
                return mt5.initialize()
            
            self.connection_retries = 0
            return True
            
        except Exception as e:
            print(f"Ошибка при проверке соединения MT5: {e}")
            return False
        
    async def isUserAllowed(self, update: Update) -> bool:
        """Проверяет, есть ли пользователь в белом списке"""
        user_id = str(update.effective_user.id)
        if user_id in self.allowed_users:
            return True
        
        # Логируем попытку несанкционированного доступа
        user_info = f"User: {update.effective_user.first_name} {update.effective_user.last_name} (@{update.effective_user.username}) ID: {user_id}"
        print(f"🚫 Несанкционированный доступ: {user_info}")
        
        await update.message.reply_text(
            "🚫 Доступ запрещен!\n\n"
            "У вас нет прав для использования этого бота. "
            "Если вы должны иметь доступ, свяжитесь с администратором."
        )
        return False      

    def moneySaverLoop(self):

        while self.bot_running:
            try:
                # Проверяем соединение перед началом цикла
                if not trading_bot.ensure_mt5_connection():
                    print("Нет соединения с MT5, ждем...")
                    time.sleep(10)
                    continue
                
                if not trading_bot.isTradingAlowed():
                    print("Сейчас торговля запрещена (23:40-02:00 ежедневно или пятница 23:40 - понедельник 03:00)")
                    time.sleep(10)
                    continue
                
                orders = trading.getPositions()

                if len(orders) == 0:
                    continue
                else:
                    for order in orders:
                        order_dict = order._asdict()
                        volume = order_dict.get("volume", 0)
                        profit = order_dict.get("profit", 0)
                        ticketId = order_dict.get("ticket", 0)
                        symbol = order_dict.get("symbol", 0)
                        order_type = order_dict.get("type", 0)  # 0 = BUY, 1 = SELL
                        # Получаем сигнал от быстрой и медленной MA
                        fast_ma = ma.get_ma_for_symbol(symbol,TIME_FRAME, 8)
                        slow_ma = ma.get_ma_for_symbol(symbol, TIME_FRAME, 21)
                        signal_ma = ma.ma_simple_signal(fast_ma, slow_ma)
                        # Получаем сигнал от MACD
                        hist_line, prev_hist_line, signal_line = macd.calculate_macd_manual(symbol, TIME_FRAME)
                        MACD_signal = macd.MACD_signal(hist_line, prev_hist_line, signal_line)
                        # Получаем сигнал от ADX
                        df = alligator.Df(symbol, TIME_FRAME)
                        adx_values, plus_di_values, minus_di_values = adx.ADX(
                            df['high'].values,
                            df['low'].values, 
                            df['close'].values,
                            14
                        )
                        ADX_signal = adx.ADX_signal(adx_values[499], plus_di_values[499], minus_di_values[499])
                        # Получаем сигнал от RSI
                        rsi_value = rsi.get_rsi_talib(symbol, TIME_FRAME)
                        rsi_signal = rsi.RSI_signal(rsi_value['RSI'].iloc[-1], rsi_value['RSI'].iloc[-2], rsi_value['RSI'].iloc[-3])
                        
                        atr_calc = atr.calculate_atr(symbol, TIME_FRAME)
                        atr_value = atr_calc.iloc[-1]
                        
                        if signal_ma['signal'] == 'BUY' and MACD_signal['signal'] == 'BUY' and rsi_signal['signal'] == 'BUY':
                            sum_signal = 'BUY'
                        elif signal_ma['signal'] == 'SELL' and MACD_signal['signal'] == 'SELL' and rsi_signal['signal'] == 'SELL':
                            sum_signal = 'SELL'
                        else:
                            sum_signal = 'NO_SIGNAL'
                            
                        # Рассчитываем уровни Stop Loss
                        stop_loss_value = trading.calculateStopLoss(symbol, profit, atr_value, dict.symbolStopLossValue[symbol], volume)
                        dict.symbolStopLossValue[symbol] = stop_loss_value
                            
                        if dict.symbolTradingStatus[symbol] > 0:
                            continue

                                                
                        
                        
                        # Для LONG позиций (BUY)
                        if order_type == 0:  # BUY
                                
                                # Условия закрытия для LONG:
                                # 1. Текущий профит < Stop Loss  
                                # 2. Появился противоположный сигнал

                                if sum_signal == 'BUY':
                                    continue
                                
                                condition_signal = sum_signal == 'SELL'
                                condition_leave_extremum = rsi_value['RSI'].iloc[-1] < 65 and dict.symbolExtremumStatus[symbol] == 1

                                

                                if condition_signal or condition_leave_extremum:
                                    trading.orderClose(ticketId, symbol)
                                    dict.symbolStopLossValue[symbol] = 0.0
                                    dict.symbolExtremumStatus[symbol] = 0
                                        
                                    if CHAT_ID:
                                        reason = ""
                                        if condition_signal:
                                            reason = "Изменился сигнал"
                                        if condition_leave_extremum:
                                            reason = "Закрытие по выходу из зоны перекупленности"
                                        result = "😊" if profit > 0 else "😡"
                                            
                                        telegram_message = (
                                            f"{result} ЗАКРЫТИЕ LONG ПОЗИЦИИ\n\n"
                                            f"💵 Пара: {symbol}\n"
                                            f"💰 Профит: {profit:.2f}\n"
                                            f"🎯 Причина: {reason}\n"
                                            f"🎯 RSI: {rsi_value['RSI'].iloc[-1]}\n"
                                            
                                        )
                                        asyncio.run_coroutine_threadsafe(
                                            self.send_telegram_message(telegram_message),
                                            self.loop
                                        )
                        
                        # Для SHORT позиций (SELL)
                        elif order_type == 1:  # SELL
                           
                                # Условия закрытия для SHORT:
                                # 1. Текущий профит < Stop Loss  
                                # 2. Появился противоположный сигнал
                                
                                if sum_signal == 'SELL':
                                    continue
                                condition_signal = sum_signal == 'BUY'
                                condition_leave_extremum = rsi_value['RSI'].iloc[-1] > 35 and dict.symbolExtremumStatus[symbol] == 1

                                

                                if  condition_signal or condition_leave_extremum:
                                    trading.orderClose(ticketId, symbol)
                                    dict.symbolStopLossValue[symbol] = 0.0
                                    dict.symbolExtremumStatus[symbol] = 0

                                    if CHAT_ID:

                                        reason = ""
                                        if condition_signal:
                                            reason = "Изменился сигнал"
                                        if condition_leave_extremum:
                                            reason = "Закрытие по выходу из зоны перепроданности"
                                        result = "😊" if profit > 0 else "😡"
                                            
                                        telegram_message = (
                                            f"{result} ЗАКРЫТИЕ LONG ПОЗИЦИИ\n\n"
                                            f"💵 Пара: {symbol}\n"
                                            f"💰 Профит: {profit:.2f}\n"
                                            f"🎯 Причина: {reason}"
                                            f"🎯 RSI: {rsi_value['RSI'].iloc[-1]}\n"

                                        )
                                        asyncio.run_coroutine_threadsafe(
                                            self.send_telegram_message(telegram_message),
                                            self.loop
                                        )

            except Exception as e:
                print(f"Ошибка в moneySaver: {str(e)}")
                continue
            time.sleep(0.1)
        
    def isTradingAlowed(self):
        """Проверка разрешенного времени для торговли"""
        now = datetime.datetime.now()
        current_time = now.time()
        current_weekday = now.weekday()
        
        daily_off_period = (
            datetime.time(23, 40) <= current_time or 
            current_time < datetime.time(2, 0))
        
        friday_off_period = (
            current_weekday == 4 and current_time >= datetime.time(23, 40)) or (
            current_weekday == 5) or (
            current_weekday == 6) or (
            current_weekday == 0 and current_time < datetime.time(3, 0))
        
        return not (daily_off_period or friday_off_period)

    def checkOpen(self, symbol, signal, comment, atr, signal_ma, signal_critical_angle_ma, MACD_signal, rsi_signal):  
        active_symbols = [symbol for symbol in dict.symbolTradingStatus.keys() if dict.symbolTradingStatus.get(symbol, 0) < 3]  
        serverTime = trading.serverTime(symbol)

        if len(trading.getPositions()) == len(active_symbols):
            return

        if trading.symbolInPostions(symbol, TargetType.LONG) or trading.symbolInPostions(symbol, TargetType.SHORT):
            #Уже есть ордер по данной паре и данному индикатору
            return

        if signal == 'BUY':

            safeVolume = trading.calculateSafeTradeWithMargin(
                symbol, 
                risk_percent=90, 
                stop_loss_pips = 2 * atr / mt5.symbol_info(symbol).point, 
                order_type=TargetType.LONG
            )
            result = trading.orderOpen(symbol, TargetType.LONG, safeVolume, f"{comment}")
            
            print_message = f"\n{'-' * 50}, \ntime:{serverTime} \npair: {symbol} \ncomment: Ордер LONG выставлен по условию, \n{'-' * 50}"
            print(print_message)
            
            # Отправляем сообщение в Telegram
            if result and CHAT_ID:
                telegram_message = (
                    f"🎯 ОТКРЫТИЕ ПОЗИЦИИ\n\n"
                    f"🟦 Направление: LONG\n"
                    f"💵 Пара: {symbol}\n"
                    f"⏰ Время: {serverTime}\n"
                    f"🔄 Сигнал МА: {signal_ma['signal']}\n"
                    f"🔄 Угол fast_ma: {signal_critical_angle_ma['angle_fast']}\n\n"
                    f"🔄 Сигнал MACD: {MACD_signal['signal']}\n"
                    f"🔄 предыдущее значение: {MACD_signal['prev_hist_line']:.5f}\n"
                    f"🔄 текущее значение: {MACD_signal['hist_line']:.5f}\n"
                    f"🔄 сигнальнная линия: {MACD_signal['signal_line']:.5f}\n\n"
                    f"🔄 Сигнал RSI: {rsi_signal['signal']}\n"
                    f"🔄 Экстремум статус: {dict.symbolExtremumStatus.get(symbol, 0)}\n"
                    f"🔄 предыдущее значение: {rsi_signal['prev_rsi']:.5f}\n"
                    f"🔄 текущее значение: {rsi_signal['rsi']:.5f}"
                )
                asyncio.run_coroutine_threadsafe(
                    self.send_telegram_message(telegram_message),
                    self.loop
                )
                
        if signal == 'SELL':
            safeVolume = trading.calculateSafeTradeWithMargin(
                symbol, 
                risk_percent = 90, 
                stop_loss_pips = 2 * atr / mt5.symbol_info(symbol).point, 
                order_type=TargetType.SHORT
            )
            result = trading.orderOpen(symbol, TargetType.SHORT, safeVolume, f"{comment}")

            print_message = f"\n{'-' * 50} \ntime:{serverTime} \npair: {symbol} \ncomment: Ордер SHORT выставлен по условию, \n{'-' * 50}"
            print(print_message)
            
            # Отправляем сообщение в Telegram
            if result and CHAT_ID:
                telegram_message = (
                    f"🎯 ОТКРЫТИЕ ПОЗИЦИИ\n\n"
                    f"🟥 Направление: SHORT\n"
                    f"💵 Пара: {symbol}\n"
                    f"⏰ Время: {serverTime}\n"
                    f"🔄 Сигнал МА: {signal_ma['signal']}\n"
                    f"🔄 Угол fast_ma: {signal_critical_angle_ma['angle_fast']}\n\n"
                    f"🔄 Сигнал MACD: {MACD_signal['signal']}\n"
                    f"🔄 предыдущее значение: {MACD_signal['prev_hist_line']:.5f}\n"
                    f"🔄 текущее значение: {MACD_signal['hist_line']:.5f}\n"
                    f"🔄 сигнальнная линия: {MACD_signal['signal_line']:.5f}\n\n"
                    f"🔄 Сигнал RSI: {rsi_signal['signal']}\n"
                    f"🔄 Экстремум статус: {dict.symbolExtremumStatus.get(symbol, 0)}\n"
                    f"🔄 предыдущее значение: {rsi_signal['prev_rsi']:.5f}\n"
                    f"🔄 текущее значение: {rsi_signal['rsi']:.5f}"
                )
                asyncio.run_coroutine_threadsafe(
                    self.send_telegram_message(telegram_message),
                    self.loop
                )
            #logger.saveToExcel(symbol, "OPEN_SHORT", 0,  angle, "Ордер SHORT выставлен по условию", Settings.filenameAlligator)

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not await self.isUserAllowed(update):
            return
        global CHAT_ID
        CHAT_ID = str(update.effective_chat.id)
        
        keyboard = [
        ["🤖 Старт", "📊 Статус"],  # Было: "/status", "/positions"
        ["💼 Позиции", "⚙️ Управление торговлей"],  # Было: "/enable_trading", "/disable_trading"
        ["🕒 График", "📈 Инфо по паре"],  # Было: "/trading_schedule", "/pair_info"
        ["📊 История"]
        ]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        
        trading_status = "🟢 Разрешена" if self.isTradingAlowed() else "🔴 Запрещена"
        message = (
            f"🤖 Торговый бот Alligator Strategy\n\n"
            f"Текущий статус торговли: {trading_status}\n"
            f"Выберите действие:"
        )
        
        await update.message.reply_text(message, reply_markup=reply_markup)

    async def status(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not await self.isUserAllowed(update):
            return
        if CHAT_ID and str(update.effective_chat.id) != CHAT_ID:
            return
            
        symbols = X_VALUE_DICT.keys()
        trading_allowed = self.isTradingAlowed()
        
        message = (
            f"📊 Статус системы:\n\n"
            f"Общее время торговли: {'🟢 Разрешено' if trading_allowed else '🔴 Запрещено'}\n"
            f"Бот: {'🟢 Работает' if self.bot_running else '🔴 Остановлен'}\n\n"
            f"Статус по парам:\n"
        )
        
        for symbol in symbols:
            status = self.dict.symbolTradingStatus.get(symbol, 0)
            status_text = {
                0: "🟢 Торговля разрешена",
                1: "🟡 Торговля приостановлена",
                2: "🔴 Торговля заблокирована",
                3: "⚫️ Торговля выключена"
            }.get(status, "❓ Неизвестный статус")
            
            if status < 3:
                message += f"{symbol}: {status_text}\n"
        
        await update.message.reply_text(message)

    async def positions(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not await self.isUserAllowed(update):
            return
        if CHAT_ID and str(update.effective_chat.id) != CHAT_ID:
            return
            
        message = "📌 Открытые позиции:\n\n"
        has_positions = False
        
        try:
            # Получаем все открытые позиции сразу
            all_positions = mt5.positions_get()
            
            if all_positions is None:
                error = mt5.last_error()
                await update.message.reply_text(f"❌ Ошибка получения позиций: {error}")
                return
                
            if len(all_positions) == 0:
                await update.message.reply_text("Нет открытых позиций")
                return
                
            # Группируем позиции по символам
            positions_by_symbol = {}
            for position in all_positions:
                symbol = position.symbol
                if symbol not in positions_by_symbol:
                    positions_by_symbol[symbol] = []
                positions_by_symbol[symbol].append(position)
            
            # Формируем сообщение
            for symbol, positions in positions_by_symbol.items():
                message += f"🔹 {symbol}:\n"
                for pos in positions:
                    direction = "🟦 LONG" if pos.type == mt5.ORDER_TYPE_BUY else "🟥 SHORT"
                    # Получить сигнал пересечения быстрой и медленной MA
                    result = "😊 Прибыль" if pos.profit > 0 else "😡 Потери"
                    fast_ma = ma.get_ma_for_symbol(symbol,TIME_FRAME, 8)
                    slow_ma = ma.get_ma_for_symbol(symbol, TIME_FRAME, 21)
                    signal = ma.ma_cross_signal(fast_ma, slow_ma, symbol)
                    message += (
                        f"{direction}: {pos.volume} лот(ов)\n"
                        f"{result}: {pos.profit}\n"
                        f"🛑  Стоп-лосс значение: {dict.symbolStopLossValue[symbol]}\n"
                        f"📐 Угол быстрой МА:{signal['angle_fast']}\n"
                        "\n"

                    )
                has_positions = True
                
            if not has_positions:
                message = "Нет открытых позиций"
                
            await update.message.reply_text(message)
            
        except Exception as e:
            await update.message.reply_text(f"❌ Ошибка при получении позиций: {str(e)}")

    async def enable_trading(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not await self.isUserAllowed(update):
            return
        if CHAT_ID and str(update.effective_chat.id) != CHAT_ID:
            return
            
        for symbol in X_VALUE_DICT.keys():
            self.dict.symbolTradingStatus[symbol] = 0
            
        await update.message.reply_text("✅ Торговля разрешена для всех пар")

    async def disable_trading(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not await self.isUserAllowed(update):
            return
        """Меню выбора пар для изменения статуса"""
        if CHAT_ID and str(update.effective_chat.id) != CHAT_ID:
            return
        
        # Создаем инлайн-клавиатуру с парами
        keyboard = []
        symbols = list(X_VALUE_DICT.keys())
        
        # Разбиваем пары на строки по 2 кнопки
        for i in range(0, len(symbols), 2):
            row = []
            for symbol in symbols[i:i+2]:
                current_status = self.dict.symbolTradingStatus.get(symbol, 0)
                status_emoji = {0: "🟢", 1: "🟡", 2: "🔴", 3: "⚫️"}.get(current_status, "❓")
                row.append(InlineKeyboardButton(f"{status_emoji} {symbol}", callback_data=f"manage_{symbol}"))
            keyboard.append(row)
        
        # Добавляем кнопку для управления всеми парами
        keyboard.append([InlineKeyboardButton("🌐 Все пары", callback_data="manage_ALL")])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            "📊 Выберите пару для управления статусом торговли:",
            reply_markup=reply_markup
        )

    async def handle_manage_pair(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not await self.isUserAllowed(update):
            return
        """Обработка выбора пары для управления"""
        query = update.callback_query
        await query.answer()
        
        if query.data.startswith("manage_"):
            symbol = query.data.replace("manage_", "")
            
            if symbol == "ALL":
                # Меню для всех пар
                keyboard = [
                    [
                        InlineKeyboardButton("🟢 Разрешить все", callback_data="status_ALL_0"),
                        InlineKeyboardButton("🟡 Приостановить все", callback_data="status_ALL_1")
                    ],
                    [
                        InlineKeyboardButton("🔴 Заблокировать все", callback_data="status_ALL_2"),
                        InlineKeyboardButton("⚫️ Выключить все", callback_data="status_ALL_3")
                    ],
                    [InlineKeyboardButton("↩️ Назад к парам", callback_data="back_to_pairs")]
                ]
                
                await query.edit_message_text(
                    "🌐 Управление статусом для ВСЕХ пар:",
                    reply_markup=InlineKeyboardMarkup(keyboard)
                )
            else:
                # Меню для конкретной пары
                current_status = self.dict.symbolTradingStatus.get(symbol, 0)
                status_text = {0: "🟢 Разрешена", 1: "🟡 Приостановлена", 2: "🔴 Заблокирована", 3: "⚫️ Выключена"}.get(current_status, "❓ Неизвестно")
                
                keyboard = [
                    [
                        InlineKeyboardButton("🟢 Разрешить", callback_data=f"status_{symbol}_0"),
                        InlineKeyboardButton("🟡 Приостановить", callback_data=f"status_{symbol}_1")
                    ],
                    [
                        InlineKeyboardButton("🔴 Заблокировать", callback_data=f"status_{symbol}_2"),
                        InlineKeyboardButton("⚫️ Выключить", callback_data=f"status_{symbol}_3")
                    ],
                    [InlineKeyboardButton("↩️ Назад к парам", callback_data="back_to_pairs")]
                ]
                
                await query.edit_message_text(
                    f"📊 Управление парой {symbol}\nТекущий статус: {status_text}",
                    reply_markup=InlineKeyboardMarkup(keyboard)
                )

    async def handle_status_change(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not await self.isUserAllowed(update):
            return
        """Обработка изменения статуса"""
        query = update.callback_query
        await query.answer()
        
        if query.data.startswith("status_"):
            data_parts = query.data.split("_")
            symbol = data_parts[1]
            new_status = int(data_parts[2])
            
            status_names = {0: "🟢 РАЗРЕШЕНА", 1: "🟡 ПРИОСТАНОВЛЕНА", 2: "🔴 ЗАБЛОКИРОВАНА", 3: "⚫️ ВЫКЛЮЧЕНА"}
            
            if symbol == "ALL":
                # Изменяем статус для всех пар
                changed_count = 0
                for p in X_VALUE_DICT.keys():
                    old_status = self.dict.symbolTradingStatus.get(p, 0)
                    if old_status != new_status:
                        self.dict.symbolTradingStatus[p] = new_status
                        changed_count += 1
                
                message = f"✅ Статус изменен для {changed_count} пар: {status_names[new_status]}"
            else:
                # Изменяем статус для конкретной пары
                old_status = self.dict.symbolTradingStatus.get(symbol, 0)
                self.dict.symbolTradingStatus[symbol] = new_status
                
                message = f"✅ Пара {symbol}: {status_names[old_status]} → {status_names[new_status]}"
            
            await query.edit_message_text(message)
            
            # Отправляем уведомление об изменении
            notification = (
                f"📊 ИЗМЕНЕНИЕ СТАТУСА ТОРГОВЛИ\n\n"
                f"{message}\n"
                f"⏰ Время: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
                f"👤 Инициатор: {query.from_user.first_name}"
            )
            
            if CHAT_ID:
                asyncio.run_coroutine_threadsafe(
                    self.send_telegram_message(notification),
                    self.loop
                )

    async def handle_back_button(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not await self.isUserAllowed(update):
            return
        """Обработка кнопки назад"""
        query = update.callback_query
        await query.answer()
        
        if query.data == "back_to_pairs":
            # Возвращаемся к меню выбора пар
            keyboard = []
            symbols = list(X_VALUE_DICT.keys())
            
            for i in range(0, len(symbols), 2):
                row = []
                for symbol in symbols[i:i+2]:
                    current_status = self.dict.symbolTradingStatus.get(symbol, 0)
                    status_emoji = {0: "🟢", 1: "🟡", 2: "🔴", 3: "⚫️"}.get(current_status, "❓")
                    row.append(InlineKeyboardButton(f"{status_emoji} {symbol}", callback_data=f"manage_{symbol}"))
                keyboard.append(row)
            
            keyboard.append([InlineKeyboardButton("🌐 Все пары", callback_data="manage_ALL")])
            
            await query.edit_message_text(
                "📊 Выберите пару для управления статусом торговли:",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )

    async def trading_schedule(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not await self.isUserAllowed(update):
            return
        if CHAT_ID and str(update.effective_chat.id) != CHAT_ID:
            return
            
        message = (
            "🕒 График торговли:\n\n"
            "Ежедневные ограничения:\n"
            "🔴 23:40 - 02:00 (следующего дня) - торговля запрещена\n\n"
            "Еженедельные ограничения:\n"
            "🔴 Пятница 23:40 - Понедельник 03:00 - торговля запрещена\n\n"
            f"Текущий статус: {'🟢 Разрешена' if self.isTradingAlowed() else '🔴 Запрещена'}"
        )
        
        await update.message.reply_text(message)

    async def handle_pair_selection(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not await self.isUserAllowed(update):
            return
        """Обработка выбора пары из инлайн-клавиатуры"""
        query = update.callback_query
        await query.answer()
        
        if query.data.startswith("pair_"):
            symbol = query.data.replace("pair_", "")
            
            try:
                # Получаем сигнал от быстрой и медленной MA
                fast_ma = ma.get_ma_for_symbol(symbol,TIME_FRAME, 8)
                slow_ma = ma.get_ma_for_symbol(symbol, TIME_FRAME, 21)
                signal_ma = ma.ma_simple_signal(fast_ma, slow_ma)
                signal_critical_angle_ma = ma.ma_critical_angle(fast_ma, slow_ma, symbol)
                # Получаем сигнал от MACD
                hist_line, prev_hist_line, signal_line = macd.calculate_macd_manual(symbol, TIME_FRAME)
                MACD_signal = macd.MACD_signal(hist_line, prev_hist_line, signal_line)
                # Получаем сигнал от ADX
                df = alligator.Df(symbol, TIME_FRAME)
                adx_values, plus_di_values, minus_di_values = adx.ADX(
                    df['high'].values,
                    df['low'].values, 
                    df['close'].values,
                    14
                )
                ADX_signal = adx.ADX_signal(adx_values[499], plus_di_values[499], minus_di_values[499])
                # Получаем сигнал от RSI
                rsi_value = rsi.get_rsi_talib(symbol, TIME_FRAME)
                rsi_signal = rsi.RSI_signal(rsi_value['RSI'].iloc[-1], rsi_value['RSI'].iloc[-2], rsi_value['RSI'].iloc[-3])
                
                message = (
                    f"📈 Информация по паре {symbol}:\n\n"
                    f"🔄 Сигнал МА: {signal_ma['signal']}\n"
                    f"🔄 Угол fast_ma: {signal_critical_angle_ma['angle_fast']}\n\n"
                    f"🔄 Сигнал MACD: {MACD_signal['signal']}\n"
                    f"🔄 предыдущее значение: {MACD_signal['prev_hist_line']:.5f}\n"
                    f"🔄 текущее значение: {MACD_signal['hist_line']:.5f}\n"
                    f"🔄 сигнальнная линия: {MACD_signal['signal_line']:.5f}\n\n"
                    f"🔄 Сигнал RSI: {rsi_signal['signal']}\n"
                    f"🔄 Экстремум статус: {dict.symbolExtremumStatus.get(symbol, 0)}\n"
                    f"🔄 предыдущее значение: {rsi_signal['prev_rsi']:.5f}\n"
                    f"🔄 текущее значение: {rsi_signal['rsi']:.5f}"

                )
                
                await query.edit_message_text(message)
            except Exception as e:
                await query.edit_message_text(f"❌ Ошибка при получении информации по паре {symbol}: {str(e)}")

    async def pair_info(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not await self.isUserAllowed(update):
            return
        if CHAT_ID and str(update.effective_chat.id) != CHAT_ID:
            return
            
        # Создаем инлайн-клавиатуру с парами
        keyboard = []
        #symbols = list(X_VALUE_DICT.keys())
        symbols = [symbol for symbol in dict.symbolTradingStatus.keys() if dict.symbolTradingStatus.get(symbol, 0) < 3]
        
        # Разбиваем пары на строки по 2 кнопки
        for i in range(0, len(symbols), 2):
            row = []
            for symbol in symbols[i:i+2]:
                row.append(InlineKeyboardButton(symbol, callback_data=f"pair_{symbol}"))
            keyboard.append(row)
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            "📈 Выберите пару для получения информации:",
            reply_markup=reply_markup
        )

    async def history_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Меню истории сделок"""
        if not await self.isUserAllowed(update):
            return
            
        keyboard = [
            ["📅 За день", "📆 За неделю"],
            ["📊 За месяц", "🔄 За все время"],
            ["🥇 По XAUUSDrfd", "🥈 По XAGUSDrfd"],
            ["↩️ Назад в главное меню"]
        ]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        
        await update.message.reply_text(
            "📊 История сделок\n\nВыберите период или инструмент:",
            reply_markup=reply_markup
        )

    async def handle_history_buttons(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка кнопок истории"""
        text = update.message.text
        
        if text == "📅 За день":
            await self.show_daily_history(update, context)
        elif text == "📆 За неделю":
            await self.show_weekly_history(update, context)
        elif text == "📊 За месяц":
            await self.show_monthly_history(update, context)
        elif text == "🔄 За все время":
            await self.show_all_time_history(update, context)
        elif text == "🥇 По XAUUSDrfd":
            await self.show_symbol_history(update, context, "XAUUSDrfd")
        elif text == "🥈 По XAGUSDrfd":
            await self.show_symbol_history(update, context, "XAGUSDrfd")
        elif text == "↩️ Назад в главное меню":
            await self.start(update, context)

    async def show_daily_history(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Показать историю за день"""
        try:
            total_profit, deals = history.get_profit_today()
            
            message = self.format_history_message("📅 История за день", total_profit, deals)
            await update.message.reply_text(message)
            
        except Exception as e:
            await update.message.reply_text(f"❌ Ошибка получения истории: {str(e)}")

    async def show_weekly_history(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Показать историю за неделю"""
        try:
            total_profit, deals = history.get_profit_this_week()
            
            message = self.format_history_message("📆 История за неделю", total_profit, deals)
            await update.message.reply_text(message)
            
        except Exception as e:
            await update.message.reply_text(f"❌ Ошибка получения истории: {str(e)}")

    async def show_monthly_history(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Показать историю за месяц"""
        try:
            total_profit, deals = history.get_profit_this_month()
            
            message = self.format_history_message("📊 История за месяц", total_profit, deals)
            await update.message.reply_text(message)
            
        except Exception as e:
            await update.message.reply_text(f"❌ Ошибка получения истории: {str(e)}")

    async def show_all_time_history(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Показать историю за все время"""
        try:
            # За последние 365 дней (примерно год)
            total_profit, deals = history.get_profit_last_days(365)
            
            message = self.format_history_message("🔄 История за все время", total_profit, deals)
            await update.message.reply_text(message)
            
        except Exception as e:
            await update.message.reply_text(f"❌ Ошибка получения истории: {str(e)}")

    async def show_symbol_history(self, update: Update, context: ContextTypes.DEFAULT_TYPE, symbol: str):
        """Показать историю по конкретному символу"""
        try:
            # За последние 30 дней для символа
            date_to = datetime.datetime.now()
            date_from = date_to - datetime.timedelta(days=30)
            total_profit, deals = history.get_closed_profit_period(date_from, date_to, symbol)
            
            # Фильтруем сделки только по нужному символу
            symbol_deals = [deal for deal in deals if deal['symbol'] == symbol]
            
            message = self.format_history_message(f"🥇 История по {symbol}", total_profit, symbol_deals)
            await update.message.reply_text(message)
            
        except Exception as e:
            await update.message.reply_text(f"❌ Ошибка получения истории: {str(e)}")

    def format_history_message(self, title: str, total_profit: float, deals: list) -> str:
        """Форматирование сообщения с историей"""
        if not deals:
            return f"{title}\n\n📭 Нет закрытых сделок за выбранный период"
        
        message = f"{title}\n\n"
        message += f"💰 Общий профит: {total_profit:.2f}\n"
        message += f"📊 Количество сделок: {len(deals)}\n\n"
        
        # Группируем сделки по символам
        by_symbol = {}
        for deal in deals:
            symbol = deal['symbol']
            if symbol not in by_symbol:
                by_symbol[symbol] = {'profit': 0, 'count': 0}
            by_symbol[symbol]['profit'] += deal['profit']
            by_symbol[symbol]['count'] += 1
        
        # Добавляем статистику по символам
        message += "📈 По инструментам:\n"
        for symbol, data in by_symbol.items():
            emoji = "🟢" if data['profit'] > 0 else "🔴"
            message += f"{emoji} {symbol}: {data['profit']:.2f} ({data['count']} сделок)\n"
        
        # Добавляем последние 5 сделок
        message += "\n📋 Последние сделки:\n"
        recent_deals = sorted(deals, key=lambda x: x['time'], reverse=True)[:5]
        
        for deal in recent_deals:
            emoji = "🟦" if deal['type'] == 'BUY' else "🟥"
            profit_emoji = "✅" if deal['profit'] > 0 else "❌"
            time_str = deal['time'].strftime('%d.%m %H:%M')
            message += f"{emoji} {deal['symbol']} {profit_emoji} {deal['profit']:.2f} ({time_str})\n"
        
        return message

    async def send_telegram_message(self, message):
        """Отправка сообщения в Telegram"""
        try:
            if self.application and CHAT_ID:
                await self.application.bot.send_message(
                    chat_id=CHAT_ID,
                    text=message
                )
        except Exception as e:
            print(f"Ошибка отправки сообщения в Telegram: {e}")
   
    def run_bot(self):
        """Запуск бота в отдельном потоке"""
        asyncio.set_event_loop(self.loop)
        self.application = Application.builder().token(TOKEN).build()
        
        # Добавляем обработчики команд
        handlers = [
            CommandHandler("start", self.start),
            CommandHandler("status", self.status),
            CommandHandler("positions", self.positions),
            CommandHandler("enable_trading", self.disable_trading),
            CommandHandler("disable_trading", self.disable_trading),
            CommandHandler("trading_schedule", self.trading_schedule),
            CommandHandler("pair_info", self.pair_info),
            CommandHandler("history", self.history_menu),
            CallbackQueryHandler(self.handle_manage_pair, pattern="^manage_"),
            CallbackQueryHandler(self.handle_status_change, pattern="^status_"),
            CallbackQueryHandler(self.handle_back_button, pattern="^back_to_pairs"),
            CallbackQueryHandler(self.handle_pair_selection, pattern="^pair_")
        ]
        
        # Добавляем обработчики текстовых сообщений для кнопок
        self.application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_buttons))
        
        # Добавляем обработчик callback запросов (для инлайн-кнопок)
        #self.application.add_handler(CallbackQueryHandler(self.handle_pair_selection))
        
        for handler in handlers:
            self.application.add_handler(handler)
        
        self.application.run_polling()

    async def handle_buttons(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка нажатий на текстовые кнопки
        """
        text = update.message.text
        if text == "📊 Статус":
            await self.status(update, context)
        elif text == "💼 Позиции":
            await self.positions(update, context)
        elif text == "🤖 Старт":
            await self.start(update, context)
        elif text == "⚙️ Управление торговлей":
            await self.disable_trading(update, context)
        elif text == "🕒 График":
            await self.trading_schedule(update, context)
        elif text == "📈 Инфо по паре":
            await self.pair_info(update, context)
        elif text == "📊 История":  
            await self.history_menu(update, context)
        elif text in ["📅 За день", "📆 За неделю", "📊 За месяц", "🔄 За все время", 
                    "🥇 По XAUUSDrfd", "🥈 По XAGUSDrfd", "↩️ Назад в главное меню"]:
            await self.handle_history_buttons(update, context)

# Основной торговый цикл
def trading_loop():
    time.sleep(10)
    symbols = X_VALUE_DICT.keys()
    global lastCheckedTime

    # Словарь для хранения предыдущих статусов
    previous_statuses = {symbol: dict.symbolTradingStatus.get(symbol, 0) for symbol in symbols}
    
    
    while True:
        try:
            # Проверяем соединение перед началом цикла
            if not trading_bot.ensure_mt5_connection():
                print("Нет соединения с MT5, ждем...")
                time.sleep(10)
                continue
            
            print(f"{datetime.datetime.now().time()} все ОК!")
            
            if not trading_bot.isTradingAlowed():
                print("Сейчас торговля запрещена (23:40-02:00 ежедневно или пятница 23:40 - понедельник 03:00)")
                time.sleep(10)
                continue

            if not trading_bot.bot_running:
                time.sleep(5)
                continue
                
            df_for_new_bar = alligator.Df('XAUUSDrfd', TIME_FRAME)
            isNewBar, lastCheckedTime = alligator.IsNewBar(df_for_new_bar, lastCheckedTime, TIME_FRAME)
            
            # Фильтруем пары: только те, у которых статус <= 3
            active_symbols = [symbol for symbol in symbols if dict.symbolTradingStatus.get(symbol, 0) < 3]
            
            
            
            for symbol in active_symbols:
                # Получаем сигнал от быстрой и медленной MA
                fast_ma = ma.get_ma_for_symbol(symbol,TIME_FRAME, 8)
                slow_ma = ma.get_ma_for_symbol(symbol, TIME_FRAME, 21)
                signal_ma = ma.ma_simple_signal(fast_ma, slow_ma)
                signal_critical_angle_ma = ma.ma_critical_angle(fast_ma, slow_ma, symbol)
                # Получаем сигнал от MACD
                hist_line, prev_hist_line, signal_line = macd.calculate_macd_manual(symbol, TIME_FRAME)
                MACD_signal = macd.MACD_signal(hist_line, prev_hist_line, signal_line)
                # Получаем сигнал от ADX
                df = alligator.Df(symbol, TIME_FRAME)
                adx_values, plus_di_values, minus_di_values = adx.ADX(
                    df['high'].values,
                    df['low'].values, 
                    df['close'].values,
                    14
                )
                ADX_signal = adx.ADX_signal(adx_values[499], plus_di_values[499], minus_di_values[499])
                # Получаем сигнал от RSI
                rsi_value = rsi.get_rsi_talib(symbol, TIME_FRAME)
                rsi_signal = rsi.RSI_signal(rsi_value['RSI'].iloc[-1], rsi_value['RSI'].iloc[-2], rsi_value['RSI'].iloc[-3])
                # Получаем atr
                atr_calc = atr.calculate_atr(symbol, TIME_FRAME)
                atr_value = atr_calc.iloc[-1]
                
                
                # Сохраняем предыдущий статус
                previous_status = previous_statuses.get(symbol, 0)
                current_status = dict.symbolTradingStatus.get(symbol, 0)

                if isNewBar and current_status == 1:
                    dict.symbolTradingStatus[symbol] = 0
                    current_status = 0

                if isNewBar:
                    orders = trading.getPositions()
                    if len(orders) > 0:
                        for order in orders:
                            order_dict = order._asdict()
                            profit = order_dict.get("profit", 0)
                            ticketId = order_dict.get("ticket", 0)
                            order_symbol = order_dict.get("symbol", 0)
                            order_type = order_dict.get("type", 0)  # 0 = BUY, 1 = SELL

                            
                            if symbol == order_symbol:
                                print("проверка на стопЛосс")
                                condition_sl = profit < dict.symbolStopLossValue[symbol]
                                
                                
                                 # Для LONG позиций (BUY)
                                if order_type == 0:  # BUY
                                    
                                    condition_rsi = rsi_signal['signal'] == 'SELL'
                                    

                                    if condition_sl or condition_rsi:
                                        trading.orderClose(ticketId, symbol)
                                        dict.symbolStopLossValue[symbol] = 0.0
                                            
                                        if CHAT_ID:
                                            reason = ""
                                            if condition_sl:
                                                reason = "Закрытие по Stop Loss"
                                            if condition_rsi:
                                                reason = "Закрытие по RSI"
                                            result = "😊" if profit > 0 else "😡"
                                                
                                            telegram_message = (
                                                f"{result} ЗАКРЫТИЕ LONG ПОЗИЦИИ\n\n"
                                                f"💵 Пара: {symbol}\n"
                                                f"💰 Профит: {profit:.2f}\n"
                                                f"🎯 Причина: {reason}\n"
                                            )
                                            asyncio.run_coroutine_threadsafe(
                                                trading_bot.send_telegram_message(telegram_message),
                                                trading_bot.loop
                                            )
                        
                                # Для SHORT позиций (SELL)
                                elif order_type == 1:  # SELL
                                        
                                        condition_rsi = rsi_signal['signal'] == 'BUY'
                                        

                                        if  condition_sl or condition_rsi:
                                            trading.orderClose(ticketId, symbol)
                                            dict.symbolStopLossValue[symbol] = 0.0

                                            if CHAT_ID:

                                                reason = ""
                                                if condition_sl:
                                                    reason = "Закрытие по Stop Loss"
                                                if condition_rsi:
                                                    reason = "Закрытие по RSI"
                                                result = "😊" if profit > 0 else "😡"
                                                    
                                                telegram_message = (
                                                    f"{result} ЗАКРЫТИЕ LONG ПОЗИЦИИ\n\n"
                                                    f"💵 Пара: {symbol}\n"
                                                    f"💰 Профит: {profit:.2f}\n"
                                                    f"🎯 Причина: {reason}"

                                                )
                                                asyncio.run_coroutine_threadsafe(
                                                    trading_bot.send_telegram_message(telegram_message),
                                                    trading_bot.loop
                                                )
                    
                    
                    if rsi_value['RSI'].iloc[-1] > 70 or  rsi_value['RSI'].iloc[-1] < 30:
                        dict.symbolExtremumStatus[symbol] = 1
                    if 65 > rsi_value['RSI'].iloc[-1] > 50 or  50 > rsi_value['RSI'].iloc[-1] > 35:
                        dict.symbolExtremumStatus[symbol] = 0
                    print(f"{symbol} signal_ma: {signal_ma['signal']} MACD_signal: {MACD_signal['signal']} ADX_signal: {ADX_signal['signal']} rsi_signal: {rsi_signal['signal']} angle: {signal_critical_angle_ma['angle_fast']}" )
                    message = (
                        f"📊 значение индикаторов\n\n"
                        f"🔢 Пара: {symbol}\n"
                        f"🔄 Сигнал МА: {signal_ma['signal']}\n"
                        f"🔄 Угол fast_ma: {signal_critical_angle_ma['angle_fast']}\n\n"
                        f"🔄 Сигнал MACD: {MACD_signal['signal']}\n"
                        f"🔄 предыдущее значение: {MACD_signal['prev_hist_line']:.5f}\n"
                        f"🔄 текущее значение: {MACD_signal['hist_line']:.5f}\n"
                        f"🔄 сигнальнная линия: {MACD_signal['signal_line']:.5f}\n\n"
                        f"🔄 Сигнал RSI: {rsi_signal['signal']}\n"
                        f"🔄 Экстремум статус: {dict.symbolExtremumStatus.get(symbol, 0)}\n"
                        f"🔄 предыдущее значение: {rsi_signal['prev_rsi']:.5f}\n"
                        f"🔄 текущее значение: {rsi_signal['rsi']:.5f}\n\n"
                        f"⏰ Время: {trading.serverTime(symbol)}\n"

                    )
                    
                    # Отправляем сообщение в Telegram
                    if CHAT_ID:
                        asyncio.run_coroutine_threadsafe(
                            trading_bot.send_telegram_message(message),
                            trading_bot.loop
                        )
                    
                    
                    
                if signal_ma['signal'] == 'BUY' and MACD_signal['signal'] == 'BUY' and rsi_signal['signal'] == 'BUY':
                    sum_signal = 'BUY'
                elif signal_ma['signal'] == 'SELL' and MACD_signal['signal'] == 'SELL' and rsi_signal['signal'] == 'SELL':
                    sum_signal = 'SELL'
                else:
                    sum_signal = 'NO_SIGNAL'
                # Проверяем изменение статуса и отправляем сообщение
                if current_status != previous_status:
                    status_names = {
                        0: "🟢 РАЗРЕШЕНА",
                        1: "🟡 ПРИОСТАНОВЛЕНА", 
                        2: "🔴 ЗАБЛОКИРОВАНА",
                        3: "⚫️ ВЫКЛЮЧЕНА"
                    }
                    
                    
                    message = (
                        f"📊 ИЗМЕНЕНИЕ СТАТУСА ТОРГОВЛИ\n\n"
                        f"🔢 Пара: {symbol}\n"
                        f"📈 Статус: {status_names.get(current_status, 'НЕИЗВЕСТНО')}\n"
                        f"📉 Предыдущий: {status_names.get(previous_status, 'НЕИЗВЕСТНО')}\n"
                        f"⏰ Время: {trading.serverTime(symbol)}\n"

                    )
                    
                    # Отправляем сообщение в Telegram
                    '''if CHAT_ID:
                        asyncio.run_coroutine_threadsafe(
                            trading_bot.send_telegram_message(message),
                            trading_bot.loop
                        )'''
                    
                    # Обновляем предыдущий статус
                    previous_statuses[symbol] = current_status
                
                if sum_signal != 'NO_SIGNAL' and dict.symbolTradingStatus[symbol] == 0:
                    trading_bot.checkOpen(symbol, sum_signal, 'sum_signal', atr_value, signal_ma, signal_critical_angle_ma, MACD_signal, rsi_signal)

                
        except Exception as e:
            print(f"Ошибка: {str(e)}")
            #logger.saveErrorsToExcel("alligatorForMetalls", str(e), Settings.filenameErrors)
            #continue
        
        time.sleep(10)    

if __name__ == '__main__':
    # Инициализация торгового бота
    trading_bot = TradingBot(trading, dict, alligator, AMA)
    
    # Запуск телеграм бота в отдельном потоке
    bot_thread = threading.Thread(target=trading_bot.run_bot, daemon=True)
    bot_thread.start()
    
     # Запуск MoneySaver
    money_saver_thread = threading.Thread(target=trading_bot.moneySaverLoop, daemon=True)
    money_saver_thread.start()
    
    # Запуск основного торгового цикла
    trading_loop()