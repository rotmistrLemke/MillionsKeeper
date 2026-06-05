"""Прогон стратегии по OHLC → детерминированная сигнальная серия + сравнение с golden."""
import json
from pathlib import Path

import pandas as pd

GOLDEN_DIR = Path(__file__).resolve().parents[1] / "golden"


def run_signal_series(strategy, df: pd.DataFrame) -> dict:
    """Прогоняет стратегию по df и возвращает сериализуемую сигнальную серию.

    Возвращает dict:
      {"entries": [[idx, "BUY"|"SELL"], ...], "flat_count": int}
    Вход учитывает флэт-гард: если is_flat(row) — вход пропускается.
    """
    work = df.copy()
    work = strategy.compute_indicators(work)
    work = strategy.compute_flat_indicators(work)

    entries = []
    flat_count = 0
    for idx in range(len(work)):
        row = work.iloc[idx]
        if strategy.is_flat(row):
            flat_count += 1
            continue
        sig = strategy.get_entry_signal(row)
        if sig in ("BUY", "SELL"):
            entries.append([idx, sig])
    return {"entries": entries, "flat_count": flat_count}


def golden_path(name: str) -> Path:
    return GOLDEN_DIR / f"{name}.json"


def load_golden(name: str) -> dict:
    return json.loads(golden_path(name).read_text(encoding="utf-8"))


def save_golden(name: str, data: dict) -> None:
    GOLDEN_DIR.mkdir(parents=True, exist_ok=True)
    golden_path(name).write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
    )
