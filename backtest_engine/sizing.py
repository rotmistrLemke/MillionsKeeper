import MetaTrader5 as mt5


# ─── Вспомогательные функции ─────────────────────────────────────────────

def get_pip_value(symbol, volume=1.0):
    info = mt5.symbol_info(symbol)
    if info is None: return 0.0
    pip_value = info.point * info.trade_contract_size * volume
    if info.currency_profit != info.currency_margin:
        conv_symbol = info.currency_profit + info.currency_margin + 'rfd'
        conv_info = mt5.symbol_info(conv_symbol)
        if conv_info is not None:
            tick = mt5.symbol_info_tick(conv_symbol)
            if tick: pip_value *= tick.ask
        else:
            conv_symbol2 = info.currency_margin + info.currency_profit + 'rfd'
            conv_info2 = mt5.symbol_info(conv_symbol2)
            if conv_info2 is not None:
                tick = mt5.symbol_info_tick(conv_symbol2)
                if tick: pip_value *= tick.bid
    return pip_value


def calc_volume(balance, risk_pct, stop_loss_pips, pip_value_per_lot, symbol_info,
                entry_price=0.0, order_type=None, num_free_slots=1, margin_safety=1.1):
    if pip_value_per_lot <= 0 or stop_loss_pips <= 0:
        return symbol_info.volume_min if symbol_info else 0.01

    risk_money     = balance * (risk_pct / 100)
    stop_loss_cost = pip_value_per_lot * stop_loss_pips
    volume_by_risk = risk_money / stop_loss_cost
    volume         = volume_by_risk

    if entry_price > 0 and symbol_info and order_type is not None:
        try:
            margin_per_lot = mt5.order_calc_margin(order_type, symbol_info.name, 1.0, entry_price)
            if margin_per_lot and margin_per_lot > 0:
                available_margin = (balance / num_free_slots) / margin_safety
                volume = min(volume_by_risk, available_margin / margin_per_lot)
        except Exception:
            pass

    if symbol_info:
        volume = min(volume, symbol_info.volume_max)
        volume = max(volume, symbol_info.volume_min)
        if symbol_info.volume_step > 0:
            volume = round(volume / symbol_info.volume_step) * symbol_info.volume_step
    return volume
