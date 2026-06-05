"""A2: golden-снимки сигнальных серий на реальном CSV XAUUSD H1.

Первый прогон с `--update-golden` создаёт baseline-файлы.
Последующие прогоны строго сравнивают текущее поведение с baseline.
"""
import pytest

from tests.strategies import golden_utils


def test_golden_signal_series(strategy, real_ohlc, request):
    update = request.config.getoption("--update-golden")
    series = golden_utils.run_signal_series(strategy, real_ohlc.copy())

    if update:
        golden_utils.save_golden(strategy.name, series)
        pytest.skip(f"golden обновлён для {strategy.name}")

    if not golden_utils.golden_path(strategy.name).exists():
        pytest.fail(
            f"Нет golden для {strategy.name}. "
            f"Сгенерируйте: pytest tests/strategies/test_golden.py --update-golden"
        )

    expected = golden_utils.load_golden(strategy.name)
    assert series == expected, (
        f"{strategy.name}: сигнальная серия изменилась относительно golden. "
        f"Если изменение намеренное — обновите через --update-golden."
    )
