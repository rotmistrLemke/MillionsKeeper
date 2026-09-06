"""Портфельные ограничения риска: лимит одновременных позиций и стоп по просадке.

Зачем отдельный слой. ExecutionAgent умеет блокировать поток при просадке 35%
его собственного депозита, но каждый поток считается изолированно. На малом
счёте это ничего не защищает: три потока по 0.01 лота на XAUUSD дают
историческую просадку около 47% депозита 2000 $, притом что ни один поток
своего порога не касается. Портфельный слой смотрит на счёт целиком.

Два независимых ограничения (каждое выключается нулём):

  max_open_positions — сколько потоков одновременно держат позицию.
      Лимит 1 на отборе даёт 72% прибыльных конфигураций вне выборки против
      21–24% при лимитах 2–3: узкое горлышко работает не как «страховка»,
      а как способ отбора лучшего сигнала на единственный слот.

  max_drawdown — доля падения equity от достигнутого пика, после которой
      новые входы прекращаются.

Стоп по просадке НЕ снимается сам. Просадка в 20–30% — событие, после которого
надо посмотреть на систему, а не переждать выходные: автоматический сброс по
понедельникам (как у per-stream DD) позволил бы потерять те же 20% ещё раз на
следующей неделе. Снятие — явное: `python -m portfolio resume`.

Состояние блокировки лежит на диске: урок `_blocked_side`, который жил только
в памяти и обнулялся рестартом, повторять не нужно.
"""
from __future__ import annotations

import json
import logging
import os
import sys
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path

logger = logging.getLogger("Portfolio")

_CONFIG_FILE = Path(__file__).parent / "config" / "portfolio.json"
_STATE_FILE = Path(__file__).parent / "portfolio_state.json"


def _positive_int(value) -> int:
    """Целое > 0 либо 0 («выключено»). Мусор — это выключено, не исключение."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return 0
    n = int(value)
    return n if n > 0 else 0


def _fraction(value) -> float:
    """Доля в (0, 1) либо 0.0. Значение ≥ 1 — почти наверняка проценты,
    и трактовать 20 как 2000% опаснее, чем отказаться от лимита вовсе."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return 0.0
    f = float(value)
    return f if 0.0 < f < 1.0 else 0.0


def _positive_float(value) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return 0.0
    f = float(value)
    return f if f > 0 else 0.0


@dataclass
class PortfolioLimits:
    max_open_positions: int = 0   # 0 = без лимита
    deposit: float = 0.0          # базовый капитал; 0 = взять первое наблюдённое equity
    max_drawdown: float = 0.0     # доля от пика; 0 = выкл

    @classmethod
    def from_dict(cls, d: dict) -> "PortfolioLimits":
        return cls(
            max_open_positions=_positive_int(d.get("max_open_positions")),
            deposit=_positive_float(d.get("deposit")),
            max_drawdown=_fraction(d.get("max_drawdown")),
        )

    def to_dict(self) -> dict:
        return asdict(self)


def load_limits(path=None) -> PortfolioLimits:
    """Читает конфиг. Любая проблема — это «ограничений нет», а не падение:
    процесс исполнения не должен умирать из-за файла настроек риска."""
    path = Path(path) if path is not None else _CONFIG_FILE
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return PortfolioLimits()
    except (OSError, ValueError) as e:
        logger.warning(f"Не удалось прочитать {path.name}: {e} — ограничения выключены")
        return PortfolioLimits()
    if not isinstance(raw, dict):
        logger.warning(f"{path.name}: ожидался объект — ограничения выключены")
        return PortfolioLimits()
    return PortfolioLimits.from_dict(raw)


