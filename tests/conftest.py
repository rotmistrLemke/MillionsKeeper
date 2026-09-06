"""Pytest-конфигурация для тестов.

Если установленный MetaTrader5 неполноценен (нет TIMEFRAME_M1) или отсутствует,
подменяем его модулем-заглушкой в sys.modules ДО импорта settings/indicators,
чтобы тесты собирались на любой машине без живого терминала.
"""
import sys
import types

import pytest


def _install_mt5_stub() -> None:
    try:
        import MetaTrader5 as _mt5
        if hasattr(_mt5, "TIMEFRAME_M1"):
            return  # реальный модуль пригоден
    except Exception:
        pass

    stub = types.ModuleType("MetaTrader5")
    for i, name in enumerate(
        ["TIMEFRAME_M1", "TIMEFRAME_M5", "TIMEFRAME_M15", "TIMEFRAME_M30",
         "TIMEFRAME_H1", "TIMEFRAME_H4", "TIMEFRAME_D1"],
        start=1,
    ):
        setattr(stub, name, i)

    def _noop(*args, **kwargs):
        return None

    # любое неизвестное обращение (функции инициализации и т.п.) → no-op
    stub.__getattr__ = lambda name: _noop  # type: ignore[attr-defined]
    sys.modules["MetaTrader5"] = stub


_install_mt5_stub()

# Pre-import settings while the stub is active so that test modules that
# install their own incomplete MT5 fakes (missing TIMEFRAME_M1) cannot cause
# a fresh import of settings to fail — Python will reuse the cached copy.
import settings  # noqa: E402  (intentional late import)


def pytest_addoption(parser):
    parser.addoption(
        "--update-golden",
        action="store_true",
        default=False,
        help="Перезаписать golden-снимки текущим поведением вместо сравнения.",
    )


@pytest.fixture(autouse=True)
def _isolate_signal_journal(tmp_path, monkeypatch):
    """Журнал отказов в тестах пишется в tmp, а не в боевую signals/signals.db.

    ExecutionAgent/IndicatorAgent пишут отказы прямо в ходе обычных тестов —
    без этой изоляции прогон засорял рабочую БД строками вроде strategy='mystrat'.
    """
    from signals import journal
    monkeypatch.setattr(journal, "_DEFAULT_DB", tmp_path / "signals.db")


@pytest.fixture(autouse=True)
def _isolate_portfolio_guard(tmp_path, monkeypatch):
    """Портфельный страж в тестах — свой, с выключенными лимитами и состоянием
    в tmp.

    Боевой `portfolio.guard` создаётся на импорте модуля и читает
    config/portfolio.json. Без изоляции любой тест ExecutionAgent начинал
    писать пик equity в portfolio_state.json репозитория, а боевые лимиты
    молча меняли поведение чужих тестов. Тесты самого стража подменяют
    guard своим экземпляром поверх этой фикстуры.
    """
    import portfolio
    monkeypatch.setattr(
        portfolio, "guard",
        portfolio.PortfolioGuard(portfolio.PortfolioLimits(),
                                 state_path=tmp_path / "portfolio_state.json"),
    )
