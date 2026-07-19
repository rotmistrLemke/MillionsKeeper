"""Регрессия: одну пару могут обслуживать несколько потоков.

Ограничение «одна пара = один поток» снято в 6f34f7c: OPEN-статус живёт
per-stream, а не на символе. Тест запирает это на уровне реестра, чтобы
ограничение не вернулось незаметно (в UI фильтр «занятых» пар пережил
6f34f7c и снова блокировал создание — фикс в app.js/openStreamForm).
"""
import pytest


@pytest.fixture
def clean_registry(monkeypatch):
    """Изолированный реестр: без записи streams.json и без синка статусов."""
    import streams
    monkeypatch.setattr(streams, "save", lambda: None)
    monkeypatch.setattr(streams, "_sync_trading_status", lambda: None)
    streams.registry._streams.clear()
    streams.registry._open_streams.clear()
    streams.registry._next_seq = 1
    return streams


def _make_two_on_same_symbol(streams, symbol="XAUUSDrfd"):
    a = streams.registry.create(name="A", strategy="aroon", symbol=symbol,
                                timeframe=16385, sl_points=300)
    b = streams.registry.create(name="B", strategy="macd_hist", symbol=symbol,
                                timeframe=16388, sl_points=500)
    return a, b


def test_two_streams_on_same_symbol_can_be_created(clean_registry):
    streams = clean_registry
    a, b = _make_two_on_same_symbol(streams)
    assert a.id != b.id
    assert a.symbol == b.symbol
    assert len(streams.registry.all()) == 2


def test_streams_on_same_symbol_get_distinct_magic(clean_registry):
    streams = clean_registry
    a, b = _make_two_on_same_symbol(streams)
    # magic привязывает позицию MT5 к потоку-владельцу — должен быть уникален.
    assert a.magic != b.magic


def test_by_symbol_returns_all_streams_of_symbol(clean_registry):
    streams = clean_registry
    a, b = _make_two_on_same_symbol(streams)
    assert {s.id for s in streams.registry.by_symbol("XAUUSDrfd")} == {a.id, b.id}


def test_open_status_is_per_stream_not_per_symbol(clean_registry):
    streams = clean_registry
    a, b = _make_two_on_same_symbol(streams)
    streams.registry.mark_stream_open(a.id)
    # Открытие одного потока не должно блокировать второй по тому же символу.
    assert streams.registry.is_stream_open(a.id) is True
    assert streams.registry.is_stream_open(b.id) is False


def test_can_create_up_to_max_streams_with_unique_magic(clean_registry):
    streams = clean_registry
    for i in range(streams.MAX_STREAMS):
        streams.registry.create(name=f"S{i}", strategy="aroon",
                                symbol="XAUUSDrfd", timeframe=16385)
    all_streams = streams.registry.all()
    assert len(all_streams) == streams.MAX_STREAMS
    # magic привязывает позицию MT5 к потоку — пул должен покрывать весь лимит.
    magics = [s.magic for s in all_streams]
    assert len(set(magics)) == streams.MAX_STREAMS
    assert min(magics) == streams.MAGIC_BASE
    assert max(magics) == streams.MAGIC_BASE + streams.MAX_STREAMS - 1


def test_creating_beyond_max_streams_raises(clean_registry):
    streams = clean_registry
    for i in range(streams.MAX_STREAMS):
        streams.registry.create(name=f"S{i}", strategy="aroon",
                                symbol="XAUUSDrfd", timeframe=16385)
    with pytest.raises(ValueError, match="лимит"):
        streams.registry.create(name="overflow", strategy="aroon",
                                symbol="XAUUSDrfd", timeframe=16385)


def test_existing_magic_preserved_on_load(clean_registry):
    """Расширение лимита не должно переназначать magic уже существующим потокам
    (иначе порвётся привязка открытых позиций MT5 к потоку-владельцу)."""
    streams = clean_registry
    saved = [
        {"id": "s1", "name": "A", "strategy": "aroon", "symbol": "XAUUSDrfd",
         "timeframe": "H1", "magic": streams.MAGIC_BASE},
        {"id": "s2", "name": "B", "strategy": "macd_hist", "symbol": "EURUSDrfd",
         "timeframe": "H4", "magic": streams.MAGIC_BASE + 9},
    ]
    with streams.registry._lock:
        streams.registry._load_raw_locked(saved)
    by_id = {s.id: s.magic for s in streams.registry.all()}
    assert by_id == {"s1": streams.MAGIC_BASE, "s2": streams.MAGIC_BASE + 9}
