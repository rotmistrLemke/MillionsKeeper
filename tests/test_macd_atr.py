import unittest
import types
import sys
from types import SimpleNamespace

# Подменим MetaTrader5
fake_mt5 = types.ModuleType('MetaTrader5')
fake_mt5.initialize = lambda: True
fake_mt5.TIMEFRAME_H1 = 1
fake_mt5.last_error = lambda: 'fake error'

# Сформируем 100 баров с увеличивающимися значениями для детерминированности
def fake_rates(symbol, timeframe, start, count):
    bars = []
    base = 1.0
    for i in range(count):
        o = base + i*0.01
        h = o + 0.005
        l = o - 0.005
        c = o + 0.002
        bars.append({'time': i, 'open': o, 'high': h, 'low': l, 'close': c, 'tick_volume':1,'spread':1,'real_volume':1})
    return bars

fake_mt5.copy_rates_from_pos = fake_rates
fake_mt5.symbol_info = lambda s: SimpleNamespace(point=0.0001)
sys.modules['MetaTrader5'] = fake_mt5

import indicators
import market_data_cache
# Принудительно биндим фейк в УЖЕ импортированные модули. Если market_data_cache был
# импортирован раньше (другим тест-файлом, например tests/indicators/*) при активном
# реальном MetaTrader5, его модульный глобал mt5 указывает на реальный пакет, и
# ATR.calculate_atr через cache.get_rates позвал бы реальный copy_rates_from_pos
# (-10004 «No IPC connection»). Явное присваивание делает этот тест независимым от
# порядка сборки/прогона pytest. Кэш сбрасываем, чтобы ключи не были загрязнены.
market_data_cache.mt5 = fake_mt5
indicators.mt5 = fake_mt5
market_data_cache.cache.invalidate()
from indicators import MACD, ATR

class TestMACDATR(unittest.TestCase):
    def test_macd_signal_logic(self):
        macd = MACD()
        buy = macd.MACD_signal(0.5, 0.1, 0.05)
        self.assertEqual(buy['signal'], 'BUY')
        sell = macd.MACD_signal(-0.5, -0.1, -0.05)
        self.assertEqual(sell['signal'], 'SELL')
        no = macd.MACD_signal(0.0, 0.0, 0.0)
        self.assertEqual(no['signal'], 'NO_SIGNAL')

    def test_atr_returns_series(self):
        atr_obj = ATR()
        tr = atr_obj.calculate_atr('EURUSD', fake_mt5.TIMEFRAME_H1)
        self.assertTrue(hasattr(tr, 'rolling'))
        self.assertGreaterEqual(len(tr), 14)

if __name__ == '__main__':
    unittest.main()
