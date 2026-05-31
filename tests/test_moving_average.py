import unittest
import importlib
import types
import sys
from types import SimpleNamespace

# Подготовим фейковый модуль MetaTrader5 для безопасного импорта
fake_mt5 = types.ModuleType('MetaTrader5')
fake_mt5.TIMEFRAME_H1 = 1
fake_mt5.initialize = lambda: True
fake_mt5.copy_rates_from_pos = lambda symbol, timeframe, start, count: [{'time': 0, 'open':1,'high':2,'low':0.5,'close':1.5}]*500
fake_mt5.symbol_info = lambda symbol: SimpleNamespace(point=0.0001, trade_contract_size=100000)
sys.modules['MetaTrader5'] = fake_mt5

import indicators
from indicators import MovingAverage
import pandas as pd

class TestMovingAverage(unittest.TestCase):
    def test_sma_simple(self):
        ma = MovingAverage()
        data = pd.Series([1.0,2.0,3.0,4.0,5.0])
        res = ma.sma(data, 3)
        # ожидаем: [nan, nan, 2.0,3.0,4.0]
        self.assertTrue(pd.isna(res.iloc[0]))
        self.assertTrue(pd.isna(res.iloc[1]))
        self.assertAlmostEqual(res.iloc[2], 2.0)
        self.assertAlmostEqual(res.iloc[3], 3.0)
        self.assertAlmostEqual(res.iloc[4], 4.0)

    def test_calculate_ma_dispatch(self):
        ma = MovingAverage()
        data = pd.Series(range(1,11), dtype=float)
        sma = ma.calculate_ma(data, 4, 'SMA')
        ema = ma.calculate_ma(data, 4, 'EMA')
        self.assertEqual(len(sma), len(data))
        self.assertEqual(len(ema), len(data))

if __name__ == '__main__':
    unittest.main()
