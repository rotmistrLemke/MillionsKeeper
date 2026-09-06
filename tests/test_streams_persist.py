"""Персистинг потоков: конфиг не должен теряться молча.

Боевой streams.json был потерян 14.07.2026 — файл остался как {"streams": []},
а 14 потоков продолжали торговать по magic из истории MT5. Причина воспроизводима:
load() при битом/пустом файле молча стартовал с пустым реестром, а следующий
save() затирал файл нетомарным write_text.

Здесь заперты три гарантии:
  1. load() падает обратно на эталон config/streams.reference.json;
  2. save() не затирает непустой конфиг пустым реестром;
  3. save() пишет атомарно и оставляет бэкап предыдущей версии.
"""
import json

import pytest


TF_H1 = 16385


@pytest.fixture
def isolated(tmp_path, monkeypatch):
    """Реестр с файлами в tmp_path: рабочий, эталон и каталог бэкапов."""
    import streams
    monkeypatch.setattr(streams, "_STREAMS_FILE", tmp_path / "streams.json")
    monkeypatch.setattr(streams, "_REFERENCE_FILE", tmp_path / "streams.reference.json")
    monkeypatch.setattr(streams, "_BACKUP_DIR", tmp_path / "streams.backup")
    monkeypatch.setattr(streams, "_sync_trading_status", lambda: None)
    streams.registry._streams.clear()
    streams.registry._open_streams.clear()
    streams.registry._next_seq = 1
    return streams


def _write(path, ids):
    path.write_text(json.dumps({"streams": [
        {"id": i, "name": i, "strategy": "aroon", "symbol": "XAUUSDrfd",
         "timeframe": "H1", "volume": 0.05, "sl_points": 3000.0,
         "tp_points": 9000.0, "magic": 100000 + n, "enabled": True}
        for n, i in enumerate(ids, start=1)
    ]}, ensure_ascii=False), encoding="utf-8")


# ── load(): fallback на эталон ────────────────────────────────────────

def test_load_falls_back_to_reference_when_working_file_missing(isolated, tmp_path):
    _write(tmp_path / "streams.reference.json", ["s2", "s3"])
    isolated.load()
    assert {s.id for s in isolated.registry.all()} == {"s2", "s3"}


def test_load_falls_back_to_reference_when_working_file_is_empty_list(isolated, tmp_path):
    (tmp_path / "streams.json").write_text('{"streams": []}', encoding="utf-8")
    _write(tmp_path / "streams.reference.json", ["s2", "s3"])
    isolated.load()
    assert {s.id for s in isolated.registry.all()} == {"s2", "s3"}


def test_load_falls_back_to_reference_when_working_file_is_corrupt(isolated, tmp_path):
    (tmp_path / "streams.json").write_text('{"streams": [{"id": "s2"', encoding="utf-8")
    _write(tmp_path / "streams.reference.json", ["s2", "s3"])
    isolated.load()
    assert {s.id for s in isolated.registry.all()} == {"s2", "s3"}


def test_load_prefers_working_file_over_reference(isolated, tmp_path):
    _write(tmp_path / "streams.json", ["s5"])
    _write(tmp_path / "streams.reference.json", ["s2", "s3"])
    isolated.load()
    assert {s.id for s in isolated.registry.all()} == {"s5"}


def test_load_without_file_and_without_reference_yields_empty_registry(isolated):
    # Поведение B2 сохраняется, когда эталона тоже нет.
    isolated.load()
    assert isolated.registry.all() == []


# ── save(): защита от затирания ───────────────────────────────────────

def test_save_refuses_to_overwrite_non_empty_config_with_empty_registry(isolated, tmp_path):
    _write(tmp_path / "streams.json", ["s2", "s3"])
    isolated.registry._streams.clear()
    isolated.save()
    kept = json.loads((tmp_path / "streams.json").read_text(encoding="utf-8"))
    assert [s["id"] for s in kept["streams"]] == ["s2", "s3"]


def test_save_writes_empty_registry_when_config_is_already_empty(isolated, tmp_path):
    # Удаление последнего потока — легитимная операция, её блокировать нельзя.
    (tmp_path / "streams.json").write_text('{"streams": []}', encoding="utf-8")
    isolated.registry._streams.clear()
    isolated.save()
    assert json.loads((tmp_path / "streams.json").read_text(encoding="utf-8"))["streams"] == []


def test_save_persists_streams(isolated, tmp_path):
    isolated.registry.create(name="A", strategy="aroon", symbol="XAUUSDrfd",
                             timeframe=TF_H1, volume=0.05, sl_points=3000)
    saved = json.loads((tmp_path / "streams.json").read_text(encoding="utf-8"))
    assert [s["strategy"] for s in saved["streams"]] == ["aroon"]
    assert saved["streams"][0]["timeframe"] == "H1"


