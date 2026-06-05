"""Характеризация IndicatorAgent (E5). Прод не трогаем."""
import pytest
from core.events import Event, EventType
from tests.execution.fakes import (
    make_stream, make_bars_df, make_indicator_strategy,
    fake_moving_average, fake_macd, fake_rsi_ind, fake_atr_ind,
    fake_adx_ind, fake_alligator,
)


async def _feed(h, payload, correlation_id=None):
    ev = Event(type=EventType.NEW_BAR, source="t",
               payload=payload, correlation_id=correlation_id)
    h.agent._queue.put_nowait(ev)
    await h.agent.run()


def _ready(h):
    for e in h.bus.events:
        if e.type == EventType.INDICATORS_READY:
            return e
    return None


def _statuses(h):
    return [e.payload["status"] for e in h.bus.events
            if e.type == EventType.AGENT_STATUS]


def _stub_calcs(h, recorder):
    """Подменяет оба calc-метода; пишет, какой позван, и возвращает маркер-dict."""
    def strat(symbol, name, tf):
        recorder.append(("strategy", symbol, name, tf))
        return {"symbol": symbol, "via": "strategy"}
    def default(symbol, tf):
        recorder.append(("default", symbol, tf))
        return {"symbol": symbol, "via": "default"}
    h.agent._calc_strategy = strat
    h.agent._calc_indicators = default


async def test_no_stream_early_return(indicator_agent_factory):
    h = indicator_agent_factory(streams={})  # by_symbol → None
    rec = []
    _stub_calcs(h, rec)
    await _feed(h, {"symbol": "XAUUSD", "timeframe": 16385})
    assert _ready(h) is None
    assert rec == []  # ни один calc не позван


async def test_disabled_stream_return(indicator_agent_factory):
    h = indicator_agent_factory(streams={
        "s1": make_stream(symbol="XAUUSD", enabled=False, timeframe=16385),
    })
    rec = []
    _stub_calcs(h, rec)
    await _feed(h, {"symbol": "XAUUSD", "timeframe": 16385})
    assert _ready(h) is None
    assert rec == []


async def test_timeframe_mismatch_return(indicator_agent_factory):
    h = indicator_agent_factory(streams={
        "s1": make_stream(symbol="XAUUSD", timeframe=16385),
    })
    rec = []
    _stub_calcs(h, rec)
    await _feed(h, {"symbol": "XAUUSD", "timeframe": 16408})  # ≠ 16385
    assert _ready(h) is None
    assert rec == []


async def test_bar_tf_zero_skips_tf_check(indicator_agent_factory):
    h = indicator_agent_factory(streams={
        "s1": make_stream(symbol="XAUUSD", strategy="default", timeframe=16385),
    })
    rec = []
    _stub_calcs(h, rec)
    await _feed(h, {"symbol": "XAUUSD", "timeframe": 0})  # falsy → tf-проверка пропущена
    assert _ready(h) is not None
    assert rec and rec[0][0] == "default"


async def test_strategy_path_when_in_STRATEGIES(indicator_agent_factory):
    h = indicator_agent_factory(
        streams={"s1": make_stream(symbol="XAUUSD", strategy="mystrat", timeframe=16385)},
        strategies={"mystrat": object()},
    )
    rec = []
    _stub_calcs(h, rec)
    await _feed(h, {"symbol": "XAUUSD", "timeframe": 16385})
    assert _ready(h).payload["via"] == "strategy"
    assert rec[0][0] == "strategy"


async def test_default_path_when_not_in_STRATEGIES(indicator_agent_factory):
    h = indicator_agent_factory(
        streams={"s1": make_stream(symbol="XAUUSD", strategy="default", timeframe=16385)},
        strategies={"mystrat": object()},  # "default" ∉ STRATEGIES
    )
    rec = []
    _stub_calcs(h, rec)
    await _feed(h, {"symbol": "XAUUSD", "timeframe": 16385})
    assert _ready(h).payload["via"] == "default"
    assert rec[0][0] == "default"


