"""Характеризационные тесты денежного пути trading.py (orderOpen/orderClose/modifySL).

Это характеризация существующего кода: тест фиксирует ТЕКУЩЕЕ поведение.
Если тест красный — сверяемся с кодом и правим ожидание под факт (не код).
"""
from types import SimpleNamespace

import pytest

from settings import TargetType
from tests.execution.fakes import make_position


def test_harness_imports_and_patches(patched_trading):
    t = patched_trading
    assert t.trading is not None
    assert t.mt5.sent == []
    assert t.cache.get_symbol_info("X").visible is True


class TestOrderOpen:
    def test_long_happy_path_builds_buy_deal(self, patched_trading):
        t = patched_trading
        out = t.trading.orderOpen("XAUUSDrfd", TargetType.LONG, 0.1, "c1")
        assert len(t.mt5.sent) == 1
        req = t.mt5.sent[0]
        assert req["action"] == t.mt5.TRADE_ACTION_DEAL
        assert req["type"] == t.mt5.ORDER_TYPE_BUY
        assert req["symbol"] == "XAUUSDrfd"
        assert req["volume"] == 0.1
        assert req["price"] == t.mt5.tick.bid          # bid для LONG (текущее поведение)
        assert req["comment"] == "c1"
        assert req["type_filling"] == t.mt5.ORDER_FILLING_FOK
        assert req["type_time"] == t.mt5.ORDER_TIME_GTC
        assert out == {"order": 12345, "price": t.mt5.tick.bid,
                       "symbol": "XAUUSDrfd", "targetType": TargetType.LONG}

    def test_short_happy_path_builds_sell_deal(self, patched_trading):
        t = patched_trading
        t.trading.orderOpen("XAUUSDrfd", TargetType.SHORT, 0.2, "c2")
        req = t.mt5.sent[0]
        assert req["type"] == t.mt5.ORDER_TYPE_SELL
        assert req["price"] == t.mt5.tick.bid           # bid и для SHORT (текущее поведение)
        assert req["volume"] == 0.2

    def test_sl_tp_magic_omitted_when_zero(self, patched_trading):
        t = patched_trading
        t.trading.orderOpen("S", TargetType.LONG, 0.1, "c", sl=0.0, tp=0.0, magic=0)
        req = t.mt5.sent[0]
        assert "sl" not in req
        assert "tp" not in req
        assert "magic" not in req

    def test_sl_tp_magic_included_and_cast_when_positive(self, patched_trading):
        t = patched_trading
        t.trading.orderOpen("S", TargetType.LONG, 0.1, "c",
                            sl=1899.0, tp=1950.0, magic=777)
        req = t.mt5.sent[0]
        assert req["sl"] == 1899.0 and isinstance(req["sl"], float)
        assert req["tp"] == 1950.0 and isinstance(req["tp"], float)
        assert req["magic"] == 777 and isinstance(req["magic"], int)

    def test_mark_open_called_on_done(self, patched_trading):
        t = patched_trading
        t.trading.orderOpen("XAUUSDrfd", TargetType.LONG, 0.1, "c")
        assert t.status.opened == ["XAUUSDrfd"]

    def test_mark_open_not_called_when_retcode_not_done(self, patched_trading):
        t = patched_trading
        t.mt5.set_result(retcode=10004, order=999, price=1900.0)  # REQUOTE, не DONE
        t.trading.orderOpen("XAUUSDrfd", TargetType.LONG, 0.1, "c")
        assert t.status.opened == []

    def test_symbol_select_when_not_visible(self, patched_trading):
        t = patched_trading
        t.cache.symbol_info.visible = False
        t.trading.orderOpen("XAUUSDrfd", TargetType.LONG, 0.1, "c")
        assert t.mt5.selected == [("XAUUSDrfd", True)]
