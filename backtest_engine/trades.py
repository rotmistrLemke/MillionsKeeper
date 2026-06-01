def _calc_pnl_points(position, exit_price, point, spread_points):
    if position['type'] == 'BUY':
        pnl = (exit_price - position['entry_price']) / point
    else:
        pnl = (position['entry_price'] - exit_price) / point
    return pnl - spread_points


def _make_default_trade(position, row, i, pnl_points, pnl_money, balance, reason):
    return {
        'type':         position['type'],
        'entry_time':   position['entry_time'],
        'entry_price':  position['entry_price'],
        'exit_time':    row['time'],
        'exit_price':   row['close'],
        'pnl_points':   pnl_points,
        'pnl_money':    pnl_money,
        'volume':       position['volume'],
        'bars_held':    i - position['entry_bar'],
        'exit_reason':  reason,
        'balance_after': balance,
        'indicators':   position.get('indicators', {}),
    }


def _make_strategy_trade(position, row, i, pnl_points, pnl_money, balance, reason, exit_price=None):
    return {
        'type':          position['type'],
        'entry_time':    position['entry_time'],
        'entry_price':   position['entry_price'],
        'exit_time':     row['time'],
        'exit_price':    exit_price or row['close'],
        'pnl_points':    pnl_points,
        'pnl_money':     pnl_money,
        'volume':        position['volume'],
        'bars_held':     i - position['entry_bar'],
        'exit_reason':   reason,
        'balance_after': balance,
        'sl':            position['sl'],
        'tp':            position['tp'],
        'indicators':    position.get('indicators', {}),
    }