class PortfolioGuard:
    """Портфельные проверки перед открытием позиции.

    Держит состояние (пик equity, факт блокировки) и умеет его сохранять —
    рестарт не должен снимать стоп по просадке.
    """

    def __init__(self, limits: PortfolioLimits = None, state_path=None):
        self.limits = limits if limits is not None else PortfolioLimits()
        self._state_path = Path(state_path) if state_path is not None else _STATE_FILE
        self.peak: float = 0.0
        self.blocked: bool = False
        self.blocked_at: str = ""
        self.blocked_detail: str = ""
        # После снятия стопа пик берётся от текущего equity, а не от deposit.
        self._reseed: bool = False
        self._load_state()

    # ── Состояние на диске ───────────────────────────────────────────
    def _load_state(self) -> None:
        try:
            raw = json.loads(self._state_path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return
        except (OSError, ValueError) as e:
            logger.warning(f"Не удалось прочитать {self._state_path.name}: {e}")
            return
        if not isinstance(raw, dict):
            return
        self.peak = _positive_float(raw.get("peak"))
        self.blocked = bool(raw.get("blocked"))
        self.blocked_at = str(raw.get("blocked_at") or "")
        self.blocked_detail = str(raw.get("blocked_detail") or "")
        self._reseed = bool(raw.get("reseed"))

    def _save_state(self) -> None:
        payload = {
            "peak": self.peak,
            "blocked": self.blocked,
            "blocked_at": self.blocked_at,
            "blocked_detail": self.blocked_detail,
            "reseed": self._reseed,
        }
        tmp = self._state_path.with_suffix(".json.tmp")
        try:
            self._state_path.parent.mkdir(parents=True, exist_ok=True)
            tmp.write_text(json.dumps(payload, indent=2, ensure_ascii=False),
                           encoding="utf-8")
            os.replace(tmp, self._state_path)
        except OSError as e:
            logger.warning(f"Не удалось сохранить {self._state_path.name}: {e}")
            try:
                tmp.unlink(missing_ok=True)
            except OSError:
                pass

    # ── Лимит одновременных позиций ──────────────────────────────────
    def check_positions(self, open_count: int) -> tuple[bool, str]:
        limit = self.limits.max_open_positions
        if limit <= 0:
            return True, ""
        if open_count >= limit:
            return False, (
                f"портфельный лимит позиций: открыто {open_count} из {limit}"
            )
        return True, ""

    # ── Стоп по просадке ─────────────────────────────────────────────
    def check_drawdown(self, equity) -> tuple[bool, str]:
        if self.limits.max_drawdown <= 0:
            return True, ""
        if self.blocked:
            return False, self.blocked_detail or "портфельный стоп по просадке"

        if isinstance(equity, bool) or not isinstance(equity, (int, float)):
            # Equity не прочитан. Блокировать на этом основании нельзя —
            # обрыв связи с терминалом не является просадкой.
            return True, ""
        equity = float(equity)

        if self.peak <= 0:
            # Первое наблюдение: точкой отсчёта служит внесённый капитал,
            # чтобы убыток с первого дня считался просадкой, а не новой нормой.
            # После resume отсчёт начинается заново от факта на счёте.
            self.peak = equity if self._reseed else max(equity, self.limits.deposit)
            self._reseed = False
            self._save_state()

        if equity > self.peak:
            self.peak = equity
            self._save_state()
            return True, ""

        dd = (self.peak - equity) / self.peak
        if dd >= self.limits.max_drawdown:
            self.blocked = True
            self.blocked_at = datetime.now().strftime("%Y-%m-%d %H:%M")
            self.blocked_detail = (
                f"портфельная просадка {dd*100:.1f}% >= "
                f"{self.limits.max_drawdown*100:.0f}% "
                f"(пик {self.peak:.0f}, equity {equity:.0f}) — "
                f"новые входы остановлены до ручного снятия"
            )
            self._save_state()
            logger.error(self.blocked_detail)
            return False, self.blocked_detail
        return True, ""

    def resume(self) -> None:
        """Снимает стоп и обнуляет точку отсчёта: пик будет взят заново
        от того equity, которое реально на счёте в момент следующей проверки."""
        self.blocked = False
        self.blocked_at = ""
        self.blocked_detail = ""
        self.peak = 0.0
        self._reseed = True
        self._save_state()
        logger.warning("Портфельный стоп по просадке снят вручную")


# Боевой экземпляр. Конфиг читается один раз на старте процесса; reload()
# нужен, когда файл поменяли на живой системе.
guard = PortfolioGuard(load_limits())


def reload() -> None:
    guard.limits = load_limits()


def _status_text() -> str:
    lim = guard.limits
    lines = ["Портфельные ограничения:"]
    lines.append(
        f"  лимит одновременных позиций: "
        f"{lim.max_open_positions if lim.max_open_positions else 'нет'}"
    )
    if lim.max_drawdown > 0:
        lines.append(f"  стоп по просадке: {lim.max_drawdown*100:.0f}% от пика"
                     f" (базовый капитал {lim.deposit:.0f})")
    else:
        lines.append("  стоп по просадке: нет")
    lines.append(f"  достигнутый пик equity: {guard.peak:.0f}")
    if guard.blocked:
        lines.append("")
        lines.append(f"  ТОРГОВЛЯ ОСТАНОВЛЕНА {guard.blocked_at}")
        lines.append(f"  {guard.blocked_detail}")
        lines.append("  снять: python -m portfolio resume")
    else:
        lines.append("  блокировки нет")
    return "\n".join(lines)


def main(argv=None) -> None:
    argv = sys.argv[1:] if argv is None else argv
    cmd = argv[0] if argv else "status"
    if cmd == "resume":
        if not guard.blocked:
            print("Блокировки нет — снимать нечего.")
            return
        was = guard.blocked_detail
        guard.resume()
        print(f"Стоп снят. Было: {was}")
        print("Пик equity будет взят заново от текущего состояния счёта.")
        return
    if cmd != "status":
        print("Использование: python -m portfolio [status|resume]")
        return
    print(_status_text())


if __name__ == "__main__":
    main()
