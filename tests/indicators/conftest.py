"""Харнесс характеризации indicators.py (E6). Прод не трогаем."""
import pytest
from tests.execution.fakes import FakeCache


@pytest.fixture
def indicators_cache(monkeypatch):
    """Монкипатчит indicators.cache на FakeCache; возвращает фейк.

    ВАЖНО: indicators.py делает `from market_data_cache import cache` → собственный
    модульный binding. Патчим именно indicators.cache (а не market_data_cache.cache).
    Покрывает и вложенные ATR()/Alligator() — они тоже читают indicators.cache.
    Настройка в тесте: fake.symbol_info.point=..., fake.rates_df=<DataFrame>.
    """
    import indicators as ind_mod
    fake = FakeCache()
    monkeypatch.setattr(ind_mod, "cache", fake)
    return fake
