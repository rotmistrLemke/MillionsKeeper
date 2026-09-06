"""Портфельные ограничения: лимит одновременных позиций и стоп по просадке.

Per-stream DD-блокировка (ExecutionAgent, 35%) считает каждый поток отдельно и
поэтому не видит суммарного риска: на депозите 2000 $ три потока по 0.01 лота
дают историческую просадку 47% при том, что ни один поток порога не касается.
Эти тесты запирают портфельный слой — он считает счёт целиком.
"""
import json

import pytest

import portfolio


# ── Конфиг ───────────────────────────────────────────────────────────

def test_missing_file_gives_everything_off(tmp_path):
    limits = portfolio.load_limits(tmp_path / "nope.json")
    assert limits.max_open_positions == 0
    assert limits.max_drawdown == 0.0
    assert limits.deposit == 0.0


def test_reads_values_from_file(tmp_path):
    p = tmp_path / "portfolio.json"
    p.write_text(json.dumps({
        "max_open_positions": 1, "deposit": 2000.0, "max_drawdown": 0.2,
    }), encoding="utf-8")
    limits = portfolio.load_limits(p)
    assert limits.max_open_positions == 1
    assert limits.deposit == 2000.0
    assert limits.max_drawdown == 0.2


def test_unknown_keys_are_ignored(tmp_path):
    p = tmp_path / "portfolio.json"
    p.write_text(json.dumps({"max_open_positions": 2, "_comment": "текст"}),
                 encoding="utf-8")
    assert portfolio.load_limits(p).max_open_positions == 2


def test_broken_json_falls_back_to_off_instead_of_raising(tmp_path):
    p = tmp_path / "portfolio.json"
    p.write_text("{не json", encoding="utf-8")
    # Испорченный конфиг риска не должен ронять торговый процесс на старте.
    limits = portfolio.load_limits(p)
    assert limits.max_open_positions == 0


def test_garbage_values_are_treated_as_off(tmp_path):
    p = tmp_path / "portfolio.json"
    p.write_text(json.dumps({
        "max_open_positions": "две", "deposit": None, "max_drawdown": -1,
    }), encoding="utf-8")
    limits = portfolio.load_limits(p)
    assert limits.max_open_positions == 0
    assert limits.deposit == 0.0
    assert limits.max_drawdown == 0.0


def test_drawdown_above_one_is_rejected(tmp_path):
    p = tmp_path / "portfolio.json"
    p.write_text(json.dumps({"max_drawdown": 20}), encoding="utf-8")
    # 20 — это явно проценты, а не доля; молча трактовать как 2000% нельзя.
    assert portfolio.load_limits(p).max_drawdown == 0.0


# ── Лимит одновременных позиций ──────────────────────────────────────

def _guard(tmp_path, **kw):
    limits = portfolio.PortfolioLimits(**kw)
    return portfolio.PortfolioGuard(limits, state_path=tmp_path / "state.json")


def test_position_limit_off_allows_any_count(tmp_path):
    g = _guard(tmp_path, max_open_positions=0)
    assert g.check_positions(7)[0] is True


def test_under_limit_is_allowed(tmp_path):
    g = _guard(tmp_path, max_open_positions=3)
    assert g.check_positions(2)[0] is True


def test_at_limit_is_blocked(tmp_path):
    # Слот занят ровно под завязку: следующий вход уже превысил бы лимит.
    g = _guard(tmp_path, max_open_positions=1)
    allowed, detail = g.check_positions(1)
    assert allowed is False
    assert "1" in detail


def test_above_limit_is_blocked(tmp_path):
    g = _guard(tmp_path, max_open_positions=3)
    assert g.check_positions(5)[0] is False


# ── Стоп по просадке ─────────────────────────────────────────────────

def test_drawdown_off_allows_any_equity(tmp_path):
    g = _guard(tmp_path, max_drawdown=0.0, deposit=2000.0)
    assert g.check_drawdown(100.0)[0] is True


