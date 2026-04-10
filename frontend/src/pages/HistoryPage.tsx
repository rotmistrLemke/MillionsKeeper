import {
  Box,
  Card,
  CardContent,
  Chip,
  FormControl,
  Grid,
  InputLabel,
  MenuItem,
  Select,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  TextField,
  Typography,
} from '@mui/material'
import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import {
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ReferenceLine,
  Cell,
} from 'recharts'
import { fetchHistory } from '../api/endpoints'
import { useTheme } from '@mui/material/styles'
import type { Trade } from '../types'

const SYMBOLS = ['', 'XAUUSDrfd', 'EURUSD', 'GBPUSD', 'USDJPY']

function PnLBarChart({ trades }: { trades: Trade[] }) {
  const theme = useTheme()
  const data = trades.slice(-100).map((t, i) => ({ i, pnl: t.pnl, type: t.type }))

  return (
    <ResponsiveContainer width="100%" height={140}>
      <BarChart data={data} margin={{ top: 4, right: 4, left: -20, bottom: 0 }}>
        <CartesianGrid strokeDasharray="3 3" stroke={theme.palette.divider} />
        <XAxis dataKey="i" hide />
        <YAxis tick={{ fontSize: 10 }} stroke={theme.palette.divider} />
        <Tooltip
          formatter={(v: number) => [(v >= 0 ? '+' : '') + v.toFixed(2), 'P&L']}
          contentStyle={{
            backgroundColor: theme.palette.background.paper,
            border: `1px solid ${theme.palette.divider}`,
            fontSize: 12,
          }}
        />
        <ReferenceLine y={0} stroke={theme.palette.divider} />
        {data.map((entry, i) => (
          <Cell
            key={i}
            fill={entry.pnl >= 0 ? theme.palette.success.main : theme.palette.error.main}
          />
        ))}
        <Bar dataKey="pnl" isAnimationActive={data.length < 200} />
      </BarChart>
    </ResponsiveContainer>
  )
}

function SummaryRow({ trades }: { trades: Trade[] }) {
  const total = trades.reduce((s, t) => s + t.pnl, 0)
  const wins = trades.filter((t) => t.pnl >= 0).length
  const wr = trades.length ? wins / trades.length : 0

  return (
    <Box sx={{ display: 'flex', gap: 3, flexWrap: 'wrap', mb: 2 }}>
      {[
        { label: 'Total Trades', value: trades.length },
        {
          label: 'Net P&L',
          value: (total >= 0 ? '+' : '') + total.toFixed(2),
          color: total >= 0 ? 'success.main' : 'error.main',
        },
        { label: 'Win Rate', value: `${(wr * 100).toFixed(1)}%`, color: wr >= 0.5 ? 'success.main' : 'warning.main' },
        { label: 'Wins', value: wins, color: 'success.main' },
        { label: 'Losses', value: trades.length - wins, color: 'error.main' },
      ].map((s) => (
        <Box key={s.label}>
          <Typography variant="overline" color="text.secondary" display="block">
            {s.label}
          </Typography>
          <Typography variant="h6" color={s.color ?? 'text.primary'} sx={{ fontSize: '1rem' }}>
            {s.value}
          </Typography>
        </Box>
      ))}
    </Box>
  )
}

