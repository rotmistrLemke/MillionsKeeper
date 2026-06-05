"""C/Task2: golden-характеризация ядра движков на синтетике (без MT5).
Запирает текущее поведение перед декомпозицией. Регенерация: --update-golden."""
import pytest

from backtest import _run_default_on_df, _run_strategy_on_df
from strategies.ema_cross import EmaCrossStrategy
from strategies.cci_rsi import CciRsiStrategy
from tests.strategies import builders, golden_utils


def _snapshot(res) -> dict:
    return {
        "summary": {
            "total_trades": res.total_trades,
            "win_rate": round(res.win_rate, 6),
            "total_pnl_points": round(res.total_pnl_points, 4),
            "max_drawdown_points": round(res.max_drawdown_points, 4),
        },
        "trades": [
            {
                "type": t["type"],
                "entry_price": round(float(t["entry_price"]), 4),
                "exit_price": round(float(t["exit_price"]), 4),
                "pnl_points": round(float(t["pnl_points"]), 4),
                "exit_reason": t["exit_reason"],
                "bars_held": int(t["bars_held"]),
            }
            for t in res.trades
        ],
    }


def _check(name, res, request):
    snap = _snapshot(res)
    if request.config.getoption("--update-golden"):
        golden_utils.save_golden(name, snap)
        pytest.skip(f"golden обновлён для {name}")
    if not golden_utils.golden_path(name).exists():
        pytest.fail(f"Нет golden {name}. Сгенерируйте: pytest -k characterization --update-golden")
    assert snap == golden_utils.load_golden(name), f"{name}: поведение движка изменилось"


CASES_DEFAULT = ["trend_up", "trend_down", "flat"]


@pytest.mark.parametrize("shape", CASES_DEFAULT)
def test_default_engine_characterization(shape, request):
    df = getattr(builders, shape)(300)
    res = _run_default_on_df(
        df, point=0.01, symbol_info=None, skip_weekend_filter=False,
        spread_points=2, deposit=0.0, risk_pct=80, fixed_volume=0.0,
    )
    _check(f"bt_default_{shape}", res, request)


STRAT_CASES = [("ema_cross", EmaCrossStrategy), ("cci_rsi", CciRsiStrategy)]


@pytest.mark.parametrize("name,cls", STRAT_CASES)
@pytest.mark.parametrize("shape", CASES_DEFAULT)
def test_strategy_engine_characterization(name, cls, shape, request):
    df = getattr(builders, shape)(300)
    res = _run_strategy_on_df(
        cls(), df, point=0.01, symbol_info=None, skip_weekend_filter=False,
        spread_points=2, deposit=0.0, risk_pct=80, fixed_volume=0.0,
        sl_atr_mult=1.5, tp_atr_mult=2.5, breakeven_atr_mult=0.0, trail_atr_mult=0.0,
    )
    _check(f"bt_{name}_{shape}", res, request)
