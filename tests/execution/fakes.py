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
        return self.tick

    def positions_get(self, ticket=None, symbol=None):
        return list(self.positions)

    def last_error(self):
        return self._error

    def symbol_select(self, symbol, enable=True):
        self.selected.append((symbol, enable))
        return True


class FakeCache:
    def __init__(self):
        self.symbol_info = SimpleNamespace(
            visible=True, point=0.01, digits=2, trade_stops_level=10,
        )
        self.positions = []

    def get_symbol_info(self, symbol):
        return self.symbol_info

    def get_positions(self):
        return list(self.positions)


class FakeStatus:
    def __init__(self):
        self.opened = []
        self._status = {}

    def mark_open(self, symbol):
        self.opened.append(symbol)
        self._status[symbol] = 1

    def status_of(self, symbol):
        return self._status.get(symbol, 0)


def make_position(fm, *, ticket=555, type=None, volume=0.1, magic=777, tp=1950.0):
    """Удобный конструктор фейковой позиции MT5."""
    return SimpleNamespace(
        ticket=ticket,
        type=fm.ORDER_TYPE_BUY if type is None else type,
        volume=volume, magic=magic, tp=tp,
    )
