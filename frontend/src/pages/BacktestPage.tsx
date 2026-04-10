import {
  Box,
  Button,
  Card,
  CardContent,
  CircularProgress,
  FormControl,
  Grid,
  InputLabel,
  MenuItem,
  Select,
  Slider,
  TextField,
  Typography,
  Alert,
} from '@mui/material'
import PlayArrowIcon from '@mui/icons-material/PlayArrow'
import { useState } from 'react'
import { useMutation, useQuery } from '@tanstack/react-query'
import { startBacktest, fetchBacktestResults, fetchStrategies } from '../api/endpoints'
import { useTradingStore } from '../store/tradingStore'
import EquityCurveChart from '../components/EquityCurveChart'
import MetricsCard from '../components/MetricsCard'
import type { BacktestRequest } from '../types'

const TIMEFRAMES = ['M1', 'M5', 'M15', 'H1', 'H4', 'D1']
const SYMBOLS = ['XAUUSDrfd', 'EURUSD', 'GBPUSD', 'USDJPY', 'XAUUSD', 'BTCUSD']

export default function BacktestPage() {
  const [form, setForm] = useState<BacktestRequest>({
    strategy: 'alligator',
    symbol: 'XAUUSDrfd',
    bars: 2000,
    deposit: 10000,
    spread: 0,
    risk: 1.0,
    timeframe: 'H1',
  })
  const [error, setError] = useState<string | null>(null)

  const lastResult = useTradingStore((s) => s.lastBacktestResult)

  const { data: strategies = [] } = useQuery({
    queryKey: ['strategies'],
    queryFn: fetchStrategies,
  })

  const { data: history = [] } = useQuery({
    queryKey: ['backtestHistory'],
    queryFn: () => fetchBacktestResults(10),
  })

  const runMutation = useMutation({
    mutationFn: startBacktest,
    onError: (e: Error) => setError(e.message),
    onMutate: () => setError(null),
  })

  const handleRun = () => runMutation.mutate(form)

  return (
    <Box sx={{ p: { xs: 1.5, md: 2 } }}>
      <Grid container spacing={2}>
        {/* Form */}
        <Grid size={{ xs: 12, md: 4 }}>
          <Card>
            <CardContent>
              <Typography variant="h6" sx={{ mb: 2 }}>
                Run Backtest
              </Typography>

              <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
                <FormControl fullWidth size="small">
                  <InputLabel>Strategy</InputLabel>
                  <Select
                    value={form.strategy}
                    label="Strategy"
                    onChange={(e) => setForm((f) => ({ ...f, strategy: e.target.value }))}
                  >
                    {strategies.length > 0
                      ? strategies.map((s) => (
                          <MenuItem key={s.name} value={s.name}>
                            {s.display_name || s.name}
                          </MenuItem>
                        ))
                      : ['alligator', 'bollinger_scalp', 'rsi_scalp'].map((s) => (
                          <MenuItem key={s} value={s}>
                            {s}
                          </MenuItem>
                        ))}
                  </Select>
                </FormControl>

                <FormControl fullWidth size="small">
                  <InputLabel>Symbol</InputLabel>
                  <Select
                    value={form.symbol}
                    label="Symbol"
                    onChange={(e) => setForm((f) => ({ ...f, symbol: e.target.value }))}
                  >
                    {SYMBOLS.map((s) => (
                      <MenuItem key={s} value={s}>
                        {s}
                      </MenuItem>
                    ))}
                  </Select>
                </FormControl>

                <FormControl fullWidth size="small">
                  <InputLabel>Timeframe</InputLabel>
                  <Select
                    value={form.timeframe}
                    label="Timeframe"
                    onChange={(e) => setForm((f) => ({ ...f, timeframe: e.target.value }))}
                  >
                    {TIMEFRAMES.map((tf) => (
                      <MenuItem key={tf} value={tf}>
                        {tf}
                      </MenuItem>
                    ))}
                  </Select>
                </FormControl>

                <Box>
                  <Typography variant="caption" color="text.secondary">
                    Bars: {form.bars?.toLocaleString()}
                  </Typography>
                  <Slider
                    value={form.bars}
                    onChange={(_, v) => setForm((f) => ({ ...f, bars: v as number }))}
                    min={500}
                    max={10000}
                    step={500}
                    marks={[
                      { value: 1000, label: '1K' },
                      { value: 5000, label: '5K' },
                      { value: 10000, label: '10K' },
                    ]}
                    size="small"
                  />
                </Box>

                <TextField
                  size="small"
                  label="Deposit"
                  type="number"
                  value={form.deposit}
                  onChange={(e) => setForm((f) => ({ ...f, deposit: Number(e.target.value) }))}
                  inputProps={{ min: 100, step: 100 }}
                />

                <Box>
                  <Typography variant="caption" color="text.secondary">
                    Risk per trade: {form.risk}%
                  </Typography>
                  <Slider
                    value={form.risk}
                    onChange={(_, v) => setForm((f) => ({ ...f, risk: v as number }))}
                    min={0.1}
                    max={5}
                    step={0.1}
                    size="small"
                  />
                </Box>

                <TextField
                  size="small"
                  label="Spread (points)"
                  type="number"
                  value={form.spread}
                  onChange={(e) => setForm((f) => ({ ...f, spread: Number(e.target.value) }))}
                  inputProps={{ min: 0, step: 1 }}
                />

                {error && <Alert severity="error" sx={{ fontSize: '0.8rem' }}>{error}</Alert>}

                <Button
                  variant="contained"
                  startIcon={runMutation.isPending ? <CircularProgress size={16} color="inherit" /> : <PlayArrowIcon />}
                  onClick={handleRun}
                  disabled={runMutation.isPending}
                  fullWidth
                >
                  {runMutation.isPending ? 'Running...' : 'Run Backtest'}
                </Button>
              </Box>
            </CardContent>
          </Card>
        </Grid>

        {/* Results */}
        <Grid size={{ xs: 12, md: 8 }}>
          {lastResult ? (
            <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
              <MetricsCard
                metrics={lastResult.metrics}
                strategy={lastResult.strategy}
                symbol={lastResult.symbol}
                timeframe={lastResult.timeframe}
              />
              <Card>
                <CardContent>
                  <Typography variant="h6" sx={{ mb: 1.5 }}>
                    Equity Curve
                  </Typography>
                  <EquityCurveChart equityCurve={lastResult.equity_curve} deposit={lastResult.deposit} />
                </CardContent>
              </Card>
            </Box>
          ) : (
            <Card sx={{ height: 300, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
              <Typography variant="body2" color="text.secondary">
                {runMutation.isPending ? 'Running backtest...' : 'Run a backtest to see results'}
              </Typography>
            </Card>
          )}

          {/* History */}
          {history.length > 0 && (
            <Card sx={{ mt: 2 }}>
              <CardContent>
                <Typography variant="h6" sx={{ mb: 1 }}>
                  Recent Runs
                </Typography>
                {history.map((r) => (
                  <Box
                    key={r.id}
                    sx={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: 2,
                      py: 1,
                      borderBottom: '1px solid',
                      borderColor: 'divider',
                      '&:last-child': { borderBottom: 'none' },
                    }}
                  >
                    <Typography variant="body2" fontWeight={600} sx={{ minWidth: 120 }}>
                      {r.strategy}
                    </Typography>
                    <Typography variant="caption" color="text.secondary" sx={{ flexGrow: 1 }}>
                      {r.symbol} · {r.timeframe} · {r.bars}bars
                    </Typography>
                    <Typography
                      variant="subtitle2"
                      color={r.metrics.total_profit >= 0 ? 'success.main' : 'error.main'}
                    >
                      {r.metrics.total_profit >= 0 ? '+' : ''}
                      {r.metrics.total_profit.toFixed(2)}
                    </Typography>
                    <Typography variant="caption" color="text.secondary">
                      WR {(r.metrics.win_rate * 100).toFixed(0)}%
                    </Typography>
                  </Box>
                ))}
              </CardContent>
            </Card>
          )}
        </Grid>
      </Grid>
    </Box>
  )
}
