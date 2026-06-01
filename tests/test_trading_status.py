"""Юнит-тесты TradingStatusRegistry (слайс B1). Без MT5."""
import pytest

from trading_status import TradingStatusRegistry, ALLOWED, OPEN, DISABLED


def _reg():
    # изолированный seed, чтобы тесты не зависели от глобального синглтона
    return TradingStatusRegistry(seed={"XAUUSDrfd": ALLOWED, "EURUSDrfd": DISABLED, "#LCO": ALLOWED})


def test_seed_values():
    r = _reg()
    assert r.status_of("XAUUSDrfd") == ALLOWED
    assert r.status_of("EURUSDrfd") == DISABLED
    assert r.status_of("#LCO") == ALLOWED


def test_has_and_contains():
    r = _reg()
    assert r.has("XAUUSDrfd") is True
    assert ("XAUUSDrfd" in r) is True
    assert r.has("NOPE") is False
    assert ("NOPE" in r) is False


def test_status_of_unknown_is_disabled():
    assert _reg().status_of("UNKNOWN") == DISABLED


def test_is_helpers():
    r = _reg()
    assert r.is_allowed("XAUUSDrfd") is True
    assert r.is_disabled("EURUSDrfd") is True
    assert r.is_open("XAUUSDrfd") is False


def test_mark_open_and_allowed():
    r = _reg()
    r.mark_open("XAUUSDrfd")
    assert r.is_open("XAUUSDrfd") is True
    r.mark_allowed("XAUUSDrfd")
    assert r.is_allowed("XAUUSDrfd") is True


def test_set_status_raw():
    r = _reg()
    r.set_status("EURUSDrfd", ALLOWED)
    assert r.status_of("EURUSDrfd") == ALLOWED
    r.set_status("EURUSDrfd", 99)  # сырое значение принимается без валидации
    assert r.status_of("EURUSDrfd") == 99


def test_activate_only_sets_target_allowed_others_disabled():
    r = _reg()
    r.set_status("EURUSDrfd", ALLOWED)
    r.activate_only("XAUUSDrfd")
    assert r.is_allowed("XAUUSDrfd")
    assert r.is_disabled("EURUSDrfd")
    assert r.is_disabled("#LCO")


def test_activate_only_skips_open_symbols():
    r = _reg()
    r.mark_open("EURUSDrfd")          # символ с открытой позицией
    r.activate_only("XAUUSDrfd")
    assert r.is_allowed("XAUUSDrfd")
    assert r.is_open("EURUSDrfd")      # OPEN не сброшен


def test_sync_enabled():
    r = _reg()
    r.sync_enabled({"XAUUSDrfd", "#LCO"})
    assert r.is_allowed("XAUUSDrfd")
    assert r.is_allowed("#LCO")
    assert r.is_disabled("EURUSDrfd")


def test_sync_enabled_skips_open():
    r = _reg()
    r.mark_open("EURUSDrfd")
    r.sync_enabled({"XAUUSDrfd"})      # EURUSDrfd не в наборе, но OPEN
    assert r.is_open("EURUSDrfd")       # не тронут
    assert r.is_allowed("XAUUSDrfd")


def test_active_symbols_excludes_disabled():
    r = _reg()
    r.set_status("EURUSDrfd", ALLOWED)
    active = set(r.active_symbols())
    assert "XAUUSDrfd" in active
    assert "EURUSDrfd" in active
    assert "#LCO" in active  # ALLOWED по seed
    r.set_status("#LCO", DISABLED)
    assert "#LCO" not in set(r.active_symbols())


def test_symbols_lists_all_keys():
    r = _reg()
    assert set(r.symbols()) == {"XAUUSDrfd", "EURUSDrfd", "#LCO"}


def test_snapshot_is_a_copy():
    r = _reg()
    snap = r.snapshot()
    snap["XAUUSDrfd"] = 999
    assert r.status_of("XAUUSDrfd") == ALLOWED  # внутреннее состояние не изменилось
