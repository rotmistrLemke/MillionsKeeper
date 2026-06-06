"""MT5Auth.reconnect: повторный initialize+login, не кидает, возвращает bool."""
import types
from types import SimpleNamespace


def _fake_mt5(*, init_ok=True, login_ok=True):
    m = types.ModuleType("MetaTrader5")
    m.initialize = lambda **kw: init_ok
    m.login = lambda **kw: login_ok
    m.last_error = lambda: "fake error"
    m.shutdown = lambda: None
    return m


def _make_auth(monkeypatch, fake):
    import authenticator
    monkeypatch.setattr(authenticator, "mt5", fake)
    # __init__ зовёт initialize_connection() → нужен init_ok=True у fake при создании
    return authenticator.MT5Auth({"login": 1, "password": "x", "server": "S"})


def test_reconnect_success(monkeypatch):
    fake = _fake_mt5(init_ok=True, login_ok=True)
    auth = _make_auth(monkeypatch, fake)
    assert auth.reconnect() is True


def test_reconnect_login_fails(monkeypatch):
    fake = _fake_mt5(init_ok=True, login_ok=False)
    auth = _make_auth(monkeypatch, fake)
    assert auth.reconnect() is False


def test_reconnect_initialize_fails_no_raise(monkeypatch):
    auth = _make_auth(monkeypatch, _fake_mt5(init_ok=True, login_ok=True))
    # теперь initialize начинает падать → initialize_connection кинет ConnectionError,
    # reconnect должен поймать и вернуть False (не пробросить)
    import authenticator
    bad = _fake_mt5(init_ok=False, login_ok=True)
    monkeypatch.setattr(authenticator, "mt5", bad)
    assert auth.reconnect() is False
