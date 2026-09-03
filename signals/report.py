"""Сводка журнала отказов.

    python -m signals.report [дней]      (по умолчанию 7)

Показывает, сколько сигналов и по какой причине не дошли до рынка —
разложение разрыва между модельными и живыми входами.
"""
from __future__ import annotations

import sys
import time

from signals import journal


def render(days: int = 7, db_path=None) -> str:
    since = int(time.time()) - int(days) * 86400
    data = journal.summary(since=since, db_path=db_path)
    if not data:
        return f"Журнал отказов за последние {days} дн. пуст."

    by_strategy: dict[str, dict[str, int]] = {}
    for (strategy, reason), n in data.items():
        by_strategy.setdefault(strategy or "—", {})[reason] = n

    total = sum(data.values())
    reasons = sorted({r for d in by_strategy.values() for r in d})
    width = max(len(s) for s in by_strategy) + 2

    lines = [f"Отказы сигналов за последние {days} дн.", ""]
    header = "стратегия".ljust(width) + "".join(r.rjust(17) for r in reasons) + "итого".rjust(8)
    lines.append(header)
    for strategy in sorted(by_strategy, key=lambda s: -sum(by_strategy[s].values())):
        row = by_strategy[strategy]
        lines.append(
            strategy.ljust(width)
            + "".join(str(row.get(r, 0)).rjust(17) for r in reasons)
            + str(sum(row.values())).rjust(8)
        )
    lines += ["", f"Всего отказов: {total}"]
    return "\n".join(lines)


def main(argv=None) -> None:
    argv = sys.argv[1:] if argv is None else argv
    days = int(argv[0]) if argv else 7
    print(render(days))


if __name__ == "__main__":
    main()
