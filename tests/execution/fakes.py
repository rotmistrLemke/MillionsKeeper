"""Фейки MT5/cache/status для характеризационных тестов trading.py.

trading.py держит mt5/cache/status как модульные глобалы, поэтому фикстура
patched_trading (в conftest.py) подменяет их через monkeypatch — боевой код не
меняется. Харнесс переиспользуем для будущих слайсов E2/E3.
"""
from types import SimpleNamespace


class FakeMT5:
    # Различимые sentinel-константы (значения близки к реальным MT5).
    TRADE_ACTION_DEAL = 1
    TRADE_ACTION_SLTP = 2
    ORDER_TYPE_BUY = 0
    ORDER_TYPE_SELL = 1
    ORDER_TIME_GTC = 0
    ORDER_FILLING_FOK = 2
    TRADE_RETCODE_DONE = 10009

    def __init__(self):
        self.sent = []                       # записанные order_send-запросы
        self.tick = SimpleNamespace(bid=1900.0, ask=1900.5, time=1_700_000_000)
        self.positions = []                  # отдаётся positions_get
        self.ticks = {}                      # symbol -> tick override (конверсионные символы)
        self.symbol_infos = {}               # symbol -> info|None для mt5.symbol_info()
        self.margin_per_lot = 100.0          # order_calc_margin (фикс-скаляр; НЕ масштабируется по
                                             # volume — реальный MT5 масштабирует; None для fail-теста)
        self.deals = []                      # отдаётся history_deals_get
        self.rates = None                    # copy_rates_from_pos (None=по умолчанию make_rates(30))
        self.selected = []                   # записанные symbol_select
        self._result = "default"             # "default" → построить успешный результат
        self._error = (1, "fake error")

    # --- настройка из тестов ---
    def set_result(self, retcode=None, order=12345, price=0.0):
        self._result = SimpleNamespace(
            retcode=self.TRADE_RETCODE_DONE if retcode is None else retcode,
            order=order, price=price,
        )

    def set_result_none(self):
        self._result = None

    # --- API, который дёргает trading.py ---
    def order_send(self, request):
        self.sent.append(dict(request))
        if self._result == "default":
            return SimpleNamespace(
                retcode=self.TRADE_RETCODE_DONE, order=12345,
                price=request.get("price", 0.0),
            )
        return self._result

    def symbol_info_tick(self, symbol):
        return self.ticks.get(symbol, self.tick)

    def positions_get(self, ticket=None, symbol=None):
        return list(self.positions)

    def order_calc_margin(self, order_type, symbol, volume, price):
        return self.margin_per_lot

    def symbol_info(self, symbol):
        return self.symbol_infos.get(symbol)

    def copy_rates_from_pos(self, symbol, timeframe, start, count):
        return self.rates if self.rates is not None else make_rates(30)

    def history_deals_get(self, date_from=None, date_to=None, position=None):
        return list(self.deals)

    def last_error(self):
        return self._error

    def symbol_select(self, symbol, enable=True):
        self.selected.append((symbol, enable))
        return True


class FakeCache:
    def __init__(self):
        self.symbol_info = SimpleNamespace(
            visible=True, point=0.01, digits=2, trade_stops_level=10,
            trade_contract_size=100.0, currency_profit="USD", currency_margin="USD",
            volume_min=0.01, volume_max=100.0, volume_step=0.01,
        )
        self.positions = []
        self.account_info = SimpleNamespace(
            balance=10000.0, equity=10000.0, margin_free=5000.0,
        )
        self.rates_df = None                 # get_rates (None → пусто)

    def get_symbol_info(self, symbol):
        return self.symbol_info

    def get_positions(self):
        return list(self.positions)

    def get_account_info(self):
        return self.account_info

    def get_rates(self, symbol, timeframe, bars=None):
        return self.rates_df


class FakeStatus:
    def __init__(self):
        self.opened = []
        self._status = {}
        self._active = []

    def mark_open(self, symbol):
        self.opened.append(symbol)
        self._status[symbol] = 1

    def status_of(self, symbol):
        return self._status.get(symbol, 0)

    def active_symbols(self):
        return list(self._active)


def make_position(fm, *, ticket=555, type=None, volume=0.1, magic=777, tp=1950.0,
                  profit=0.0, swap=0.0, commission=0.0):
    """Удобный конструктор фейковой позиции MT5."""
    return SimpleNamespace(
        ticket=ticket,
        type=fm.ORDER_TYPE_BUY if type is None else type,
        volume=volume, magic=magic, tp=tp,
        profit=profit, swap=swap, commission=commission,
    )


def make_deal(*, magic=777, profit=0.0, commission=0.0, swap=0.0, comment=""):
    """Фейковый закрытый deal MT5 (для history_deals_get)."""
    return SimpleNamespace(magic=magic, profit=profit, commission=commission,
                           swap=swap, comment=comment)


def make_stream(*, id="s1", name="Stream-1", strategy="default", symbol="XAUUSD",
                volume=0.1, sl_atr=0.0, tp_atr=0.0, magic=777, deposit=0.0,
                enabled=True, breakeven_atr=0.0, trail_atr=0.0, timeframe=16385):
    """TradingStream-подобный объект для тестов агентов."""
    return SimpleNamespace(
        id=id, name=name, strategy=strategy, symbol=symbol,
        volume=volume, sl_atr=sl_atr, tp_atr=tp_atr, magic=magic,
        deposit=deposit, enabled=enabled,
        breakeven_atr=breakeven_atr, trail_atr=trail_atr, timeframe=timeframe,
    )