# ── save(): бэкапы ────────────────────────────────────────────────────

def test_save_backs_up_previous_version(isolated, tmp_path):
    _write(tmp_path / "streams.json", ["s2"])
    isolated.registry.create(name="B", strategy="macd_hist", symbol="XAUUSDrfd",
                             timeframe=TF_H1, volume=0.05, sl_points=3000)
    backups = sorted((tmp_path / "streams.backup").glob("*.json"))
    assert len(backups) == 1
    prev = json.loads(backups[0].read_text(encoding="utf-8"))
    assert [s["id"] for s in prev["streams"]] == ["s2"]


def test_backup_rotation_keeps_at_most_ten(isolated, tmp_path):
    _write(tmp_path / "streams.json", ["s2"])
    for n in range(14):
        isolated.registry.create(name=f"S{n}", strategy="aroon", symbol="XAUUSDrfd",
                                 timeframe=TF_H1, volume=0.05, sl_points=3000)
    assert len(list((tmp_path / "streams.backup").glob("*.json"))) <= 10


def test_save_is_atomic_no_tmp_left_behind(isolated, tmp_path):
    isolated.registry.create(name="A", strategy="aroon", symbol="XAUUSDrfd",
                             timeframe=TF_H1, volume=0.05, sl_points=3000)
    assert list(tmp_path.glob("*.tmp")) == []


# ── эталон в репозитории ──────────────────────────────────────────────

def test_reference_config_is_loadable_and_consistent():
    """Эталон боевых потоков должен грузиться реестром без потерь."""
    import streams
    data = json.loads(streams._REFERENCE_FILE.read_text(encoding="utf-8"))
    items = data["streams"]
    assert len(items) == 14
    assert len({s["magic"] for s in items}) == len(items), "magic должны быть уникальны"
    assert len({s["id"] for s in items}) == len(items), "id должны быть уникальны"
    for s in items:
        assert streams.MAGIC_BASE <= s["magic"] < streams.MAGIC_BASE + streams.MAX_STREAMS

    registry = streams.StreamRegistry()
    registry._load_raw_locked(items)
    loaded = registry.all()
    assert len(loaded) == 14
    # _load_raw_locked переназначает конфликтующие magic — здесь их быть не должно.
    assert {s.magic for s in loaded} == {s["magic"] for s in items}

    from strategies import STRATEGIES
    assert {s.strategy for s in loaded} <= set(STRATEGIES), "неизвестная стратегия в эталоне"


# ── зафиксированные решения по потокам ────────────────────────────────

def test_active_portfolio_is_the_seven_stream_contour():
    """Второй контур: шестёрка + ema50_overstretch, отдельный VPS.

    Ветка существует ради одного вопроса: работает ли состав из семи потоков
    живьём. На основном контуре его проверить нельзя — депозит 1964 $ его не
    вмещает, и урезание до трёх было вынужденным, а не выводом о качестве.

    Шесть с плюсом в каждом из пяти кварталов (ema_cross, cci_rsi, aroon,
    triple_ema, market_phase, combined_a_plus) плюс контртрендовая
    ema50_overstretch: сама убыточна (−198 за год), но единственная
    отрицательно коррелированная (−0.25 с cci_rsi) и срезает просадку
    портфеля с 6579 до 5814.
    """
    import streams
    data = json.loads(streams._REFERENCE_FILE.read_text(encoding="utf-8"))
    active = {s["strategy"] for s in data["streams"] if s["enabled"]}
    assert active == {
        "ema_cross", "cci_rsi", "aroon", "triple_ema",
        "market_phase", "combined_a_plus", "ema50_overstretch",
    }


def test_active_streams_use_minimum_lot():
    """0.01 против 0.05 у прежнего состава: контур тестовый, а размер счёта
    под него ещё не зафиксирован. Минимальный лот — единственное значение,
    безопасное при любом депозите от 5000 $."""
    import streams
    data = json.loads(streams._REFERENCE_FILE.read_text(encoding="utf-8"))
    assert {s["volume"] for s in data["streams"] if s["enabled"]} == {0.01}


def test_seven_streams_run_without_a_position_limit():
    """Лимит одной позиции здесь выключен намеренно: одновременная работа семи
    потоков и есть предмет эксперимента. С лимитом 1 контур повторял бы
    основной и отвечал бы на уже отвеченный вопрос."""
    import portfolio
    assert portfolio.load_limits().max_open_positions == 0


def test_drawdown_stop_stays_on_for_the_test_contour():
    """Тестовый — не значит бесконтрольный: портфельный стоп обязателен,
    иначе контур молча сольёт счёт вместо того, чтобы дать ответ."""
    import portfolio
    limits = portfolio.load_limits()
    assert 0 < limits.max_drawdown < 1
    assert limits.deposit >= 5000.0
