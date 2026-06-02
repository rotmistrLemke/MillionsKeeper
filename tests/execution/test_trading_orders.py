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


class TestOrderClose:
    def test_no_position_returns_false_without_send(self, patched_trading):
        t = patched_trading
        t.mt5.positions = []
        assert t.trading.orderClose(555, "S", "TP") is False
        assert t.mt5.sent == []

    def test_tick_none_returns_false(self, patched_trading):
        t = patched_trading
        t.mt5.positions = [make_position(t.mt5)]
        t.mt5.tick = None
        assert t.trading.orderClose(555, "S", "TP") is False
        assert t.mt5.sent == []

    def test_closing_buy_uses_sell_at_bid(self, patched_trading):
        t = patched_trading
        t.mt5.positions = [make_position(t.mt5, type=t.mt5.ORDER_TYPE_BUY, magic=42)]
        ok = t.trading.orderClose(555, "S", "TP")
        assert ok is True
        req = t.mt5.sent[0]
        assert req["type"] == t.mt5.ORDER_TYPE_SELL
        assert req["price"] == t.mt5.tick.bid
        assert req["position"] == 555
        assert req["magic"] == 42

    def test_closing_sell_uses_buy_at_ask(self, patched_trading):
        t = patched_trading
        t.mt5.positions = [make_position(t.mt5, type=t.mt5.ORDER_TYPE_SELL)]
        t.trading.orderClose(555, "S", "TP")
        req = t.mt5.sent[0]
        assert req["type"] == t.mt5.ORDER_TYPE_BUY
        assert req["price"] == t.mt5.tick.ask

    def test_comment_truncated_to_31(self, patched_trading):
        t = patched_trading
        t.mt5.positions = [make_position(t.mt5)]
        long_comment = "X" * 50
        t.trading.orderClose(555, "S", long_comment)
        assert t.mt5.sent[0]["comment"] == "X" * 31

    def test_result_none_returns_false(self, patched_trading):
        t = patched_trading
        t.mt5.positions = [make_position(t.mt5)]
        t.mt5.set_result_none()
        assert t.trading.orderClose(555, "S", "TP") is False

    def test_retcode_not_done_returns_false(self, patched_trading):
        t = patched_trading
        t.mt5.positions = [make_position(t.mt5)]
        t.mt5.set_result(retcode=10004, order=1, price=1900.0)
        assert t.trading.orderClose(555, "S", "TP") is False


class TestModifySL:
    def test_no_position_returns_false(self, patched_trading):
        t = patched_trading
        t.mt5.positions = []
        assert t.trading.modifySL(555, "S", 1899.0) is False
        assert t.mt5.sent == []

    def test_buy_sl_too_close_blocked_without_send(self, patched_trading):
        # point=0.01, trade_stops_level=10 → min_dist=0.1; bid=1900 → порог 1899.9
        t = patched_trading
        t.mt5.positions = [make_position(t.mt5, type=t.mt5.ORDER_TYPE_BUY)]
        assert t.trading.modifySL(555, "S", 1899.95) is False  # >= 1899.9
        assert t.mt5.sent == []

    def test_sell_sl_too_close_blocked_without_send(self, patched_trading):
        # SELL: ref=ask=1900.5; порог = 1900.5 + 0.1 = 1900.6
        t = patched_trading
        t.mt5.positions = [make_position(t.mt5, type=t.mt5.ORDER_TYPE_SELL)]
        assert t.trading.modifySL(555, "S", 1900.55) is False  # <= 1900.6
        assert t.mt5.sent == []

    def test_valid_buy_sl_sends_sltp_rounded(self, patched_trading):
        t = patched_trading
        t.mt5.positions = [make_position(t.mt5, type=t.mt5.ORDER_TYPE_BUY, tp=1950.0)]
        ok = t.trading.modifySL(555, "S", 1899.0)  # < 1899.9 → разрешено
        assert ok is True
        req = t.mt5.sent[0]
        assert req["action"] == t.mt5.TRADE_ACTION_SLTP
        assert req["position"] == 555
        assert req["sl"] == 1899.0                 # round(1899.0, digits=2)
        assert req["tp"] == 1950.0                 # по умолчанию из pos.tp

    def test_explicit_new_tp_used(self, patched_trading):
        t = patched_trading
        t.mt5.positions = [make_position(t.mt5, type=t.mt5.ORDER_TYPE_BUY, tp=1950.0)]
        t.trading.modifySL(555, "S", 1899.0, new_tp=1975.0)
        assert t.mt5.sent[0]["tp"] == 1975.0

    def test_retcode_not_done_returns_false(self, patched_trading):
        t = patched_trading
        t.mt5.positions = [make_position(t.mt5, type=t.mt5.ORDER_TYPE_BUY)]
        t.mt5.set_result(retcode=10004, order=1, price=0.0)
        assert t.trading.modifySL(555, "S", 1899.0) is False


class TestOrderOpenFindings:
    @pytest.mark.xfail(
        reason="находка E1: при order_send→None строка trading.py:70 'result.order' "
               "даёт AttributeError; желаемое поведение — graceful-возврат без падения",
        raises=AttributeError, strict=True,
    )
    def test_order_send_none_should_not_crash(self, patched_trading):
        t = patched_trading
        t.mt5.set_result_none()
        # Желаемое: не падать, а вернуть результат с order=None (или None).
        out = t.trading.orderOpen("S", TargetType.LONG, 0.1, "c")
        assert out["order"] is None
