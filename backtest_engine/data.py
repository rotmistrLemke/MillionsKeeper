import MetaTrader5 as mt5


# ─── Загрузка данных ──────────────────────────────────────────────────────

def load_rates(symbol, timeframe, bars=2000, date_from=None, date_to=None):
    if date_from is not None:
        if date_to is not None:
            rates = mt5.copy_rates_range(symbol, timeframe, date_from, date_to)
        else:
            rates = mt5.copy_rates_from(symbol, timeframe, date_from, bars)
    else:
        rates = mt5.copy_rates_from_pos(symbol, timeframe, 0, bars)
    return rates