def test_deposit_is_the_starting_peak(tmp_path):
    # Просадка считается от внесённого капитала, а не от того, что осталось:
    # иначе первая же неделя убытков молча становится новой нормой.
    g = _guard(tmp_path, max_drawdown=0.3, deposit=2000.0)
    assert g.check_drawdown(1300.0)[0] is False


def test_peak_rises_with_equity(tmp_path):
    g = _guard(tmp_path, max_drawdown=0.3, deposit=2000.0)
    g.check_drawdown(3000.0)
    assert g.peak == 3000.0
    # 2100 — это +5% к депозиту, но −30% от пика 3000.
    assert g.check_drawdown(2100.0)[0] is False


def test_drawdown_below_threshold_is_allowed(tmp_path):
    g = _guard(tmp_path, max_drawdown=0.3, deposit=2000.0)
    assert g.check_drawdown(1450.0)[0] is True   # −27.5%


def test_block_detail_names_the_numbers(tmp_path):
    g = _guard(tmp_path, max_drawdown=0.3, deposit=2000.0)
    _, detail = g.check_drawdown(1400.0)
    assert "30" in detail            # порог
    assert "2000" in detail          # пик


def test_block_does_not_lift_when_equity_recovers(tmp_path):
    # Автоснятие вернуло бы систему в рынок ровно на отскоке — а решение
    # после просадки в треть депозита принимает человек, а не таймер.
    g = _guard(tmp_path, max_drawdown=0.3, deposit=2000.0)
    g.check_drawdown(1400.0)
    assert g.check_drawdown(1990.0)[0] is False


def test_non_numeric_equity_does_not_block_trading(tmp_path):
    # Не смогли прочитать equity — это не повод ни блокировать, ни падать.
    g = _guard(tmp_path, max_drawdown=0.3, deposit=2000.0)
    assert g.check_drawdown(None)[0] is True
    assert g.blocked is False


# ── Живучесть блокировки ─────────────────────────────────────────────

def test_block_survives_restart(tmp_path):
    state = tmp_path / "state.json"
    g = portfolio.PortfolioGuard(
        portfolio.PortfolioLimits(max_drawdown=0.3, deposit=2000.0), state_path=state)
    g.check_drawdown(1400.0)

    fresh = portfolio.PortfolioGuard(
        portfolio.PortfolioLimits(max_drawdown=0.3, deposit=2000.0), state_path=state)
    assert fresh.blocked is True
    assert fresh.check_drawdown(1990.0)[0] is False


def test_resume_lifts_the_block_and_persists(tmp_path):
    state = tmp_path / "state.json"
    limits = portfolio.PortfolioLimits(max_drawdown=0.3, deposit=2000.0)
    g = portfolio.PortfolioGuard(limits, state_path=state)
    g.check_drawdown(1400.0)
    g.resume()

    fresh = portfolio.PortfolioGuard(limits, state_path=state)
    assert fresh.blocked is False


def test_resume_rebaselines_peak_to_current_equity(tmp_path):
    # После снятия пик берётся от того, что реально на счёте: иначе стоп
    # сработал бы повторно на первом же сигнале, от старого депозита.
    g = _guard(tmp_path, max_drawdown=0.3, deposit=2000.0)
    g.check_drawdown(1400.0)
    g.resume()
    assert g.check_drawdown(1400.0)[0] is True
    assert g.peak == 1400.0


def test_unreadable_state_file_starts_unblocked(tmp_path):
    state = tmp_path / "state.json"
    state.write_text("{сломано", encoding="utf-8")
    g = portfolio.PortfolioGuard(portfolio.PortfolioLimits(max_drawdown=0.3),
                                 state_path=state)
    assert g.blocked is False


# ── CLI: снятие стопа ────────────────────────────────────────────────

def test_cli_status_reports_the_block(tmp_path, monkeypatch, capsys):
    g = _guard(tmp_path, max_drawdown=0.3, deposit=2000.0)
    g.check_drawdown(1300.0)
    monkeypatch.setattr(portfolio, "guard", g)
    portfolio.main(["status"])
    assert "35" in capsys.readouterr().out