def make_clock(fixed_dt):
    """Фабрика фейк-класса datetime: .now() возвращает зафиксированный реальный datetime."""
    class _FakeDateTime:
        @classmethod
        def now(cls, tz=None):
            return fixed_dt
    return _FakeDateTime


def make_strategy(*, hedge=False, trailing=False):
    """Фабрика фейк-класса стратегии для STRATEGIES."""
    class _FakeStrategy:
        def wants_hedge(self):
            return hedge
        def uses_trailing_exit(self):
            return trailing
    return _FakeStrategy


class FakeBus:
    """Шина для тестов агентов: пишет события, поддерживает subscribe (no-op-хранилище)."""
    def __init__(self):
        self.events = []
        self.subscriptions = []

    def subscribe(self, event_type, handler):
        self.subscriptions.append((event_type, handler))

    async def publish(self, ev):
        self.events.append(ev)

    def publish_sync(self, ev):
        self.events.append(ev)


class FakeRegistry:
    """Подмена streams.registry: get(id) / by_symbol(symbol) поверх dict потоков."""
    def __init__(self, streams=None):
        # streams: dict[id -> stream]
        self._streams = dict(streams or {})

    def get(self, stream_id):
        return self._streams.get(stream_id)

    def by_symbol(self, symbol):
        for s in self._streams.values():
            if s.symbol == symbol:
                return s
        return None

    def by_magic(self, magic):
        for s in self._streams.values():
            if getattr(s, "magic", None) == magic:
                return s
        return None


class FakeTrading:
    """Спай вместо trading.Trading: записывает вызовы orderOpen/orderClose/calc."""
    def __init__(self):
        self.open_calls = []
        self.close_calls = []
        self.calc_calls = []
        self._open_results = None   # None → дефолтный успешный dict на каждый вызов
        self._close_result = True
        self._calc_result = 0.5
        self.positions_list = []             # отдаётся getPositions()
        self.modify_calls = []               # записи modifySL
        self._modify_result = True

    def set_open_result(self, *results):
        """Последовательность результатов orderOpen (1-й — основная нога, 2-й — хедж)."""
        self._open_results = list(results)

    def set_close_result(self, val):
        self._close_result = val

    def set_calc_result(self, val):
        self._calc_result = val

    def orderOpen(self, symbol, order_type, volume, comment, sl=0.0, tp=0.0, magic=0):
        self.open_calls.append(dict(
            symbol=symbol, order_type=order_type, volume=volume,
            comment=comment, sl=sl, tp=tp, magic=magic,
        ))
        if self._open_results is None:
            return {"order": 12345, "price": 1900.5}
        if self._open_results:
            return self._open_results.pop(0)
        return None

    def orderClose(self, ticket, symbol, tag):
        self.close_calls.append(dict(ticket=ticket, symbol=symbol, tag=tag))
        return self._close_result

    def getPositions(self):
        return list(self.positions_list)

    def set_modify_result(self, val):
        self._modify_result = val

    def modifySL(self, ticket, symbol, new_sl, new_tp=None):
        self.modify_calls.append(dict(ticket=ticket, symbol=symbol, new_sl=new_sl, new_tp=new_tp))
        return self._modify_result

    def calculateSafeTradeWithMargin(self, symbol, risk, stop_loss_pips, order_type):
        self.calc_calls.append(dict(
            symbol=symbol, risk=risk, stop_loss_pips=stop_loss_pips, order_type=order_type,
        ))
        return self._calc_result


def make_mt5_position(*, ticket=1001, symbol="XAUUSD", type=0, volume=0.1,
                      price_open=1899.0, sl=0.0, profit=12.34, time=1_700_000_000,
                      magic=777, comment=""):
    """MT5-подобная открытая позиция (для FakeTrading.getPositions). type: 0=BUY,1=SELL."""
    return SimpleNamespace(
        ticket=ticket, symbol=symbol, type=type, volume=volume,
        price_open=price_open, sl=sl, profit=profit, time=time,
        magic=magic, comment=comment,
    )


def make_rates(n=30, *, high=1.05, low=0.95, close=1.0, open_=1.0):
    """numpy structured array баров для copy_rates_from_pos (значения неважны — ATR замокан)."""
    import numpy as np
    arr = np.zeros(n, dtype=[("open", "f8"), ("high", "f8"), ("low", "f8"), ("close", "f8")])
    arr["open"] = open_
    arr["high"] = high
    arr["low"] = low
    arr["close"] = close
    return arr


def make_runtime_strategy(*, exit_signal=False, hedge_exit_signal=False,
                          wants_hedge=False, raise_on_exit=False, raise_on_closed=False):
    """Фейк рантайм-стратегии (под get_runtime_strategy)."""
    class _S:
        def __init__(self):
            self.closed_calls = []
        def compute_indicators(self, df):
            return df
        def compute_flat_indicators(self, df):
            return df
        def get_exit_signal(self, row, pos):
            if raise_on_exit:
                raise RuntimeError("exit boom")
            return exit_signal
        def get_hedge_exit_signal(self, row, pos):
            return hedge_exit_signal
        def wants_hedge(self):
            return wants_hedge
        def on_trade_closed(self, pos, reason):
            if raise_on_closed:
                raise RuntimeError("closed boom")
            self.closed_calls.append((pos, reason))
    return _S()


def make_rsi(value):
    """Фабрика фейк-класса RSI (под indicators.RSI). value=None → нет данных."""
    import pandas as pd
    class _RSI:
        def get_rsi_talib(self, symbol, timeframe):
            if value is None:
                return None
            return {"RSI": pd.Series([value])}
    return _RSI