async def test_stream_id_injected(indicator_agent_factory):
    h = indicator_agent_factory(
        streams={"sX": make_stream(id="sX", symbol="XAUUSD", strategy="default", timeframe=16385)},
    )
    _stub_calcs(h, [])
    await _feed(h, {"symbol": "XAUUSD", "timeframe": 16385})
    assert _ready(h).payload["stream_id"] == "sX"


async def test_correlation_id_passthrough(indicator_agent_factory):
    h = indicator_agent_factory(
        streams={"s1": make_stream(symbol="XAUUSD", strategy="default", timeframe=16385)},
    )
    _stub_calcs(h, [])
    await _feed(h, {"symbol": "XAUUSD", "timeframe": 16385}, correlation_id="cid-9")
    assert _ready(h).correlation_id == "cid-9"


async def test_calculated_metric_increments(indicator_agent_factory):
    h = indicator_agent_factory(
        streams={"s1": make_stream(symbol="XAUUSD", strategy="default", timeframe=16385)},
    )
    _stub_calcs(h, [])
    await _feed(h, {"symbol": "XAUUSD", "timeframe": 16385})
    assert h.agent.metrics["calculated"] == 1


async def test_status_sequence_on_success(indicator_agent_factory):
    h = indicator_agent_factory(
        streams={"s1": make_stream(symbol="XAUUSD", strategy="default", timeframe=16385)},
    )
    _stub_calcs(h, [])
    await _feed(h, {"symbol": "XAUUSD", "timeframe": 16385})
    # IDLE(старт) → RUNNING → IDLE(готово)
    assert _statuses(h) == ["idle", "running", "idle"]


async def test_calc_exception_sets_error_no_ready(indicator_agent_factory):
    h = indicator_agent_factory(
        streams={"s1": make_stream(symbol="XAUUSD", strategy="default", timeframe=16385)},
    )
    def boom(symbol, tf):
        raise RuntimeError("calc boom")
    h.agent._calc_indicators = boom
    await _feed(h, {"symbol": "XAUUSD", "timeframe": 16385})
    assert _ready(h) is None
    assert _statuses(h)[-1] == "error"
    assert h.agent.metrics["calculated"] == 0


async def test_calc_strategy_df_none_minimal(indicator_agent_factory):
    h = indicator_agent_factory(
        rates_df=None,
        runtime_strategy=make_indicator_strategy(),
    )
    res = h.agent._calc_strategy("XAUUSD", "mystrat", 16385)
    assert res == {"symbol": "XAUUSD", "strategy": "mystrat",
                   "entry_signal": "NO_SIGNAL", "is_flat": True}


async def test_calc_strategy_df_too_short_minimal(indicator_agent_factory):
    h = indicator_agent_factory(
        rates_df=make_bars_df(time=1000, n=10),  # < 50
        runtime_strategy=make_indicator_strategy(),
    )
    res = h.agent._calc_strategy("XAUUSD", "mystrat", 16385)
    assert res["entry_signal"] == "NO_SIGNAL"
    assert res["is_flat"] is True
    assert "indicators_raw" not in res


async def test_calc_strategy_flat_no_signal(indicator_agent_factory):
    h = indicator_agent_factory(
        rates_df=make_bars_df(time=1000, n=60),
        runtime_strategy=make_indicator_strategy(flat=True, entry_signal="BUY"),
    )
    res = h.agent._calc_strategy("XAUUSD", "mystrat", 16385)
    # flat=True → signal не запрашивается → NO_SIGNAL
    assert res["entry_signal"] == "NO_SIGNAL"
    assert res["is_flat"] is True


async def test_calc_strategy_not_flat_buy(indicator_agent_factory):
    h = indicator_agent_factory(
        rates_df=make_bars_df(time=1000, n=60),
        runtime_strategy=make_indicator_strategy(flat=False, entry_signal="BUY"),
    )
    res = h.agent._calc_strategy("XAUUSD", "mystrat", 16385)
    assert res["entry_signal"] == "BUY"
    assert res["is_flat"] is False


