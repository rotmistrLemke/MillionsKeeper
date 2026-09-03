"""B2: streams.load() без streams.json даёт пустой реестр (миграция удалена).

С появлением эталона config/streams.reference.json «пустой старт» возможен
только когда эталона тоже нет — иначе реестр поднимается из него
(см. tests/test_streams_persist.py).
"""
import importlib


def test_load_without_file_yields_empty_registry(tmp_path, monkeypatch):
    import streams
    importlib.reload(streams)
    # Перенаправляем файл потоков на несуществующий путь во временном каталоге.
    monkeypatch.setattr(streams, "_STREAMS_FILE", tmp_path / "nope_streams.json")
    monkeypatch.setattr(streams, "_REFERENCE_FILE", tmp_path / "nope_reference.json")
    # Чистый реестр на старте.
    streams.registry._streams.clear()
    streams.load()
    assert streams.registry.all() == []
