import numpy as np


# ─── BacktestResult ───────────────────────────────────────────────────────

class BacktestResult:
    def __init__(self, initial_deposit=0.0):
        self.trades        = []
        self.equity_curve  = []
        self.initial_deposit = initial_deposit

    @property
    def total_trades(self): return len(self.trades)

    @property
    def winning_trades(self): return [t for t in self.trades if t['pnl_points'] >= 0]

    @property
    def losing_trades(self): return [t for t in self.trades if t['pnl_points'] < 0]

    @property
    def win_rate(self): return len(self.winning_trades) / self.total_trades if self.total_trades else 0

    @property
    def total_pnl_points(self): return sum(t['pnl_points'] for t in self.trades)

    @property
    def total_pnl_money(self): return sum(t['pnl_money'] for t in self.trades)

    @property
    def avg_win(self):
        wins = [t['pnl_points'] for t in self.winning_trades]
        return np.mean(wins) if wins else 0

    @property
    def avg_loss(self):
        losses = [t['pnl_points'] for t in self.losing_trades]
        return np.mean(losses) if losses else 0

    @property
    def avg_win_money(self):
        wins = [t['pnl_money'] for t in self.winning_trades]
        return np.mean(wins) if wins else 0

    @property
    def avg_loss_money(self):
        losses = [t['pnl_money'] for t in self.losing_trades]
        return np.mean(losses) if losses else 0

    @property
    def profit_factor(self):
        gross_win  = sum(t['pnl_points'] for t in self.winning_trades)
        gross_loss = abs(sum(t['pnl_points'] for t in self.losing_trades))
        if gross_loss > 0:
            return gross_win / gross_loss
        # Нет убытков → бесконечный PF. Возвращаем 0 (если и побед нет) или
        # большое конечное число — иначе json.dumps выдаёт Infinity, которое
        # ломает JSON.parse в браузере и UI зависает.
        return 0.0 if gross_win == 0 else 9999.0

    @property
    def max_drawdown_points(self):
        if not self.equity_curve: return 0
        peak, max_dd = self.equity_curve[0], 0
        for eq in self.equity_curve:
            if eq > peak: peak = eq
            dd = peak - eq
            if dd > max_dd: max_dd = dd
        return max_dd

    @property
    def max_drawdown_money(self):
        if not self.trades: return 0
        cumulative = self.initial_deposit
        peak, max_dd = cumulative, 0
        for t in self.trades:
            cumulative += t['pnl_money']
            if cumulative > peak: peak = cumulative
            dd = peak - cumulative
            if dd > max_dd: max_dd = dd
        return max_dd

    @property
    def max_drawdown_pct(self):
        if not self.trades or self.initial_deposit <= 0: return 0
        cumulative = self.initial_deposit
        peak, max_dd_pct = cumulative, 0
        for t in self.trades:
            cumulative += t['pnl_money']
            if cumulative > peak: peak = cumulative
            if peak > 0:
                dd_pct = (peak - cumulative) / peak * 100
                if dd_pct > max_dd_pct: max_dd_pct = dd_pct
        return max_dd_pct

    @property
    def final_balance(self): return self.initial_deposit + self.total_pnl_money

    @property
    def return_pct(self):
        if self.initial_deposit <= 0: return 0
        return self.total_pnl_money / self.initial_deposit * 100

    @property
    def max_consecutive_losses(self):
        max_streak = current = 0
        for t in self.trades:
            if t['pnl_points'] <= 0:
                current += 1
                max_streak = max(max_streak, current)
            else:
                current = 0
        return max_streak