async def test_calc_strategy_not_flat_none_signal(indicator_agent_factory):
    h = indicator_agent_factory(
        rates_df=make_bars_df(time=1000, n=60),
        runtime_strategy=make_indicator_strategy(flat=False, entry_signal=None),
    )
    res = h.agent._calc_strategy("XAUUSD", "mystrat", 16385)
    assert res["entry_signal"] == "NO_SIGNAL"  # signal or "NO_SIGNAL"


async def test_calc_strategy_indicators_raw_collected(indicator_agent_factory):
    h = indicator_agent_factory(
        rates_df=make_bars_df(time=1000, n=60,
                              extra_cols={"rsi": 55.0, "ema8": 1900.0}),
        runtime_strategy=make_indicator_strategy(
            flat=False, entry_signal="BUY",
            indicator_cols=("rsi", "ema8", "missing_col")),
    )
    res = h.agent._calc_strategy("XAUUSD", "mystrat", 16385)
    assert res["indicators_raw"] == {"rsi": 55.0, "ema8": 1900.0}  # missing_col пропущен


async def test_calc_strategy_indicators_raw_skips_nan(indicator_agent_factory):
    import math
    h = indicator_agent_factory(
        rates_df=make_bars_df(time=1000, n=60, extra_cols={"rsi": math.nan}),
        runtime_strategy=make_indicator_strategy(
            flat=False, entry_signal="BUY", indicator_cols=("rsi",)),
    )
    res = h.agent._calc_strategy("XAUUSD", "mystrat", 16385)
    assert res["indicators_raw"] == {}  # NaN пропущен
    assert res["rsi_value"] is None     # _get_float тоже None


async def test_calc_strategy_legacy_fields_and_getfloat(indicator_agent_factory):
    h = indicator_agent_factory(
        rates_df=make_bars_df(time=1000, n=60,
                              extra_cols={"rsi": 60.0, "ema8": 1900.0, "ema21": 1899.0}),
        runtime_strategy=make_indicator_strategy(flat=False, entry_signal="BUY"),
    )
    res = h.agent._calc_strategy("XAUUSD", "mystrat", 16385)
    assert res["signal_ma"] == "NO_SIGNAL"
    assert res["signal_critical_angle"] == "NO_SIGNAL"
    assert res["macd_signal"] == "NO_SIGNAL"
    assert res["rsi_signal"] == "NO_SIGNAL"
    assert res["rsi_value"] == 60.0
    assert res["ema8"] == 1900.0
    assert res["ema21"] == 1899.0


async def test_calc_strategy_atr_and_adx_fallbacks(indicator_agent_factory):
    h = indicator_agent_factory(
        # нет 'atr' и нет 'flat_adx'; есть 'flat_atr'
        rates_df=make_bars_df(time=1000, n=60, extra_cols={"flat_atr": 3.0}),
        runtime_strategy=make_indicator_strategy(flat=False, entry_signal="BUY"),
    )
    res = h.agent._calc_strategy("XAUUSD", "mystrat", 16385)
    assert res["atr_value"] == 3.0   # _get_float('atr') None → flat_atr
    assert res["adx_value"] == 0.0   # _get_float('flat_adx') None → 0.0


def _patch_indicators(monkeypatch, *, ma=None, macd=None, rsi=None,
                      atr=None, adx=None, alligator=None):
    """Подменяет классы indicators.* фейками (дефолты — нейтральные)."""
    import indicators
    monkeypatch.setattr(indicators, "MovingAverage", ma or fake_moving_average())
    monkeypatch.setattr(indicators, "MACD", macd or fake_macd())
    monkeypatch.setattr(indicators, "RSI", rsi or fake_rsi_ind())
    monkeypatch.setattr(indicators, "ATR", atr or fake_atr_ind(scalar=None))
    monkeypatch.setattr(indicators, "ADX", adx or fake_adx_ind(values=[20.0]))
    monkeypatch.setattr(indicators, "Alligator", alligator or fake_alligator())


async def test_calc_indicators_dict_signals_extracted(indicator_agent_factory, monkeypatch):
    h = indicator_agent_factory()
    _patch_indicators(
        monkeypatch,
        ma=fake_moving_average(cross={"signal": "BUY"}, critical={"signal": "BUY"}),
        macd=fake_macd(signal={"signal": "SELL"}),
    )
    res = h.agent._calc_indicators("XAUUSD", 16385)
    assert res["signal_ma"] == "BUY"
    assert res["signal_critical_angle"] == "BUY"
    assert res["macd_signal"] == "SELL"


