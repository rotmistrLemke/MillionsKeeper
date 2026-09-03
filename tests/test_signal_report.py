"""Сводка журнала отказов: python -m signals.report [дней]."""
import time

import pytest

from signals import journal as J
from signals import report as R


@pytest.fixture
def db(tmp_path, monkeypatch):
    path = tmp_path / "signals.db"
    monkeypatch.setattr(J, "_DEFAULT_DB", path)
    return path


def test_render_groups_by_strategy_and_reason(db):
    now = int(time.time())
    for _ in range(3):
        J.record(symbol="XAUUSDrfd", stream_id="s4", strategy="cci_rsi",
                 signal="BUY", reason=J.Reason.FLAT, ts=now, db_path=db)
    J.record(symbol="XAUUSDrfd", stream_id="s4", strategy="cci_rsi",
             signal="BUY", reason=J.Reason.NIGHT_BLOCK, ts=now, db_path=db)

    text = R.render(days=1, db_path=db)
    assert "cci_rsi" in text
    assert "FLAT" in text and "3" in text
    assert "NIGHT_BLOCK" in text
    assert "Всего отказов: 4" in text


def test_render_on_empty_journal_says_so(db):
    text = R.render(days=7, db_path=db)
    assert "пуст" in text.lower()


def test_render_ignores_rows_outside_window(db):
    old = int(time.time()) - 30 * 86400
    J.record(symbol="XAUUSDrfd", strategy="cci_rsi", reason=J.Reason.FLAT,
             ts=old, db_path=db)
    assert "пуст" in R.render(days=7, db_path=db).lower()
