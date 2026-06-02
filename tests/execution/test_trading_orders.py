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
