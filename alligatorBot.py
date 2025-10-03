import time
from telegram import Update, ReplyKeyboardMarkup, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler
import asyncio
import pandas as pd
import threading
import MetaTrader5 as mt5
import datetime
from account import Account
from indicators import AdaptiveMovingAverage, Alligator, BullsBearsPower, MACD, MovingAverage
from trading import Trading
from settings import TargetType, IndicatorType, Dictionary
from logs.logger import Logger
from authenticator import MT5Auth
from history import History

# Конфигурация бота
TOKEN = "8062299925:AAFA14ISWThGN9D0ktg7lXxRtX2lvglzG9w"
#TOKEN = "8235563483:AAF1gESvpoES7ttfJBlOKMfbA2z7BVl55LA" #AlligatorMinerTesr
CHAT_ID = None  # Будет заполнено после /start
# Белый список разрешенных пользователей
ALLOWED_USERS = {
    "320526655": "Pavel Bogatyrev",  # Замените на ваш реальный Chat ID
    # "987654321": "Другой пользователь",  # Можно добавить других
}

account = Account.accountDemo2
auth = MT5Auth(account)
auth.login()
trading = Trading()
history = History()
alligator = Alligator()
bbp = BullsBearsPower()
logger = Logger()
dict = Dictionary()
AMA = AdaptiveMovingAverage()
X_VALUE_DICT = Dictionary.symbolXvalueH1
lastCheckedTime = None
checkFlat = None
TIME_FRAME = mt5.TIMEFRAME_M1
macd = MACD()
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
                if not trading_bot.isTradingAlowed():
                    print("Сейчас торговля запрещена (23:40-02:00 ежедневно или пятница 23:40 - понедельник 03:00)")
                    time.sleep(60)
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
                        open_price = order_dict.get("price_open", 0)
                        point = mt5.symbol_info(symbol).point

                        if dict.symbolTradingStatus[symbol] > 0:
                            continue
                                                
                        # Рассчитываем уровни Take Profit и Stop Loss
                        take_profit_value = mt5.symbol_info(symbol).spread * volume * 5
                        stop_loss_value = mt5.symbol_info(symbol).spread * volume * -3

                        dict.symbolTakeProfitValue[symbol] = take_profit_value
                        dict.symbolStopLossValue[symbol] = stop_loss_value

                        # Получить сигнал пересечения быстрой и медленной MA
                        fast_ma = ma.get_ma_for_symbol(symbol,TIME_FRAME, 8)
                        slow_ma = ma.get_ma_for_symbol(symbol, TIME_FRAME, 21)
                        signal = ma.ma_cross_signal(fast_ma, slow_ma)

                        # Получаем текущие low и high из последних баров
                        rates = mt5.copy_rates_from_pos(symbol, TIME_FRAME, 0, 2)  # 2 последних бара M1
                        if rates is None or len(rates) < 2:
                            continue
                        
                        # Текущий бар (последний завершенный бар)
                        current_low = rates[-1]['low']
                        current_high = rates[-1]['high']
                    
                    # Или используем предыдущий бар для более стабильных значений
                    # current_low = rates[-2]['low']
                    # current_high = rates[-2]['high']
                        
                        # Для LONG позиций (BUY)
                        if order_type == 0:  # BUY

                                maxValue = (current_high - open_price) / point * volume
                                
                                # Условия закрытия для LONG:
                                # 1. Текущий профит > Take Profit
                                # 2. Текущий профит < Stop Loss  
                                # 3. Максимум > Take Profit
                                condition_tp = profit > take_profit_value
                                condition_sl = profit < stop_loss_value
                                condition_maxValue = maxValue > take_profit_value
                                condition_signal = signal['signal'] == 'SELL'
                                
                                if condition_tp or condition_sl or condition_signal:
                                    trading.orderClose(ticketId, symbol)
                                    dict.symbolTakeProfitValue[symbol] = 0.0
                                    dict.symbolStopLossValue[symbol] = 0.0
                                    
                                    if CHAT_ID:
                                        reason = ""
                                        if condition_tp:
                                            reason = "Достигнут Take Profit"
                                        elif condition_sl:
                                            reason = "Достигнут Stop Loss"
                                        elif condition_signal:
                                            reason = "Разворот тренда"
                                        else:
                                            reason = f"Достигнут максимум: {abs(maxValue):.0f} пунктов"
                                        
                                        telegram_message = (
                                            f"🎯 ЗАКРЫТИЕ LONG ПОЗИЦИИ\n\n"
                                            f"💵 Пара: {symbol}\n"
                                            f"💰 Профит: {profit:.2f}\n"
                                            f"🎯 Причина: {reason}"
                                        )
                                        asyncio.run_coroutine_threadsafe(
                                            self.send_telegram_message(telegram_message),
                                            self.loop
                                        )
                        
                        # Для SHORT позиций (SELL)
                        elif order_type == 1:  # SELL
                           
                                minValue = (open_price - current_low) / point * volume
                                
                                
                                # Условия закрытия для SHORT:
                                # 1. Текущий профит > Take Profit
                                # 2. Текущий профит < Stop Loss
                                # 3. Цена откатилась от минимума более чем на max_drawdown_points
                                condition_tp = profit > take_profit_value
                                condition_sl = profit < stop_loss_value
                                condition_minValue = minValue > take_profit_value
                                condition_signal = signal['signal'] == 'BUY'
                                
                                if condition_tp or condition_sl or condition_signal:
                                    trading.orderClose(ticketId, symbol)
                                    dict.symbolTakeProfitValue[symbol] = 0.0
                                    dict.symbolStopLossValue[symbol] = 0.0

                                    if CHAT_ID:
                                        reason = ""
                                        if condition_tp:
                                            reason = "Достигнут Take Profit"
                                        elif condition_sl:
                                            reason = "Достигнут Stop Loss"
                                        elif condition_signal:
                                            reason = "Разворот тренда"
                                        else:
                                            reason = f"Достигнут минимум: {abs(minValue):.0f} пунктов"
                                        
                                        telegram_message = (
                                            f"🎯 ЗАКРЫТИЕ SHORT ПОЗИЦИИ\n\n"
                                            f"💵 Пара: {symbol}\n"
                                            f"💰 Профит: {profit:.2f}\n"
                                            f"🎯 Причина: {reason}"
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

    def checkOpen(self, symbol, signal):    
        serverTime = trading.serverTime(symbol)
        if trading.symbolInPostions(symbol,TargetType.LONG,f"{IndicatorType.ALLIGATOR_MAIN}_{TIME_FRAME}") or trading.symbolInPostions(symbol,TargetType.SHORT,f"{IndicatorType.ALLIGATOR_MAIN}_{TIME_FRAME}"):
            #Уже есть ордер по данной паре и данному индикатору
            return

        if signal['signal'] == 'BUY':

            safeVolume = trading.calculateSafeTradeWithMargin(
                symbol, 
                risk_percent=90, 
                stop_loss_pips = mt5.symbol_info(symbol).spread * 5, 
                order_type=TargetType.LONG
            )
            result = trading.orderOpen(symbol, TargetType.LONG, safeVolume, f"{IndicatorType.ALLIGATOR_MAIN}_{TIME_FRAME}")
            
            print_message = f"\n{"-" * 50}, \ntime:{serverTime} \npair: {symbol} \ncomment: Ордер LONG выставлен по условию, \n{"-" * 50}"
            print(print_message)
            
            # Отправляем сообщение в Telegram
            if result and CHAT_ID:
                telegram_message = (
                    f"🎯 ОТКРЫТИЕ ПОЗИЦИИ\n\n"
                    f"🟦 Направление: LONG\n"
                    f"💵 Пара: {symbol}\n"
                    f"⏰ Время: {serverTime}\n"
                )
                asyncio.run_coroutine_threadsafe(
                    self.send_telegram_message(telegram_message),
                    self.loop
                )
                
        if signal['signal'] == 'SELL':
            safeVolume = trading.calculateSafeTradeWithMargin(
                symbol, 
                risk_percent = 90, 
                stop_loss_pips = mt5.symbol_info(symbol).spread * 5, 
                order_type=TargetType.SHORT
            )
            result = trading.orderOpen(symbol, TargetType.SHORT, safeVolume, f"{IndicatorType.ALLIGATOR_MAIN}_{TIME_FRAME}")

            print_message = f"\n{"-" * 50} \ntime:{serverTime} \npair: {symbol} \ncomment: Ордер SHORT выставлен по условию, \n{"-" * 50}"
            print(print_message)
            
            # Отправляем сообщение в Telegram
            if result and CHAT_ID:
                telegram_message = (
                    f"🎯 ОТКРЫТИЕ ПОЗИЦИИ\n\n"
                    f"🟥 Направление: SHORT\n"
                    f"💵 Пара: {symbol}\n"

                    f"⏰ Время: {serverTime}\n"
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
                    message += (
                        f"  {direction}: {pos.volume} лот(ов)\n"
                        f"💰  Прибыль: {pos.profit}\n"
                        f"🛑  Тейк-профит значение: {dict.symbolTakeProfitValue[symbol]}\n"
                        f"🛑  Стоп-лосс значение: {dict.symbolStopLossValue[symbol]}\n"

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
                df = self.alligator.Df(symbol, mt5.TIMEFRAME_H1)
                check_flat = self.ama.checkFlat(df, symbol, self.dict.symbolXvalueH1)
                median_price, jaw, teeth, lips, open_price = self.alligator.MainData(df)
                jaw_shifted, teeth_shifted, lips_shifted = self.alligator.ShiftedData(jaw, teeth, lips, median_price)
                last_jaw, last_teeth, last_lips, prelast_lips = self.alligator.LastData(symbol, jaw_shifted, teeth_shifted, lips_shifted)
                angle = self.alligator.SupportData(last_lips, prelast_lips, symbol, X_VALUE_DICT)
                
                message = (
                    f"📈 Информация по паре {symbol}:\n\n"
                    f"📊 Статус торговли: {self.dict.symbolTradingStatus.get(symbol, 0)}\n"
                    f"🔄 Флэт: {'Да' if check_flat['value'] else 'Нет'}\n"
                    f"📐 Угол губ: {angle:.2f}°\n"
                    f"📏 Угол флэта: {check_flat['angle']:.2f}°\n"

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
        symbols = list(X_VALUE_DICT.keys())
        
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
    symbols = X_VALUE_DICT.keys()
    global lastCheckedTime

    # Словарь для хранения предыдущих статусов
    previous_statuses = {symbol: dict.symbolTradingStatus.get(symbol, 0) for symbol in symbols}
    
    
    while True:
        try:
            if not trading_bot.isTradingAlowed():
                print("Сейчас торговля запрещена (23:40-02:00 ежедневно или пятница 23:40 - понедельник 03:00)")
                time.sleep(60)
                continue

            if not trading_bot.bot_running:
                time.sleep(5)
                continue
                
            df = alligator.Df('XAUUSDrfd', TIME_FRAME)
            isNewBar, lastCheckedTime = alligator.IsNewBar(df, lastCheckedTime, TIME_FRAME)
            
            # Фильтруем пары: только те, у которых статус <= 3
            active_symbols = [symbol for symbol in symbols if dict.symbolTradingStatus.get(symbol, 0) < 3]
            
            
            
            for symbol in active_symbols:
                
                # Сохраняем предыдущий статус
                previous_status = previous_statuses.get(symbol, 0)
                current_status = dict.symbolTradingStatus.get(symbol, 0)

                if isNewBar and current_status == 1:
                    dict.symbolTradingStatus[symbol] = 0
                    current_status = 0

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
                    if CHAT_ID:
                        asyncio.run_coroutine_threadsafe(
                            trading_bot.send_telegram_message(message),
                            trading_bot.loop
                        )
                    
                    # Обновляем предыдущий статус
                    previous_statuses[symbol] = current_status
                
                # Получить сигнал пересечения быстрой и медленной MA
                fast_ma = ma.get_ma_for_symbol(symbol,TIME_FRAME, 8)
                slow_ma = ma.get_ma_for_symbol(symbol, TIME_FRAME, 21)
                signal = ma.ma_cross_signal(fast_ma, slow_ma)
                
                if signal['signal'] != 'NO_SIGNAL' and dict.symbolTradingStatus[symbol] == 0:
                    trading_bot.checkOpen(symbol, signal)

                print(f"{symbol} signal: {signal['signal']}")

        except Exception as e:
            print(f"Ошибка: {str(e)}")
            #logger.saveErrorsToExcel("alligatorForMetalls", str(e), Settings.filenameErrors)
            #continue
        
        time.sleep(1)

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