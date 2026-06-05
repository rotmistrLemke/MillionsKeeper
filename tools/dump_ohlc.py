"""Разовый забор исторических баров из MT5 в CSV для golden-тестов.

Запуск (локально, при запущенном MT5-терминале):
    python tools/dump_ohlc.py --symbol XAUUSDrfd --timeframe H1 --count 500 \
        --out tests/fixtures/xauusd_h1.csv
"""
import argparse
import os
import sys

import MetaTrader5 as mt5
import pandas as pd

TF = {
    "M1": mt5.TIMEFRAME_M1, "M5": mt5.TIMEFRAME_M5, "M15": mt5.TIMEFRAME_M15,
    "M30": mt5.TIMEFRAME_M30, "H1": mt5.TIMEFRAME_H1, "H4": mt5.TIMEFRAME_H4,
    "D1": mt5.TIMEFRAME_D1,
}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--symbol", default="XAUUSDrfd")
    p.add_argument("--timeframe", default="H1", choices=list(TF))
    p.add_argument("--count", type=int, default=500)
    p.add_argument("--out", default="tests/fixtures/xauusd_h1.csv")
    args = p.parse_args()

    if not mt5.initialize():
        print(f"mt5.initialize() failed: {mt5.last_error()}", file=sys.stderr)
        sys.exit(1)
    try:
        rates = mt5.copy_rates_from_pos(args.symbol, TF[args.timeframe], 0, args.count)
    finally:
        mt5.shutdown()

    if rates is None or len(rates) == 0:
        print("Нет данных от MT5", file=sys.stderr)
        sys.exit(1)

    df = pd.DataFrame(rates)
    df["time"] = pd.to_datetime(df["time"], unit="s")
    cols = ["time", "open", "high", "low", "close", "tick_volume"]
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    df[cols].to_csv(args.out, index=False)
    print(f"Записано {len(df)} баров в {args.out}")


if __name__ == "__main__":
    main()