export default function HistoryPage() {
  const [symbol, setSymbol] = useState('')
  const [limit, setLimit] = useState(200)

  const { data: trades = [], isLoading } = useQuery({
    queryKey: ['history', symbol, limit],
    queryFn: () => fetchHistory({ symbol: symbol || undefined, limit }),
  })

  const fmt = (v: number, d = 5) => v.toFixed(d)
  const fmtDate = (s: string) => new Date(s).toLocaleString('ru-RU', { dateStyle: 'short', timeStyle: 'short' })

  return (
    <Box sx={{ p: { xs: 1.5, md: 2 } }}>
      {/* Filters */}
      <Card sx={{ mb: 2 }}>
        <CardContent>
          <Grid container spacing={2} alignItems="center">
            <Grid size={{ xs: 12, sm: 4, md: 3 }}>
              <FormControl fullWidth size="small">
                <InputLabel>Symbol</InputLabel>
                <Select value={symbol} label="Symbol" onChange={(e) => setSymbol(e.target.value)}>
                  {SYMBOLS.map((s) => (
                    <MenuItem key={s} value={s}>
                      {s || 'All symbols'}
                    </MenuItem>
                  ))}
                </Select>
              </FormControl>
            </Grid>
            <Grid size={{ xs: 12, sm: 4, md: 2 }}>
              <TextField
                size="small"
                label="Limit"
                type="number"
                value={limit}
                onChange={(e) => setLimit(Number(e.target.value))}
                inputProps={{ min: 10, max: 1000, step: 10 }}
                fullWidth
              />
            </Grid>
            <Grid size={{ xs: 12, sm: 4, md: 7 }}>
              <Typography variant="caption" color="text.secondary">
                Showing {trades.length} closed trades
              </Typography>
            </Grid>
          </Grid>
        </CardContent>
      </Card>

      {/* Summary + Chart */}
      {trades.length > 0 && (
        <Card sx={{ mb: 2 }}>
          <CardContent>
            <SummaryRow trades={trades} />
            <Typography variant="overline" color="text.secondary">
              P&L per trade (last 100)
            </Typography>
            <PnLBarChart trades={trades} />
          </CardContent>
        </Card>
      )}

      {/* Table */}
      <Card>
        <CardContent sx={{ pb: '12px !important' }}>
          <Typography variant="h6" sx={{ mb: 1.5 }}>
            Trade Log
          </Typography>
          {isLoading ? (
            <Typography color="text.secondary">Loading...</Typography>
          ) : trades.length === 0 ? (
            <Typography color="text.secondary" sx={{ py: 3, textAlign: 'center' }}>
              No trades found
            </Typography>
          ) : (
            <TableContainer sx={{ maxHeight: 480 }}>
              <Table size="small" stickyHeader>
                <TableHead>
                  <TableRow>
                    <TableCell>#</TableCell>
                    <TableCell>Symbol</TableCell>
                    <TableCell>Type</TableCell>
                    <TableCell align="right">Vol</TableCell>
                    <TableCell align="right">Open</TableCell>
                    <TableCell align="right">Close</TableCell>
                    <TableCell align="right">P&L</TableCell>
                    <TableCell align="right">Pts</TableCell>
                    <TableCell>Close Time</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {trades.map((t) => (
                    <TableRow key={t.id} hover>
                      <TableCell>
                        <Typography variant="caption" color="text.secondary">
                          {t.ticket}
                        </Typography>
                      </TableCell>
                      <TableCell>
                        <Typography variant="body2" fontWeight={500}>
                          {t.symbol}
                        </Typography>
                      </TableCell>
                      <TableCell>
                        <Chip
                          label={t.type}
                          size="small"
                          color={t.type === 'BUY' ? 'success' : 'error'}
                          sx={{ fontWeight: 700, fontSize: '0.6rem', height: 16 }}
                        />
                      </TableCell>
                      <TableCell align="right">
                        <Typography variant="subtitle2">{t.volume}</Typography>
                      </TableCell>
                      <TableCell align="right">
                        <Typography variant="subtitle2">{fmt(t.open_price)}</Typography>
                      </TableCell>
                      <TableCell align="right">
                        <Typography variant="subtitle2">{fmt(t.close_price)}</Typography>
                      </TableCell>
                      <TableCell align="right">
                        <Typography
                          variant="subtitle2"
                          color={t.pnl >= 0 ? 'success.main' : 'error.main'}
                          fontWeight={600}
                        >
                          {t.pnl >= 0 ? '+' : ''}
                          {t.pnl.toFixed(2)}
                        </Typography>
                      </TableCell>
                      <TableCell align="right">
                        <Typography
                          variant="caption"
                          color={t.pnl_points >= 0 ? 'success.light' : 'error.light'}
                        >
                          {t.pnl_points >= 0 ? '+' : ''}
                          {t.pnl_points.toFixed(1)}
                        </Typography>
                      </TableCell>
                      <TableCell>
                        <Typography variant="caption" color="text.secondary">
                          {fmtDate(t.close_time)}
                        </Typography>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </TableContainer>
          )}
        </CardContent>
      </Card>
    </Box>
  )
}
