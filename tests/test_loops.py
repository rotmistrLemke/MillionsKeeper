import unittest
import types
import importlib
import sys
from types import SimpleNamespace
from unittest import mock


class TestLoops(unittest.TestCase):
    def setUp(self):
        fake_mt5 = types.ModuleType('MetaTrader5')
        fake_mt5.TIMEFRAME_H1 = 1
        fake_mt5.ORDER_TYPE_BUY = 0
        fake_mt5.ORDER_TYPE_SELL = 1
        fake_mt5.TRADE_ACTION_DEAL = 0
        fake_mt5.TRADE_RETCODE_DONE = 0
        fake_mt5.ORDER_TIME_GTC = 0
        fake_mt5.ORDER_FILLING_FOK = 0
        fake_mt5.initialize = lambda: True
        fake_mt5.shutdown = lambda: True
        fake_mt5.last_error = lambda: 'fake error'

        import time, random
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
        importlib.reload(alligatorBot)
        self.alligatorBot = alligatorBot

    def test_trading_loop_one_iteration(self):
        """Тест: trading_loop выполняет одну итерацию без ошибок."""
        class FakeTrading:
            def getPositions(self):
                return ()
            def orderClose(self, ticket, symbol):
                pass
            def serverTime(self, symbol):
                return 'now'
            def symbolInPostions(self, symbol, target):
                return False
            def calculateSafeTradeWithMargin(self, *args, **kwargs):
                return 0
            def orderOpen(self, *args, **kwargs):
                return False

        fake_trading = FakeTrading()
        bot = self.alligatorBot.TradingBot(fake_trading, self.alligatorBot.dict, self.alligatorBot.alligator, self.alligatorBot.AMA)

        self.alligatorBot.trading_bot = bot
        self.alligatorBot.trading = fake_trading
        bot.ensure_mt5_connection = lambda: True

        counter = {'c': 0}
        def fake_sleep(sec):
            counter['c'] += 1
            if counter['c'] > 1:
                raise StopIteration()

        with mock.patch.object(self.alligatorBot.time, 'sleep', fake_sleep):
            try:
                self.alligatorBot.trading_loop()
            except StopIteration:
                pass

        self.assertTrue(True)

if __name__ == '__main__':
    unittest.main()
