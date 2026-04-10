import { Card, CardContent, Grid, Typography, Box, Divider } from '@mui/material'
import type { BacktestMetrics } from '../types'

interface Props {
  metrics: BacktestMetrics
  strategy: string
  symbol: string
  timeframe?: string
}

function Metric({
  label,
  value,
  color,
  mono = false,
}: {
  label: string
  value: string
  color?: string
  mono?: boolean
}) {
  return (
    <Box>
      <Typography variant="overline" color="text.secondary" display="block">
        {label}
      </Typography>
      <Typography
        variant={mono ? 'subtitle2' : 'body1'}
        color={color ?? 'text.primary'}
        fontWeight={600}
        sx={{ fontSize: '0.95rem' }}
      >
        {value}
      </Typography>
    </Box>
  )
}

export default function MetricsCard({ metrics: m, strategy, symbol, timeframe }: Props) {
  const pct = (v: number) => `${(v * 100).toFixed(1)}%`
  const money = (v: number) => (v >= 0 ? '+' : '') + v.toFixed(2)
  const f = (v: number, d = 2) => v.toFixed(d)

  return (
    <Card>
      <CardContent>
        <Box sx={{ display: 'flex', alignItems: 'baseline', gap: 1, mb: 1 }}>
          <Typography variant="h6">{strategy}</Typography>
          <Typography variant="caption" color="text.secondary">
            {symbol} · {timeframe ?? 'H1'} · {m.total_trades} trades
          </Typography>
        </Box>
        <Divider sx={{ mb: 2 }} />

        <Grid container spacing={2}>
          <Grid size={{ xs: 6, sm: 4, md: 2 }}>
            <Metric
              label="Net Profit"
              value={`${money(m.total_profit)}`}
              color={m.total_profit >= 0 ? 'success.main' : 'error.main'}
            />
          </Grid>
          <Grid size={{ xs: 6, sm: 4, md: 2 }}>
            <Metric
              label="Return"
              value={`${money(m.return_pct)}%`}
              color={m.return_pct >= 0 ? 'success.main' : 'error.main'}
            />
          </Grid>
          <Grid size={{ xs: 6, sm: 4, md: 2 }}>
            <Metric label="Win Rate" value={pct(m.win_rate)} color={m.win_rate >= 0.5 ? 'success.main' : 'warning.main'} />
          </Grid>
          <Grid size={{ xs: 6, sm: 4, md: 2 }}>
            <Metric
              label="Profit Factor"
              value={m.profit_factor === Infinity ? '∞' : f(m.profit_factor)}
              color={m.profit_factor >= 1.5 ? 'success.main' : m.profit_factor >= 1 ? 'warning.main' : 'error.main'}
            />
          </Grid>
          <Grid size={{ xs: 6, sm: 4, md: 2 }}>
            <Metric
              label="Sharpe"
              value={f(m.sharpe_ratio, 3)}
              color={m.sharpe_ratio >= 1 ? 'success.main' : 'text.secondary'}
            />
          </Grid>
          <Grid size={{ xs: 6, sm: 4, md: 2 }}>
            <Metric label="Max DD" value={`${f(m.max_drawdown)}%`} color="error.light" />
          </Grid>
          <Grid size={{ xs: 6, sm: 4, md: 2 }}>
            <Metric label="Avg Trade" value={money(m.avg_profit_per_trade)} mono />
          </Grid>
          <Grid size={{ xs: 6, sm: 4, md: 2 }}>
            <Metric label="Final Balance" value={f(m.final_balance)} mono />
          </Grid>
          <Grid size={{ xs: 6, sm: 4, md: 2 }}>
            <Metric label="Max DD $" value={f(m.max_drawdown_money)} color="error.light" mono />
          </Grid>
          <Grid size={{ xs: 6, sm: 4, md: 2 }}>
            <Metric label="Consec. Losses" value={String(m.max_consecutive_losses)} />
          </Grid>
        </Grid>
      </CardContent>
    </Card>
  )
}
