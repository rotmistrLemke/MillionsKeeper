from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional


class AnomalyType(str, Enum):
    EMA_FAR_UP   = "EMA_FAR_UP"
    EMA_FAR_DOWN = "EMA_FAR_DOWN"
    STOCH_OB     = "STOCH_OB"
    STOCH_OS     = "STOCH_OS"


@dataclass
class Snapshot:
    price: float
    ema50: float
    atr: float
    dist_atr: float        # (price - ema50) / atr (со знаком)
    stoch_k: float
    stoch_d: float
    bar_time: str          # ISO-8601 UTC

    def to_dict(self) -> dict:
        return {
            "price": self.price,
            "ema50": self.ema50,
            "atr": self.atr,
            "dist_atr": self.dist_atr,
            "stoch_k": self.stoch_k,
            "stoch_d": self.stoch_d,
            "bar_time": self.bar_time,
        }


@dataclass
class DetectResult:
    types: List[AnomalyType] = field(default_factory=list)
    snapshot: Optional[Snapshot] = None

    @property
    def is_anomaly(self) -> bool:
        return bool(self.types)
