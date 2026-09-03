"""Журнал отклонённых сигналов.

До рынка доходит от четверти до половины входов (cci_rsi 2 из 18 модельных,
triple_ema 20 из 34, ema_pullback 4 из 11). Причина каждого отказа была видна
только в статусе агента — строкой, которая нигде не оседала. Журнал копит
отказы, чтобы разрыв live↔бэктест можно было разложить по причинам.
"""
import sqlite3

import pytest

from signals import journal as J


@pytest.fixture
def db(tmp_path, monkeypatch):
    path = tmp_path / "signals.db"
    monkeypatch.setattr(J, "_DEFAULT_DB", path)
    return path


def _rec(db, **kw):
    kw.setdefault("symbol", "XAUUSDrfd")
    kw.setdefault("stream_id", "s4")
    kw.setdefault("strategy", "cci_rsi")
    kw.setdefault("signal", "BUY")
    kw.setdefault("reason", J.Reason.STREAM_BUSY)
    J.record(db_path=db, **kw)


# ── запись и чтение ───────────────────────────────────────────────────

def test_record_persists_row(db):
    _rec(db, reason=J.Reason.NIGHT_BLOCK, detail="23:50–05:00")
    rows = J.recent(db_path=db)
    assert len(rows) == 1
    r = rows[0]
    assert (r["symbol"], r["stream_id"], r["strategy"], r["signal"]) == \
           ("XAUUSDrfd", "s4", "cci_rsi", "BUY")
    assert r["reason"] == "NIGHT_BLOCK"
    assert r["detail"] == "23:50–05:00"
    assert r["ts"] > 0


def test_recent_is_newest_first_and_limited(db):
    for n in range(5):
        _rec(db, detail=f"n{n}", ts=1_800_000_000 + n)
    rows = J.recent(db_path=db, limit=2)
    assert [r["detail"] for r in rows] == ["n4", "n3"]


def test_summary_counts_by_strategy_and_reason(db):
    _rec(db, strategy="cci_rsi", reason=J.Reason.FLAT)
    _rec(db, strategy="cci_rsi", reason=J.Reason.FLAT)
    _rec(db, strategy="cci_rsi", reason=J.Reason.STREAM_BUSY)
    _rec(db, strategy="triple_ema", reason=J.Reason.FLAT)

    assert J.summary(db_path=db) == {
        ("cci_rsi", "FLAT"): 2,
        ("cci_rsi", "STREAM_BUSY"): 1,
        ("triple_ema", "FLAT"): 1,
    }


def test_summary_respects_since(db):
    _rec(db, reason=J.Reason.FLAT, ts=1_000)
    _rec(db, reason=J.Reason.STREAM_BUSY, ts=9_000)
    assert J.summary(db_path=db, since=5_000) == {("cci_rsi", "STREAM_BUSY"): 1}


def test_purge_drops_old_rows_only(db):
    _rec(db, reason=J.Reason.FLAT, ts=1_000)
    _rec(db, reason=J.Reason.FLAT, ts=9_000)
    removed = J.purge_before(5_000, db_path=db)
    assert removed == 1
    assert len(J.recent(db_path=db)) == 1


# ── устойчивость: журнал не должен ронять торговлю ────────────────────

def test_record_never_raises_on_broken_db(tmp_path):
    broken = tmp_path / "not_a.db"
    broken.write_bytes(b"this is not sqlite")
    J.record(symbol="XAUUSDrfd", stream_id="s4", strategy="cci_rsi",
             signal="BUY", reason=J.Reason.FLAT, db_path=broken)   # не бросает


def test_recent_on_missing_db_returns_empty(tmp_path):
    assert J.recent(db_path=tmp_path / "nope.db") == []


def test_reasons_are_stable_strings():
    """Названия причин уходят в БД — менять их нельзя без миграции."""
    assert {
        J.Reason.FLAT, J.Reason.SYMBOL_DISABLED, J.Reason.NO_STREAM,
        J.Reason.STREAM_DISABLED, J.Reason.STREAM_BUSY, J.Reason.NIGHT_BLOCK,
        J.Reason.DRAWDOWN_BLOCK, J.Reason.ORDER_FAILED, J.Reason.ORDER_ERROR,
        J.Reason.HEDGE_FAILED,
    } == {
        "FLAT", "SYMBOL_DISABLED", "NO_STREAM", "STREAM_DISABLED", "STREAM_BUSY",
        "NIGHT_BLOCK", "DRAWDOWN_BLOCK", "ORDER_FAILED", "ORDER_ERROR", "HEDGE_FAILED",
    }


def test_schema_has_index_on_ts(db):
    _rec(db)
    with sqlite3.connect(db) as conn:
        idx = [r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='rejected_signals'")]
    assert any("ts" in (n or "") for n in idx), "нужен индекс по времени для summary(since=…)"
