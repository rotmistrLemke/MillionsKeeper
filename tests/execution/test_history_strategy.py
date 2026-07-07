"""HistoryAgent: определение стратегии/потока закрытой сделки.

Приоритет — magic → поток из реестра; фолбэк — разбор comment входного
ордера («s6:default»). Покрывает пометку стратегии в истории сделок.
"""
from types import SimpleNamespace

from agents.history_agent import HistoryAgent


def test_strategy_from_comment_parses_stream_prefix():
    assert HistoryAgent._strategy_from_comment("s6:default") == "default"
    assert HistoryAgent._strategy_from_comment("s12:macd_hist:H") == "macd_hist"


def test_strategy_from_comment_rejects_non_stream():
    assert HistoryAgent._strategy_from_comment("SL") is None
    assert HistoryAgent._strategy_from_comment("") is None
    assert HistoryAgent._strategy_from_comment("manual entry") is None


def test_deal_strategy_prefers_registry_by_magic(monkeypatch):
    import streams as streams_mod
    stream = SimpleNamespace(strategy="macd_hist", name="Поток 1")
    monkeypatch.setattr(streams_mod.registry, "by_magic",
                        lambda m: stream if m == 100000 else None)
    # comment входного ордера намеренно расходится с реестром — приоритет у magic.
    in_d = SimpleNamespace(magic=100000, comment="s1:default")
    out_d = SimpleNamespace(magic=100000, comment="SL")
    assert HistoryAgent._deal_strategy(in_d, out_d) == ("macd_hist", "Поток 1")


def test_deal_strategy_falls_back_to_comment_when_stream_gone(monkeypatch):
    import streams as streams_mod
    monkeypatch.setattr(streams_mod.registry, "by_magic", lambda m: None)
    in_d = SimpleNamespace(magic=0, comment="s3:cci_rsi")
    out_d = SimpleNamespace(magic=0, comment="TP")
    assert HistoryAgent._deal_strategy(in_d, out_d) == ("cci_rsi", None)


def test_deal_strategy_unknown_returns_none(monkeypatch):
    import streams as streams_mod
    monkeypatch.setattr(streams_mod.registry, "by_magic", lambda m: None)
    in_d = SimpleNamespace(magic=0, comment="разовый ручной вход")
    assert HistoryAgent._deal_strategy(in_d, None) == (None, None)
