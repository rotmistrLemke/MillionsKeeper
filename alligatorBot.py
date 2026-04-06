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
from market_data_cache import cache
from backtest import run_backtest, print_report

# Конфигурация бота
TOKEN = Account.token
CHAT_ID = None  # Будет заполнено после /start
# Белый список разрешенных пользователей
ALLOWED_USERS = {
    "320526655": "Pavel Bogatyrev",
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
        print(f"Несанкционированный доступ: {user_info}")

        await update.message.reply_text(
            "Доступ запрещен!\n\n"
            "У вас нет прав для использования этого бота. "
            "Если вы должны иметь доступ, свяжитесь с администратором."
        )
        return False

    def isTradingAlowed(self):
        """Проверка разрешенного времени для торговли"""
        now = datetime.datetime.now()
        current_time = now.time()
        current_weekday = now.weekday()

        friday_off_period = (
            current_weekday == 4 and current_time >= datetime.time(23, 30)) or (
            current_weekday == 5) or (
            current_weekday == 6) or (
            current_weekday == 0 and current_time < datetime.time(2, 10))

        return not (friday_off_period)

    def checkOpen(self, symbol, signal, comment, atr, signal_ma, signal_critical_angle_ma, MACD_signal, rsi_signal):
        active_symbols = [s for s in dict.symbolTradingStatus.keys() if dict.symbolTradingStatus.get(s, 0) < 3]
        serverTime = trading.serverTime(symbol)

        positions = trading.getPositions()
        if len(positions) == len(active_symbols):
            return

        if trading.symbolInPostions(symbol, TargetType.LONG) or trading.symbolInPostions(symbol, TargetType.SHORT):
            return

        if signal not in ('BUY', 'SELL'):
            return

        is_buy = signal == 'BUY'
        target_type = TargetType.LONG if is_buy else TargetType.SHORT
        risk_percent = 80 if is_buy else 90
        direction_text = "LONG" if is_buy else "SHORT"
        direction_emoji = "🟦" if is_buy else "🟥"

        symbol_info = cache.get_symbol_info(symbol)
        safeVolume = trading.calculateSafeTradeWithMargin(
            symbol,
            risk_percent=risk_percent,
            stop_loss_pips=2 * atr / symbol_info.point,
            order_type=target_type
        )

        if safeVolume == 0:
            telegram_message_error = f"Ошибка открытия позиции: неправильный расчет безопасного объема\n"
            asyncio.run_coroutine_threadsafe(
                self.send_telegram_message(telegram_message_error),
                self.loop
            )

        result = trading.orderOpen(symbol, target_type, safeVolume, f"{comment}")

        print_message = f"\n{'-' * 50}, \ntime:{serverTime} \npair: {symbol} \ncomment: Ордер {direction_text} выставлен по условию, \n{'-' * 50}"
        print(print_message)

        if result and CHAT_ID:
            telegram_message = (
                f"🎯 ОТКРЫТИЕ ПОЗИЦИИ\n\n"
                f"{direction_emoji} Направление: {direction_text}\n"
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

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not await self.isUserAllowed(update):
            return
        global CHAT_ID
        CHAT_ID = str(update.effective_chat.id)

        keyboard = [
        ["🤖 Старт", "📊 Статус"],
        ["💼 Позиции", "⚙️ Управление торговлей"],
        ["🕒 График", "📈 Инфо по паре"],
        ["📊 История", "🧪 Бэктест"]
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

            for symbol, positions in positions_by_symbol.items():
                message += f"🔹 {symbol}:\n"

                # Получаем MA один раз для символа вместо в каждой итерации
                fast_ma = ma.get_ma_for_symbol(symbol, TIME_FRAME, 8)
                slow_ma = ma.get_ma_for_symbol(symbol, TIME_FRAME, 21)
                signal = ma.ma_cross_signal(fast_ma, slow_ma, symbol)

                for pos in positions:
                    direction = "🟦 LONG" if pos.type == mt5.ORDER_TYPE_BUY else "🟥 SHORT"
                    result = "😊 Прибыль" if pos.profit > 0 else "😡 Потери"
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
                changed_count = 0
                for p in X_VALUE_DICT.keys():
                    old_status = self.dict.symbolTradingStatus.get(p, 0)
                    if old_status != new_status:
                        self.dict.symbolTradingStatus[p] = new_status
                        changed_count += 1

                message = f"✅ Статус изменен для {changed_count} пар: {status_names[new_status]}"
            else:
                old_status = self.dict.symbolTradingStatus.get(symbol, 0)
                self.dict.symbolTradingStatus[symbol] = new_status

                message = f"✅ Пара {symbol}: {status_names[old_status]} → {status_names[new_status]}"

            await query.edit_message_text(message)

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
                fast_ma = ma.get_ma_for_symbol(symbol, TIME_FRAME, 8)
                slow_ma = ma.get_ma_for_symbol(symbol, TIME_FRAME, 21)
                signal_ma = ma.ma_simple_signal(fast_ma, slow_ma)
                signal_critical_angle_ma = ma.ma_critical_angle(fast_ma, slow_ma, symbol)
                hist_line, prev_hist_line, signal_line = macd.calculate_macd_manual(symbol, TIME_FRAME)
                MACD_signal = macd.MACD_signal(hist_line, prev_hist_line, signal_line)
                df = alligator.Df(symbol, TIME_FRAME)
                adx_values, plus_di_values, minus_di_values = adx.ADX(
                    df['high'].values,
                    df['low'].values,
                    df['close'].values,
                    14
                )
                ADX_signal = adx.ADX_signal(adx_values[-1], plus_di_values[-1], minus_di_values[-1])
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

        keyboard = []
        symbols = [symbol for symbol in dict.symbolTradingStatus.keys() if dict.symbolTradingStatus.get(symbol, 0) < 3]

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
            total_profit, deals = history.get_profit_last_days(365)
            message = self.format_history_message("🔄 История за все время", total_profit, deals)
            await update.message.reply_text(message)
        except Exception as e:
            await update.message.reply_text(f"❌ Ошибка получения истории: {str(e)}")

    async def show_symbol_history(self, update: Update, context: ContextTypes.DEFAULT_TYPE, symbol: str):
        """Показать историю по конкретному символу"""
        try:
            date_to = datetime.datetime.now()
            date_from = date_to - datetime.timedelta(days=30)
            total_profit, deals = history.get_closed_profit_period(date_from, date_to, symbol)

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

        by_symbol = {}
        for deal in deals:
            symbol = deal['symbol']
            if symbol not in by_symbol:
                by_symbol[symbol] = {'profit': 0, 'count': 0}
            by_symbol[symbol]['profit'] += deal['profit']
            by_symbol[symbol]['count'] += 1

        message += "📈 По инструментам:\n"
        for symbol, data in by_symbol.items():
            emoji = "🟢" if data['profit'] > 0 else "🔴"
            message += f"{emoji} {symbol}: {data['profit']:.2f} ({data['count']} сделок)\n"

        message += "\n📋 Последние сделки:\n"
        recent_deals = sorted(deals, key=lambda x: x['time'], reverse=True)[:5]

        for deal in recent_deals:
            emoji = "🟦" if deal['type'] == 'BUY' else "🟥"
            profit_emoji = "✅" if deal['profit'] > 0 else "❌"
            time_str = deal['time'].strftime('%d.%m %H:%M')
            message += f"{emoji} {deal['symbol']} {profit_emoji} {deal['profit']:.2f} ({time_str})\n"

        return message

    async def backtest_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Меню бэктеста — выбор символа"""
        if not await self.isUserAllowed(update):
            return

        keyboard = []
        symbols = [s for s in dict.symbolTradingStatus.keys() if dict.symbolTradingStatus.get(s, 0) < 3]

        for i in range(0, len(symbols), 2):
            row = []
            for symbol in symbols[i:i+2]:
                row.append(InlineKeyboardButton(symbol, callback_data=f"bt_sym_{symbol}"))
            keyboard.append(row)

        keyboard.append([InlineKeyboardButton("🌐 Все активные пары", callback_data="bt_sym_ALL")])

        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(
            "🧪 Бэктест стратегии MA+MACD+RSI\n\nВыберите пару:",
            reply_markup=reply_markup
        )

    async def handle_backtest_symbol(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка выбора символа — показ выбора периода"""
        if not await self.isUserAllowed(update):
            return
        query = update.callback_query
        await query.answer()

        symbol = query.data.replace("bt_sym_", "")

        keyboard = [
            [
                InlineKeyboardButton("500 баров", callback_data=f"bt_bars_{symbol}_500"),
                InlineKeyboardButton("1000 баров", callback_data=f"bt_bars_{symbol}_1000"),
            ],
            [
                InlineKeyboardButton("2000 баров", callback_data=f"bt_bars_{symbol}_2000"),
                InlineKeyboardButton("5000 баров", callback_data=f"bt_bars_{symbol}_5000"),
            ],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        name = "все активные пары" if symbol == "ALL" else symbol
        await query.edit_message_text(
            f"🧪 Бэктест: {name}\n\nВыберите глубину истории:",
            reply_markup=reply_markup
        )

    async def handle_backtest_bars(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка выбора баров — показ выбора депозита"""
        if not await self.isUserAllowed(update):
            return
        query = update.callback_query
        await query.answer()

        # bt_bars_{symbol}_{bars}
        parts = query.data.split("_")
        symbol = parts[2]
        bars = parts[3]

        keyboard = [
            [
                InlineKeyboardButton("Без депозита", callback_data=f"bt_dep_{symbol}_{bars}_0"),
            ],
            [
                InlineKeyboardButton("1 000 $", callback_data=f"bt_dep_{symbol}_{bars}_1000"),
                InlineKeyboardButton("5 000 $", callback_data=f"bt_dep_{symbol}_{bars}_5000"),
            ],
            [
                InlineKeyboardButton("10 000 $", callback_data=f"bt_dep_{symbol}_{bars}_10000"),
                InlineKeyboardButton("50 000 $", callback_data=f"bt_dep_{symbol}_{bars}_50000"),
            ],
            [
                InlineKeyboardButton("100 000 $", callback_data=f"bt_dep_{symbol}_{bars}_100000"),
            ],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        name = "все активные пары" if symbol == "ALL" else symbol
        await query.edit_message_text(
            f"🧪 Бэктест: {name}, {bars} баров\n\n"
            f"💰 Выберите сумму депозита для расчёта прибыли:\n"
            f"(«Без депозита» — результат только в пунктах)",
            reply_markup=reply_markup
        )

    async def handle_backtest_deposit(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка выбора депозита — запрос объёма текстом"""
        if not await self.isUserAllowed(update):
            return
        query = update.callback_query
        await query.answer()

        # bt_dep_{symbol}_{bars}_{deposit}
        parts = query.data.split("_")
        symbol = parts[2]
        bars = parts[3]
        deposit = parts[4]

        # Сохраняем параметры и ждём текстового ввода объёма
        context.user_data['bt_symbol'] = symbol
        context.user_data['bt_bars'] = int(bars)
        context.user_data['bt_deposit'] = float(deposit)
        context.user_data['bt_awaiting_volume'] = True

        name = "все активные пары" if symbol == "ALL" else symbol
        dep_str = f", депозит {float(deposit):,.0f}$" if float(deposit) > 0 else ""
        await query.edit_message_text(
            f"🧪 Бэктест: {name}, {bars} баров{dep_str}\n\n"
            f"📊 Введите объём сделки в лотах (число):\n"
            f"Например: 0.1 или 1.5\n"
            f"Введите 0 для авторасчёта по % риска от баланса"
        )

    async def handle_backtest_volume_text(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка текстового ввода объёма для бэктеста"""
        if not context.user_data.get('bt_awaiting_volume'):
            return False  # не наш обработчик

        text = update.message.text.strip().replace(',', '.')
        try:
            fixed_volume = float(text)
        except ValueError:
            await update.message.reply_text("❌ Введите число, например: 0.1 или 1.5\nИли 0 для авторасчёта.")
            return True

        if fixed_volume < 0:
            await update.message.reply_text("❌ Объём не может быть отрицательным.")
            return True

        context.user_data['bt_awaiting_volume'] = False
        symbol = context.user_data['bt_symbol']
        bars = context.user_data['bt_bars']
        deposit = context.user_data['bt_deposit']

        await self._run_backtest_and_send(update, context, symbol, bars, deposit, fixed_volume)
        return True

    async def handle_backtest_run(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Запуск бэктеста из callback (обратная совместимость)"""
        if not await self.isUserAllowed(update):
            return
        query = update.callback_query
        await query.answer()

        # bt_run_{symbol}_{bars}_{deposit}
        parts = query.data.split("_")
        symbol = parts[2]
        bars = int(parts[3])
        deposit = float(parts[4])
        fixed_volume = 0.0

        await self._run_backtest_and_send(update, context, symbol, bars, deposit, fixed_volume)

    async def _run_backtest_and_send(self, update, context, symbol, bars, deposit, fixed_volume):
        """Общая логика запуска бэктеста и отправки результата."""
        dep_str = f", депозит {deposit:,.0f}$" if deposit > 0 else ""
        vol_str = f", объём {fixed_volume} лот" if fixed_volume > 0 else ", авторасчёт объёма"

        # Отправляем сообщение "ожидайте"
        if update.callback_query:
            await update.callback_query.edit_message_text(
                f"⏳ Бэктест запущен: {symbol}, {bars} баров H1{dep_str}{vol_str}...\nПодождите..."
            )
        else:
            await update.message.reply_text(
                f"⏳ Бэктест запущен: {symbol}, {bars} баров H1{dep_str}{vol_str}...\nПодождите..."
            )

        try:
            if symbol == "ALL":
                symbols = [s for s in dict.symbolTradingStatus.keys() if dict.symbolTradingStatus.get(s, 0) < 3]
            else:
                symbols = [symbol]

            messages = []
            for sym in symbols:
                res = run_backtest(sym, mt5.TIMEFRAME_H1, bars=bars, spread_points=0,
                                   deposit=deposit, fixed_volume=fixed_volume)
                messages.append(self._format_backtest_result(sym, bars, res, deposit, fixed_volume))

            full_message = "\n\n".join(messages)

            if len(full_message) > 4000:
                chunks = [full_message[i:i+4000] for i in range(0, len(full_message), 4000)]
                for chunk in chunks:
                    await self.application.bot.send_message(chat_id=CHAT_ID, text=chunk)
            else:
                await self.application.bot.send_message(chat_id=CHAT_ID, text=full_message)

        except Exception as e:
            await self.application.bot.send_message(
                chat_id=CHAT_ID,
                text=f"❌ Ошибка бэктеста: {str(e)}"
            )

    def _format_backtest_result(self, symbol, bars, result, deposit=0, fixed_volume=0.0):
        """Форматирование результата бэктеста для Telegram."""
        if result is None or result.total_trades == 0:
            return f"🧪 {symbol} ({bars} баров)\nНет сделок за период."

        msg = (
            f"🧪 БЭКТЕСТ: {symbol}\n"
            f"{'─' * 30}\n"
            f"Баров: {bars} (H1)\n"
        )

        if deposit > 0:
            msg += f"Депозит: {deposit:,.0f} $\n"
        if fixed_volume > 0:
            msg += f"Объём: {fixed_volume} лот (фикс.)\n"

        msg += (
            f"Сделок: {result.total_trades}\n"
            f"Win Rate: {result.win_rate:.1f}%\n"
            f"Прибыльных: {len(result.winning_trades)} | Убыточных: {len(result.losing_trades)}\n"
            f"{'─' * 30}\n"
            f"Итого P&L: {result.total_pnl_points:+.1f} пунктов\n"
            f"Средняя прибыль: {result.avg_win:+.1f} пунктов\n"
            f"Средний убыток: {result.avg_loss:+.1f} пунктов\n"
            f"Profit Factor: {result.profit_factor:.2f}\n"
            f"Макс. просадка: {result.max_drawdown_points:.1f} пунктов\n"
            f"Макс. серия убытков: {result.max_consecutive_losses}\n"
        )

        if deposit > 0:
            msg += (
                f"{'─' * 30}\n"
                f"💰 ФИНАНСЫ:\n"
                f"P&L: {result.total_pnl_money:+,.2f} $\n"
                f"Баланс: {result.final_balance:,.2f} $\n"
                f"Доходность: {result.return_pct:+.1f}%\n"
                f"Ср. прибыль: {result.avg_win_money:+,.2f} $\n"
                f"Ср. убыток: {result.avg_loss_money:+,.2f} $\n"
                f"Просадка: {result.max_drawdown_money:,.2f} $ ({result.max_drawdown_pct:.1f}%)\n"
            )

        if result.trades:
            import numpy as np
            avg_bars = np.mean([t['bars_held'] for t in result.trades])
            msg += f"Удержание: {avg_bars:.1f} баров\n"

            msg += f"{'─' * 30}\n"
            msg += "Последние 5 сделок:\n"
            for t in result.trades[-5:]:
                entry_t = t['entry_time'].strftime('%d.%m %H:%M') if hasattr(t['entry_time'], 'strftime') else str(t['entry_time'])
                emoji = "🟦" if t['type'] == 'BUY' else "🟥"
                pnl_emoji = "✅" if t['pnl_points'] > 0 else "❌"
                if deposit > 0:
                    msg += f"{emoji} {entry_t} {pnl_emoji} {t['pnl_money']:+,.2f}$ ({t['volume']:.2f} лот)\n"
                else:
                    msg += f"{emoji} {entry_t} {pnl_emoji} {t['pnl_points']:+.1f}п ({t['bars_held']}б)\n"
                ind = t.get('indicators', {})
                if ind:
                    msg += f"  EMA: {ind['ema8']:.4f}/{ind['ema21']:.4f}\n"
                    msg += f"  MACD: {ind['macd_line']:.5f} Sig: {ind['macd_signal']:.5f}\n"
                    msg += f"  RSI: {ind['rsi']:.1f} ATR: {ind['atr']:.5f}\n"

        return msg

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

    def _init_chat_id(self):
        """Получение CHAT_ID из последних обновлений Telegram при старте."""
        global CHAT_ID
        if CHAT_ID:
            return
        import urllib.request, json
        try:
            req = urllib.request.urlopen(f"https://api.telegram.org/bot{TOKEN}/getUpdates", timeout=10)
            data = json.loads(req.read().decode())
            if data.get("ok"):
                for upd in reversed(data.get("result", [])):
                    msg = upd.get("message") or upd.get("callback_query", {}).get("message")
                    if msg and msg.get("chat"):
                        user_id = str(msg["chat"]["id"])
                        if user_id in ALLOWED_USERS:
                            CHAT_ID = user_id
                            print(f"CHAT_ID инициализирован из истории: {CHAT_ID}")
                            return
        except Exception as e:
            print(f"Не удалось получить CHAT_ID при старте: {e}")

    def run_bot(self):
        """Запуск бота в отдельном потоке"""
        asyncio.set_event_loop(self.loop)
        self._init_chat_id()
        self.application = Application.builder().token(TOKEN).build()

        handlers = [
            CommandHandler("start", self.start),
            CommandHandler("status", self.status),
            CommandHandler("positions", self.positions),
            CommandHandler("enable_trading", self.disable_trading),
            CommandHandler("disable_trading", self.disable_trading),
            CommandHandler("trading_schedule", self.trading_schedule),
            CommandHandler("pair_info", self.pair_info),
            CommandHandler("history", self.history_menu),
            CommandHandler("backtest", self.backtest_menu),
            CallbackQueryHandler(self.handle_manage_pair, pattern="^manage_"),
            CallbackQueryHandler(self.handle_status_change, pattern="^status_"),
            CallbackQueryHandler(self.handle_back_button, pattern="^back_to_pairs"),
            CallbackQueryHandler(self.handle_pair_selection, pattern="^pair_"),
            CallbackQueryHandler(self.handle_backtest_symbol, pattern="^bt_sym_"),
            CallbackQueryHandler(self.handle_backtest_bars, pattern="^bt_bars_"),
            CallbackQueryHandler(self.handle_backtest_deposit, pattern="^bt_dep_"),
            CallbackQueryHandler(self.handle_backtest_run, pattern="^bt_run_")
        ]

        self.application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_buttons))

        for handler in handlers:
            self.application.add_handler(handler)

        self.application.run_polling()

    async def handle_buttons(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка нажатий на текстовые кнопки"""
        # Перехват ввода объёма для бэктеста
        if context.user_data.get('bt_awaiting_volume'):
            handled = await self.handle_backtest_volume_text(update, context)
            if handled:
                return

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
        elif text == "🧪 Бэктест":
            await self.backtest_menu(update, context)
        elif text in ["📅 За день", "📆 За неделю", "📊 За месяц", "🔄 За все время",
                    "🥇 По XAUUSDrfd", "🥈 По XAGUSDrfd", "↩️ Назад в главное меню"]:
            await self.handle_history_buttons(update, context)

# Основной торговый цикл
def trading_loop():
    time.sleep(10)
    symbols = X_VALUE_DICT.keys()
    global lastCheckedTime

    previous_statuses = {symbol: dict.symbolTradingStatus.get(symbol, 0) for symbol in symbols}

    while True:
        try:
            # Сбрасываем кэш в начале каждой итерации
            cache.invalidate()

            if not trading_bot.ensure_mt5_connection():
                print("Нет соединения с MT5, ждем...")
                time.sleep(10)
                continue

            print(f"{datetime.datetime.now().time()} все ОК!")

            if not trading_bot.isTradingAlowed():
                positions = trading.getPositions()
                if len(positions) > 0:
                    for position in positions:
                        order_dict = position._asdict()
                        ticket_id = order_dict.get("ticket", 0)
                        symbol = order_dict.get("symbol", "Unknown")
                        trading.orderClose(ticket_id, symbol)
                        time.sleep(0.1)
                print("Сейчас торговля запрещена (пятница 23:40 - понедельник 02:00)")
                time.sleep(10)
                continue

            if not trading_bot.bot_running:
                time.sleep(5)
                continue

            df_for_new_bar = alligator.Df('XAUUSDrfd', TIME_FRAME)
            isNewBar, lastCheckedTime = alligator.IsNewBar(df_for_new_bar, lastCheckedTime, TIME_FRAME)

            active_symbols = [s for s in symbols if dict.symbolTradingStatus.get(s, 0) < 3]

            # Получаем позиции один раз за итерацию (из кэша)
            all_orders = trading.getPositions()

            for symbol in active_symbols:
                # Получаем MA (данные берутся из кэша при повторном запросе)
                fast_ma = ma.get_ma_for_symbol(symbol, TIME_FRAME, 8)
                slow_ma = ma.get_ma_for_symbol(symbol, TIME_FRAME, 21)
                signal_ma = ma.ma_simple_signal(fast_ma, slow_ma)

                # ATR вычисляем один раз и передаём в MA-методы
                atr_calc = atr.calculate_atr(symbol, TIME_FRAME)
                atr_value = atr_calc.iloc[-1]

                signal_critical_angle_ma = ma.ma_critical_angle(fast_ma, slow_ma, symbol, atr_value)

                # MACD (данные из кэша)
                hist_line, prev_hist_line, signal_line = macd.calculate_macd_manual(symbol, TIME_FRAME)
                MACD_signal = macd.MACD_signal(hist_line, prev_hist_line, signal_line)

                # ADX (используем уже загруженный df из кэша)
                df = alligator.Df(symbol, TIME_FRAME)
                adx_values, plus_di_values, minus_di_values = adx.ADX(
                    df['high'].values,
                    df['low'].values,
                    df['close'].values,
                    14
                )
                ADX_signal = adx.ADX_signal(adx_values[-1], plus_di_values[-1], minus_di_values[-1])

                # RSI (данные из кэша, 100 баров вместо 1000)
                rsi_value = rsi.get_rsi_talib(symbol, TIME_FRAME)
                rsi_signal = rsi.RSI_signal(rsi_value['RSI'].iloc[-1], rsi_value['RSI'].iloc[-2], rsi_value['RSI'].iloc[-3])

                previous_status = previous_statuses.get(symbol, 0)
                current_status = dict.symbolTradingStatus.get(symbol, 0)

                if isNewBar and current_status == 1:
                    dict.symbolTradingStatus[symbol] = 0
                    current_status = 0

                if isNewBar and current_status == 2 and MACD_signal['signal'] == 'NO_SIGNAL':
                    dict.symbolTradingStatus[symbol] = 0
                    current_status = 0

                if signal_ma['signal'] == 'BUY' and MACD_signal['signal'] == 'BUY' and rsi_signal['signal'] == 'BUY':
                    sum_signal = 'BUY'
                elif signal_ma['signal'] == 'SELL' and MACD_signal['signal'] == 'SELL' and rsi_signal['signal'] == 'SELL':
                    sum_signal = 'SELL'
                else:
                    sum_signal = 'NO_SIGNAL'

                if isNewBar:
                    # Используем уже загруженные позиции вместо повторного вызова
                    if len(all_orders) > 0:
                        for order in all_orders:
                            order_dict = order._asdict()
                            profit = order_dict.get("profit", 0)
                            ticketId = order_dict.get("ticket", 0)
                            order_symbol = order_dict.get("symbol", 0)
                            order_type = order_dict.get("type", 0)

                            if symbol == order_symbol:
                                print("проверка на стопЛосс")
                                condition_sl = profit > dict.symbolStopLossValue[symbol]

                                # ФИКС: определяем направление один раз
                                is_long = order_type == 0  # BUY
                                condition_rsi = rsi_signal['rsi'] < 45 if is_long else rsi_signal['rsi'] > 55
                                # ФИКС: правильный текст для SHORT (было "ЗАКРЫТИЕ LONG")
                                direction_text = "LONG" if is_long else "SHORT"

                                if condition_sl:
                                    dict.symbolTradingStatus[symbol] = 2
                                if condition_sl or condition_rsi:
                                    trading.orderClose(ticketId, symbol)

                                    if CHAT_ID:
                                        reason = ""
                                        if condition_sl:
                                            reason = "Закрытие по Stop Loss"
                                        if condition_rsi:
                                            reason = "Закрытие по RSI"
                                        result = "😊" if profit > 0 else "😡"

                                        telegram_message = (
                                            f"{result} ЗАКРЫТИЕ {direction_text} ПОЗИЦИИ\n\n"
                                            f"💵 Пара: {symbol}\n"
                                            f"💰 Профит: {profit:.2f}\n"
                                            f"🎯 Причина: {reason}\n"
                                            f"🎯 RSI: {rsi_value['RSI'].iloc[-1]}\n"
                                            f"🎯 StopLoss: {dict.symbolStopLossValue[symbol]}"
                                        )
                                        asyncio.run_coroutine_threadsafe(
                                            trading_bot.send_telegram_message(telegram_message),
                                            trading_bot.loop
                                        )

                    if rsi_value['RSI'].iloc[-1] > 70 or rsi_value['RSI'].iloc[-1] < 30:
                        dict.symbolExtremumStatus[symbol] = 1
                    if 65 > rsi_value['RSI'].iloc[-1] > 50 or 50 > rsi_value['RSI'].iloc[-1] > 35:
                        dict.symbolExtremumStatus[symbol] = 0
                    print(f"{symbol} signal_ma: {signal_ma['signal']} MACD_signal: {MACD_signal['signal']} ADX_signal: {ADX_signal['signal']} rsi_signal: {rsi_signal['signal']} angle: {signal_critical_angle_ma['angle_fast']}")
                    message = (
                        f"📊 Значение индикаторов\n\n"
                        f"🔢 Пара: {symbol}\n"
                        f"🔄 Сигнал МА: {signal_ma['signal']}\n"
                        f"🔄 Угол fast_ma: {signal_critical_angle_ma['angle_fast']}\n\n"
                        f"🔄 Сигнал MACD: {MACD_signal['signal']}\n"
                        f"🔄 Предыдущее значение: {MACD_signal['prev_hist_line']:.5f}\n"
                        f"🔄 Текущее значение: {MACD_signal['hist_line']:.5f}\n"
                        f"🔄 Сигнальнная линия: {MACD_signal['signal_line']:.5f}\n\n"
                        f"🔄 Сигнал RSI: {rsi_signal['signal']}\n"
                        f"🔄 Экстремум статус: {dict.symbolExtremumStatus.get(symbol, 0)}\n"
                        f"🔄 Предпредыдущее значение: {rsi_signal['prev2_rsi']:.5f}\n"
                        f"🔄 Предыдущее значение: {rsi_signal['prev_rsi']:.5f}\n"
                        f"🔄 Текущее значение: {rsi_signal['rsi']:.5f}\n\n"
                        f"🔄 Стоп-лосс: {dict.symbolStopLossValue[symbol]}\n\n"
                        f"⏰ Время: {trading.serverTime(symbol)}\n"
                    )

                    if CHAT_ID:
                        asyncio.run_coroutine_threadsafe(
                            trading_bot.send_telegram_message(message),
                            trading_bot.loop
                        )

                    if sum_signal != 'NO_SIGNAL' and dict.symbolTradingStatus[symbol] == 0:
                        trading_bot.checkOpen(symbol, sum_signal, 'sum_signal', atr_value, signal_ma, signal_critical_angle_ma, MACD_signal, rsi_signal)

                # Проверяем изменение статуса
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

                    previous_statuses[symbol] = current_status

        except Exception as e:
            print(f"Ошибка: {str(e)}")

        time.sleep(10)

if __name__ == '__main__':
    # Инициализация торгового бота
    trading_bot = TradingBot(trading, dict, alligator, AMA)

    # Запуск телеграм бота в отдельном потоке
    bot_thread = threading.Thread(target=trading_bot.run_bot, daemon=True)
    bot_thread.start()

    # Запуск основного торгового цикла
    trading_loop()
