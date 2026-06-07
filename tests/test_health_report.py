"""build_report: per-agent liveness + overall (чистая)."""
from datetime import datetime, timedelta
from core.agent_registry import AgentInfo
from core.health import build_report


def _info(name, *, status="idle", hb_age=None, interval=None, errors=0):
    i = AgentInfo(name, name)
    i.status = status
    i.expected_interval = interval
    i.error_count = errors
    i.last_heartbeat = None if hb_age is None else datetime(2026, 1, 1) - timedelta(seconds=hb_age)
    return i


NOW = datetime(2026, 1, 1)


def test_fresh_not_stale():
    rep = build_report([_info("A", hb_age=5, interval=10)], NOW)
    a = rep["agents"][0]
    assert a["stale"] is False and rep["overall"] == "ok"
    assert a["silent_sec"] == 5


def test_old_heartbeat_is_stale():
    # hb_age 40 > 3*10 → stale
    rep = build_report([_info("A", hb_age=40, interval=10)], NOW)
    assert rep["agents"][0]["stale"] is True and rep["overall"] == "degraded"


def test_no_interval_never_stale():
    rep = build_report([_info("Telegram", hb_age=99999, interval=None)], NOW)
    assert rep["agents"][0]["stale"] is False and rep["overall"] == "ok"


def test_no_heartbeat_not_stale():
    rep = build_report([_info("A", hb_age=None, interval=10)], NOW)
    a = rep["agents"][0]
    assert a["stale"] is False and a["silent_sec"] is None


def test_error_status_degraded():
    rep = build_report([_info("A", status="error", hb_age=1, interval=10)], NOW)
    assert rep["overall"] == "degraded"


def test_boundary_exactly_k_not_stale():
    # hb_age == 3*10 == 30 → не > порога → не stale (строгое >)
    rep = build_report([_info("A", hb_age=30, interval=10)], NOW)
    assert rep["agents"][0]["stale"] is False