def test_cli_resume_lifts_the_block(tmp_path, monkeypatch, capsys):
    g = _guard(tmp_path, max_drawdown=0.3, deposit=2000.0)
    g.check_drawdown(1300.0)
    monkeypatch.setattr(portfolio, "guard", g)
    portfolio.main(["resume"])
    assert g.blocked is False


def test_cli_without_args_shows_status_not_an_error(tmp_path, monkeypatch, capsys):
    g = _guard(tmp_path, max_open_positions=1)
    monkeypatch.setattr(portfolio, "guard", g)
    portfolio.main([])
    out = capsys.readouterr().out
    assert "лимит" in out.lower()


# ── Изоляция от боевого состояния ────────────────────────────────────

def test_tests_never_write_the_production_state_file():
    """Прогон тестов дёргает ExecutionAgent, тот — боевой portfolio.guard,
    и первое же наблюдение equity писало пик в portfolio_state.json репозитория.
    Ровно так же журнал отказов однажды засорил боевую signals.db."""
    assert portfolio.guard._state_path != portfolio._STATE_FILE


def test_default_guard_in_tests_has_limits_off():
    """Иначе боевой config/portfolio.json начинает влиять на чужие тесты."""
    assert portfolio.guard.limits.max_open_positions == 0
    assert portfolio.guard.limits.max_drawdown == 0.0


# ── Предполётная сверка депозита ─────────────────────────────────────
# Контуров теперь два: три потока под 1964 $ и семь под 5000 $, каждый в
# своей ветке со своим config/. Перепутанная ветка на счёте — ошибка того же
# рода, что перепутанный счёт в терминале: тихая и дорогая. Проверка счёта
# в authenticator ловит не тот счёт, эта — не тот конфиг на правильном счёте.

def test_matching_deposit_passes(tmp_path):
    g = _guard(tmp_path, deposit=2000.0)
    ok, detail = g.check_deposit(1964.02)
    assert ok is True and detail == ""


def test_deposit_far_above_equity_is_refused(tmp_path):
    # Конфиг семи потоков (5000) на счёте основного контура (1964).
    g = _guard(tmp_path, deposit=5000.0)
    ok, detail = g.check_deposit(1964.02)
    assert ok is False
    assert "5000" in detail and "1964" in detail


def test_equity_above_deposit_is_fine(tmp_path):
    # Счёт вырос или пополнен — это не повод отказываться стартовать.
    g = _guard(tmp_path, deposit=2000.0)
    assert g.check_deposit(9000.0)[0] is True


def test_modest_shortfall_is_tolerated(tmp_path):
    # Часть депозита уже потеряна в просадке — это рабочая ситуация,
    # а не признак перепутанного конфига.
    g = _guard(tmp_path, deposit=2000.0)
    assert g.check_deposit(1450.0)[0] is True


def test_check_is_skipped_when_deposit_not_configured(tmp_path):
    g = _guard(tmp_path, deposit=0.0)
    assert g.check_deposit(50.0)[0] is True


def test_unknown_equity_does_not_block_startup(tmp_path):
    g = _guard(tmp_path, deposit=5000.0)
    assert g.check_deposit(None)[0] is True


def test_startup_refuses_a_foreign_contour_config(tmp_path, monkeypatch):
    """Старт с чужим конфигом останавливается, а не логируется и продолжается:
    торговать неверными размерами хуже, чем не торговать вовсе. Чинится
    правкой одной строки в config/portfolio.json."""
    g = _guard(tmp_path, deposit=5000.0)
    monkeypatch.setattr(portfolio, "guard", g)
    with pytest.raises(SystemExit) as e:
        portfolio.assert_deposit_matches(1964.02)
    assert "5000" in str(e.value)


def test_startup_proceeds_on_a_matching_account(tmp_path, monkeypatch):
    g = _guard(tmp_path, deposit=5000.0)
    monkeypatch.setattr(portfolio, "guard", g)
    portfolio.assert_deposit_matches(5200.0)   # не бросает
