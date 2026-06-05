"""Фикстуры и параметризация для тестов стратегий."""
from pathlib import Path

import pandas as pd
import pytest

from strategies import STRATEGIES

# (имя, класс) для параметризации по всем стратегиям реестра
ALL_STRATEGIES = list(STRATEGIES.items())
STRATEGY_IDS = [name for name, _ in ALL_STRATEGIES]

_FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "xauusd_h1.csv"


@pytest.fixture(scope="session")
def real_ohlc() -> pd.DataFrame:
    """~500 реальных баров XAUUSD H1. Каждый тест получает свежую копию через .copy()."""
    if not _FIXTURE.exists():
        pytest.skip(f"Нет фикстуры {_FIXTURE} — запустите tools/dump_ohlc.py")
    df = pd.read_csv(_FIXTURE, parse_dates=["time"])
    return df


@pytest.fixture(params=ALL_STRATEGIES, ids=STRATEGY_IDS)
def strategy(request):
    """Свежий экземпляр стратегии (минуя runtime-singleton, чтобы состояние не протекало)."""
    name, cls = request.param
    return cls()
