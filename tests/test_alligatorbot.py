import sys
import types
from types import SimpleNamespace
import importlib

# Подготовим фейковый mt5 перед импортом модуля
fake_mt5 = types.ModuleType('MetaTrader5')
fake_mt5.TIMEFRAME_H1 = 1
fake_mt5.initialize = lambda: True
fake_mt5.shutdown = lambda: True
fake_mt5.last_error = lambda: 'fake error'
fake_mt5.ORDER_TYPE_BUY = 0
fake_mt5.ORDER_TYPE_SELL = 1
fake_mt5.TRADE_ACTION_DEAL = 0
fake_mt5.TRADE_RETCODE_DONE = 0
fake_mt5.ORDER_TIME_GTC = 0
fake_mt5.ORDER_FILLING_FOK = 0

import time
import random

def fake_copy_rates_from_pos(symbol, timeframe, start, count):
    now = int(time.time())
    bars = []
    base = 1.0 if 'XAU' not in symbol else 1800.0
    for i in range(count):
        t = now - i * 3600
        o = base + random.uniform(-0.5, 0.5)
        h = o + random.uniform(0, 0.5)
        l = o - random.uniform(0, 0.5)
        c = o + random.uniform(-0.2, 0.2)
        bars.append({'time': t, 'open': o, 'high': h, 'low': l, 'close': c, 'tick_volume': 1, 'spread': 1, 'real_volume': 1})
    return bars

fake_mt5.copy_rates_from_pos = fake_copy_rates_from_pos
fake_mt5.symbol_info = lambda symbol: SimpleNamespace(point=0.0001, trade_contract_size=100000, visible=True, volume_max=100, volume_min=0.01, volume_step=0.01, currency_profit='USD', currency_margin='USD')
fake_mt5.symbol_info_tick = lambda symbol: SimpleNamespace(bid=1.0, ask=1.0001, time=int(time.time()))
fake_mt5.positions_get = lambda: ()
fake_mt5.order_calc_margin = lambda *args: 100.0
fake_mt5.account_info = lambda: SimpleNamespace(balance=10000, equity=10000, margin_free=5000)
sys.modules['MetaTrader5'] = fake_mt5

import alligatorBot
import_alligator = importlib.reload(alligatorBot)


def test_df_returns_dataframe():
    """Тест: Alligator.Df возвращает DataFrame с данными."""
    symbols = list(import_alligator.X_VALUE_DICT.keys())
    assert len(symbols) > 0
    symbol = symbols[0]

    df = import_alligator.alligator.Df(symbol, import_alligator.TIME_FRAME)
    assert df is not None and not df.empty


def test_checkOpen_calls_orderOpen_on_buy_signal():
    """Тест: checkOpen вызывает orderOpen при BUY сигнале."""
    calls = {'orderOpen': False}

    class FakeTrading:
        def serverTime(self, symbol):
            return 'now'
        def getPositions(self):
            return ()
        def symbolInPostions(self, symbol, target):
            return False
        def calculateSafeTradeWithMargin(self, symbol, risk_percent, stop_loss_pips, order_type):
            return 0.1
        def orderOpen(self, symbol, targetType, volume, comment):
            calls['orderOpen'] = True
            return True

    fake_trading = FakeTrading()
    bot = import_alligator.TradingBot(fake_trading, import_alligator.dict, import_alligator.alligator, import_alligator.AMA)

    # Подменяем глобальный trading на фейковый
    old_trading = import_alligator.trading
    import_alligator.trading = fake_trading

    symbols = list(import_alligator.X_VALUE_DICT.keys())
    symbol = symbols[0]
    bot.dict.symbolTradingStatus[symbol] = 0

    signal = 'BUY'
    comment = 'test'
    atr_val = 1.0
    signal_ma = {'signal': 'BUY'}
    signal_critical_angle_ma = {'angle_fast': 0}
    MACD_signal = {'signal': 'BUY', 'hist_line': 0.5, 'prev_hist_line': 0.1, 'signal_line': 0.05}
    rsi_signal = {'signal': 'BUY', 'rsi': 55.0, 'prev_rsi': 52.0, 'prev2_rsi': 50.0}

    bot.checkOpen(symbol, signal, comment, atr_val, signal_ma, signal_critical_angle_ma, MACD_signal, rsi_signal)

    import_alligator.trading = old_trading
    assert calls['orderOpen'] is True
