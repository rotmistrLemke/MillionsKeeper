"""Подключение обязано попасть ровно в тот счёт, который указан в .env.

06.09.2026 при переезде на счёт 1100137867 выяснилось: MT5_PATH не задан, и
initialize() вызывался БЕЗ кредов — то есть подключался к тому счёту, который
на тот момент открыт в терминале. Запуск упал только потому, что терминал
держал чужой счёт неавторизованным. Будь там любой рабочий счёт — бот молча
торговал бы не тот депозит, считая, что торгует нужный. Для второго контура
на отдельном VPS, где два счёта живут рядом, это авария, а не теория.
"""
from types import SimpleNamespace

import pytest

import authenticator


class FakeMT5:
    def __init__(self, *, connected_login=777, initialize_ok=True, login_ok=True,
                 account_info_none=False):
        self.init_kwargs = None
        self.login_kwargs = None
        self._connected_login = connected_login
        self._initialize_ok = initialize_ok
        self._login_ok = login_ok
        self._account_info_none = account_info_none
        self.shutdown_called = False

    def initialize(self, **kwargs):
        self.init_kwargs = kwargs
        return self._initialize_ok

    def login(self, **kwargs):
        self.login_kwargs = kwargs
        return self._login_ok

    def account_info(self):
        if self._account_info_none:
            return None
        return SimpleNamespace(login=self._connected_login)

    def last_error(self):
        return (1, "fake")

    def shutdown(self):
        self.shutdown_called = True


ACCOUNT = {"login": 777, "password": "secret", "server": "AlfaForexRU-Real"}


@pytest.fixture
def fake(monkeypatch):
    def make(**kw):
        f = FakeMT5(**kw)
        monkeypatch.setattr(authenticator, "mt5", f)
        monkeypatch.delenv("MT5_PATH", raising=False)
        return f
    return make


# ── Креды передаются всегда ──────────────────────────────────────────

def test_initialize_gets_credentials_without_mt5_path(fake):
    f = fake()
    authenticator.MT5Auth(ACCOUNT)
    assert f.init_kwargs["login"] == 777
    assert f.init_kwargs["server"] == "AlfaForexRU-Real"
    assert "path" not in f.init_kwargs


def test_initialize_gets_path_when_configured(fake, monkeypatch):
    f = fake()
    monkeypatch.setenv("MT5_PATH", r"C:\MT5\terminal64.exe")
    authenticator.MT5Auth(ACCOUNT)
    assert f.init_kwargs["path"] == r"C:\MT5\terminal64.exe"
    assert f.init_kwargs["login"] == 777


def test_initialize_without_login_passes_no_credentials(fake):
    # Бэктест-утилиты подключаются к уже открытому терминалу без .env.
    f = fake()
    authenticator.MT5Auth({"login": 0, "password": "", "server": ""})
    assert f.init_kwargs == {}


# ── Сверка подключённого счёта ───────────────────────────────────────

def test_login_succeeds_on_the_expected_account(fake):
    fake(connected_login=777)
    auth = authenticator.MT5Auth(ACCOUNT)
    assert auth.login() is True
    assert auth.authorized is True


def test_login_refuses_a_different_account(fake):
    fake(connected_login=999)
    auth = authenticator.MT5Auth(ACCOUNT)
    with pytest.raises(ConnectionError):
        auth.login()
    assert auth.authorized is False


def test_mismatch_message_names_both_accounts(fake):
    fake(connected_login=999)
    auth = authenticator.MT5Auth(ACCOUNT)
    with pytest.raises(ConnectionError) as e:
        auth.login()
    assert "777" in str(e.value) and "999" in str(e.value)


def test_unverifiable_account_is_refused(fake):
    # account_info() не ответил — проверить счёт нечем, торговать вслепую нельзя.
    fake(account_info_none=True)
    auth = authenticator.MT5Auth(ACCOUNT)
    with pytest.raises(ConnectionError):
        auth.login()


def test_failed_login_does_not_claim_authorization(fake):
    fake(login_ok=False)
    auth = authenticator.MT5Auth(ACCOUNT)
    assert auth.login() is False
    assert auth.authorized is False


def test_reconnect_reports_failure_instead_of_raising(fake):
    # ConnectionAgent крутит reconnect в цикле — исключение уронило бы агента.
    fake(connected_login=999)
    auth = authenticator.MT5Auth.__new__(authenticator.MT5Auth)
    auth.account = ACCOUNT
    auth.authorized = False
    assert auth.reconnect() is False
