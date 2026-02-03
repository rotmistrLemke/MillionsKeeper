import sys
import types
import time
import datetime
import random
from types import SimpleNamespace

# Создаём "фейковый" модуль MetaTrader5 до импорта проекта
fake_mt5 = types.ModuleType('MetaTrader5')

# Константы
fake_mt5.TIMEFRAME_H1 = 1
fake_mt5.ORDER_TYPE_BUY = 0
fake_mt5.ORDER_TYPE_SELL = 1
fake_mt5.TRADE_ACTION_DEAL = 0
fake_mt5.TRADE_RETCODE_DONE = 0
fake_mt5.ORDER_TIME_GTC = 0
fake_mt5.ORDER_FILLING_FOK = 0

# Простейшие реализации
def fake_initialize():
    return True

def fake_login(**kwargs):
    return True

def fake_shutdown():
    return True

def fake_terminal_info():
    return True

def fake_last_error():
    return "fake error"

# symbol info
class FakeSymbolInfo:
    def __init__(self, point=0.0001, trade_contract_size=100000, currency_profit='USD', currency_margin='USD', visible=True):
        self.point = point
        self.trade_contract_size = trade_contract_size
        self.currency_profit = currency_profit
        self.currency_margin = currency_margin
        self.visible = visible

class FakeTick:
    def __init__(self, bid=1.0):
        self.bid = bid

fake_mt5.initialize = fake_initialize
fake_mt5.login = fake_login
fake_mt5.shutdown = fake_shutdown
fake_mt5.terminal_info = fake_terminal_info
fake_mt5.last_error = fake_last_error

# Возвращаем простую структуру для symbol_info
def fake_symbol_info(symbol):
    # Немного различаем XAU/XAG
    if 'XAU' in symbol or 'XAG' in symbol:
        return FakeSymbolInfo(point=0.01, trade_contract_size=100, currency_profit='USD', currency_margin='USD')
    return FakeSymbolInfo()

fake_mt5.symbol_info = fake_symbol_info
fake_mt5.symbol_info_tick = lambda symbol: FakeTick(bid=round(1.0 + random.random() * 0.01, 5))

# simple positions_get -> empty
fake_mt5.positions_get = lambda: []

# copy_rates_from_pos: return list of dicts acceptable for pd.DataFrame
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

# order_send and Close
fake_mt5.order_send = lambda req: SimpleNamespace(retcode=fake_mt5.TRADE_RETCODE_DONE, order=random.randint(1000,9999), price=round(1.0+random.random()*0.01,5))
fake_mt5.Close = lambda symbol, ticket: True
fake_mt5.symbol_select = lambda symbol, flag: True

# account_info
fake_mt5.account_info = lambda: SimpleNamespace(margin_free=10000.0)

# attach to sys.modules before importing project
sys.modules['MetaTrader5'] = fake_mt5

# Теперь импортируем проект и выполним безопасный dry-run
import alligatorBot

print('Symbols:', list(alligatorBot.X_VALUE_DICT.keys()))

# Выполним one-shot кеширование индикаторов для каждой пары
for symbol in alligatorBot.X_VALUE_DICT.keys():
    try:
        df = alligatorBot.alligator.Df(symbol, alligatorBot.TIME_FRAME)
        if df is None:
            print(symbol, 'no data')
            continue
        alligatorBot.update_indicator_cache(symbol, df)
        cached = alligatorBot.indicator_cache.get(symbol)
        if cached:
            print(symbol, 'cached: atr_value=', cached.get('atr_value'), 'MACD_signal=', cached.get('MACD_signal'))
        else:
            print(symbol, 'no cache')
    except Exception as e:
        print('Error for', symbol, e)

print('Dry-run finished')
