"""
Персистентное состояние активной стратегии.
Сохраняется между перезапусками программы.
"""
import json
import logging
from pathlib import Path

logger = logging.getLogger("ActiveState")

_STATE_FILE = Path(__file__).parent / "active_state.json"


def load() -> None:
    """Применяет сохранённое состояние к GlobalValues и Dictionary.symbolTradingStatus."""
    if not _STATE_FILE.exists():
        return
    try:
        data = json.loads(_STATE_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as e:
        logger.warning(f"Не удалось прочитать {_STATE_FILE.name}: {e}")
        return

    from settings import GlobalValues, Dictionary, TF_MAP

    strategy = data.get("strategy")
    symbol   = data.get("symbol")
    tf_str   = data.get("timeframe")
    volume   = data.get("volume")

    if isinstance(strategy, str):
        GlobalValues.active_strategy = strategy
    if isinstance(symbol, str) and symbol in Dictionary.symbolTradingStatus:
        GlobalValues.active_symbol = symbol
    if isinstance(tf_str, str) and tf_str in TF_MAP:
        GlobalValues.time_frame = TF_MAP[tf_str]
    if isinstance(volume, (int, float)) and volume >= 0:
        GlobalValues.active_volume = float(volume)

    # Активируем только сохранённую пару, остальные — выключены.
    active_symbol = GlobalValues.active_symbol
    for s in Dictionary.symbolTradingStatus.keys():
        Dictionary.symbolTradingStatus[s] = 0 if s == active_symbol else 3

    logger.info(
        f"Загружено состояние: strategy={GlobalValues.active_strategy}, "
        f"symbol={GlobalValues.active_symbol}, timeframe={tf_str}, volume={GlobalValues.active_volume}"
    )


def save() -> None:
    """Сохраняет текущее состояние из GlobalValues в файл."""
    from settings import GlobalValues, TF_REVERSE
    data = {
        "strategy":  GlobalValues.active_strategy,
        "symbol":    GlobalValues.active_symbol,
        "timeframe": TF_REVERSE.get(GlobalValues.time_frame, "H1"),
        "volume":    GlobalValues.active_volume,
    }
    try:
        _STATE_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")
    except OSError as e:
        logger.warning(f"Не удалось сохранить {_STATE_FILE.name}: {e}")