async def test_calc_indicators_non_dict_signal_is_no_signal(indicator_agent_factory, monkeypatch):
    h = indicator_agent_factory()
    # cross возвращает не-dict → isinstance-guard → "NO_SIGNAL"
    _patch_indicators(monkeypatch, ma=fake_moving_average(cross="BUY", critical=None))
    res = h.agent._calc_indicators("XAUUSD", 16385)
    assert res["signal_ma"] == "NO_SIGNAL"


async def test_calc_indicators_rsi_none(indicator_agent_factory, monkeypatch):
    h = indicator_agent_factory()
    _patch_indicators(monkeypatch, rsi=fake_rsi_ind(rsi_series=None))
    res = h.agent._calc_indicators("XAUUSD", 16385)
    assert res["rsi_signal"] == "NO_SIGNAL"
    assert res["rsi_value"] is None


async def test_calc_indicators_rsi_too_short(indicator_agent_factory, monkeypatch):
    h = indicator_agent_factory()
    _patch_indicators(monkeypatch, rsi=fake_rsi_ind(rsi_series=[50.0, 51.0]))  # len 2 < 3
    res = h.agent._calc_indicators("XAUUSD", 16385)
    assert res["rsi_signal"] == "NO_SIGNAL"
    assert res["rsi_value"] is None


async def test_calc_indicators_rsi_full(indicator_agent_factory, monkeypatch):
    h = indicator_agent_factory()
    _patch_indicators(
        monkeypatch,
        rsi=fake_rsi_ind(rsi_series=[40.0, 45.0, 60.0], signal={"signal": "BUY"}),
    )
    res = h.agent._calc_indicators("XAUUSD", 16385)
    assert res["rsi_value"] == 60.0
    assert res["rsi_signal"] == "BUY"


async def test_calc_indicators_atr_series_vs_scalar(indicator_agent_factory, monkeypatch):
    h = indicator_agent_factory()
    _patch_indicators(monkeypatch, atr=fake_atr_ind(series=[1.0, 2.5]))
    res = h.agent._calc_indicators("XAUUSD", 16385)
    assert res["atr_value"] == 2.5  # float(.iloc[-1])

    h2 = indicator_agent_factory()
    _patch_indicators(monkeypatch, atr=fake_atr_ind(scalar=7.0))  # без .iloc
    res2 = h2.agent._calc_indicators("XAUUSD", 16385)
    assert res2["atr_value"] == 7.0  # как есть


async def test_calc_indicators_ema_from_ma(indicator_agent_factory, monkeypatch):
    h = indicator_agent_factory()
    _patch_indicators(monkeypatch, ma=fake_moving_average(ma_value=1234.0))
    res = h.agent._calc_indicators("XAUUSD", 16385)
    assert res["ema8"] == 1234.0
    assert res["ema21"] == 1234.0


async def test_calc_indicators_adx_value_and_empty(indicator_agent_factory, monkeypatch):
    h = indicator_agent_factory()
    _patch_indicators(monkeypatch, adx=fake_adx_ind(values=[33.0]))
    res = h.agent._calc_indicators("XAUUSD", 16385)
    assert res["adx_value"] == 33.0

    h2 = indicator_agent_factory()
    _patch_indicators(monkeypatch, adx=fake_adx_ind(values=[]))  # пусто → 0.0
    res2 = h2.agent._calc_indicators("XAUUSD", 16385)
    assert res2["adx_value"] == 0.0


async def test_calc_indicators_result_has_symbol_and_keys(indicator_agent_factory, monkeypatch):
    h = indicator_agent_factory()
    _patch_indicators(monkeypatch)
    res = h.agent._calc_indicators("XAUUSD", 16385)
    assert res["symbol"] == "XAUUSD"
    for k in ("signal_ma", "signal_critical_angle", "macd_signal", "rsi_signal",
              "rsi_value", "atr_value", "adx_value", "ema8", "ema21"):
        assert k in res
