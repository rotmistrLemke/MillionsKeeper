"""Статус торговли по символу (слайс B1).

Инкапсулирует бывший settings.Dictionary.symbolTradingStatus за доменным API.
Один экземпляр-синглтон `status`, по образцу streams.registry.

Статусы:
  ALLOWED  (0) — разрешено торговать
  OPEN     (1) — позиция открыта, не входить повторно
  DISABLED (3) — выключено
"""
import threading

ALLOWED = 0
OPEN = 1
DISABLED = 3

# Seed-вселенная символов — перенесена дословно из settings.Dictionary.symbolTradingStatus.
_SEED: dict[str, int] = {
    "EURUSDrfd": 3, "NZDUSDrfd": 3, "EURGBPrfd": 3, "USDCHFrfd": 3,
    "USDJPYrfd": 3, "EURCHFrfd": 3, "GBPUSDrfd": 3, "USDCADrfd": 3,
    "EURJPYrfd": 3, "AUDCADrfd": 3, "AUDUSDrfd": 3, "AUDJPYrfd": 3,
    "AUDCHFrfd": 3, "CHFJPYrfd": 3, "EURAUDrfd": 3, "GBPCHFrfd": 3,
    "EURCADrfd": 3, "GBPCADrfd": 3, "XAUUSDrfd": 0, "GBPJPYrfd": 3,
    "XAGUSDrfd": 3, "USDSGDrfd": 3, "#LCO": 0,
}


class TradingStatusRegistry:
    def __init__(self, seed: dict | None = None):
        self._status: dict[str, int] = dict(_SEED if seed is None else seed)
        self._lock = threading.RLock()

    # ── Запросы ──────────────────────────────────────────────────────
    def has(self, symbol: str) -> bool:
        with self._lock:
            return symbol in self._status

    def __contains__(self, symbol: str) -> bool:
        return self.has(symbol)

    def status_of(self, symbol: str) -> int:
        with self._lock:
            return self._status.get(symbol, DISABLED)

    def is_allowed(self, symbol: str) -> bool:
        return self.status_of(symbol) == ALLOWED

    def is_open(self, symbol: str) -> bool:
        return self.status_of(symbol) == OPEN

    def is_disabled(self, symbol: str) -> bool:
        return self.status_of(symbol) == DISABLED

    def symbols(self) -> list:
        with self._lock:
            return list(self._status.keys())

    def active_symbols(self) -> list:
        with self._lock:
            return [s for s, v in self._status.items() if v != DISABLED]

    def snapshot(self) -> dict:
        with self._lock:
            return dict(self._status)

    # ── Мутации ──────────────────────────────────────────────────────
    def mark_open(self, symbol: str) -> None:
        with self._lock:
            self._status[symbol] = OPEN

    def mark_allowed(self, symbol: str) -> None:
        with self._lock:
            self._status[symbol] = ALLOWED

    def set_status(self, symbol: str, value: int) -> None:
        with self._lock:
            self._status[symbol] = value

    def activate_only(self, symbol: str) -> None:
        """Целевой символ → ALLOWED, прочие → DISABLED. Символы со статусом OPEN не трогаем."""
        with self._lock:
            for s, st in list(self._status.items()):
                if st == OPEN:
                    continue
                self._status[s] = ALLOWED if s == symbol else DISABLED

    def sync_enabled(self, enabled_symbols: set) -> None:
        """Символы из набора → ALLOWED, прочие → DISABLED. OPEN не трогаем."""
        with self._lock:
            for s, st in list(self._status.items()):
                if st == OPEN:
                    continue
                self._status[s] = ALLOWED if s in enabled_symbols else DISABLED


status = TradingStatusRegistry()
