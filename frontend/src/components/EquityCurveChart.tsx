import {
  ResponsiveContainer,
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ReferenceLine,
} from 'recharts'
import { Box, Typography, useTheme } from '@mui/material'

interface Props {
  equityCurve: number[]
  deposit?: number
  height?: number
}

function buildChartData(curve: number[]) {
  return curve.map((v, i) => ({ bar: i, pnl: v }))
}

function calcMaxDD(curve: number[]): number {
  let peak = -Infinity
  let maxDD = 0
  for (const v of curve) {
    if (v > peak) peak = v
    const dd = peak - v
    if (dd > maxDD) maxDD = dd
  }
  return maxDD
}

const CustomTooltip = ({ active, payload }: { active?: boolean; payload?: Array<{ value: number }> }) => {
  if (!active || !payload?.length) return null
  const val = payload[0].value
  return (
    <Box
      sx={{
        bgcolor: 'background.paper',
        border: '1px solid',
        borderColor: 'divider',
        px: 1.5,
        py: 1,
        borderRadius: 1,
      }}
    >
      <Typography variant="subtitle2" color={val >= 0 ? 'success.main' : 'error.main'}>
        {val >= 0 ? '+' : ''}
        {val.toFixed(2)}
      </Typography>
    </Box>
  )
}

export default function EquityCurveChart({ equityCurve, height = 220 }: Props) {
  const theme = useTheme()

  if (!equityCurve || equityCurve.length === 0) {
    return (
      <Box sx={{ height, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        <Typography variant="body2" color="text.secondary">
          No data
        </Typography>
      </Box>
    )
  }

  const data = buildChartData(equityCurve)
  const maxDD = calcMaxDD(equityCurve)
  const finalPnl = equityCurve[equityCurve.length - 1]
  const isProfit = finalPnl >= 0

  const strokeColor = isProfit ? theme.palette.success.main : theme.palette.error.main
  const fillId = `equity-fill-${isProfit ? 'green' : 'red'}`

  return (
    <Box>
      <Box sx={{ display: 'flex', gap: 3, mb: 1, flexWrap: 'wrap' }}>
        <Box>
          <Typography variant="overline" color="text.secondary">
            Net P&L
          </Typography>
          <Typography
            variant="subtitle2"
            color={isProfit ? 'success.main' : 'error.main'}
            sx={{ fontSize: '1rem', fontWeight: 700 }}
          >
            {finalPnl >= 0 ? '+' : ''}
            {finalPnl.toFixed(2)}
          </Typography>
        </Box>
        <Box>
          <Typography variant="overline" color="text.secondary">
            Max DD
          </Typography>
          <Typography variant="subtitle2" color="error.light" sx={{ fontSize: '1rem' }}>
            -{maxDD.toFixed(2)}
          </Typography>
        </Box>
        <Box>
          <Typography variant="overline" color="text.secondary">
            Bars
          </Typography>
          <Typography variant="subtitle2" sx={{ fontSize: '1rem' }}>
            {equityCurve.length}
          </Typography>
        </Box>
      </Box>

      <ResponsiveContainer width="100%" height={height}>
        <AreaChart data={data} margin={{ top: 4, right: 4, left: -20, bottom: 0 }}>
          <defs>
            <linearGradient id={fillId} x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor={strokeColor} stopOpacity={0.3} />
              <stop offset="95%" stopColor={strokeColor} stopOpacity={0} />
            </linearGradient>
          </defs>
          <CartesianGrid strokeDasharray="3 3" stroke={theme.palette.divider} />
          <XAxis dataKey="bar" tick={{ fontSize: 10 }} stroke={theme.palette.divider} />
          <YAxis tick={{ fontSize: 10 }} stroke={theme.palette.divider} />
          <Tooltip content={<CustomTooltip />} />
          <ReferenceLine y={0} stroke={theme.palette.divider} strokeWidth={1} />
          <Area
            type="monotone"
            dataKey="pnl"
            stroke={strokeColor}
            strokeWidth={1.5}
            fill={`url(#${fillId})`}
            dot={false}
            isAnimationActive={equityCurve.length < 1000}
          />
        </AreaChart>
      </ResponsiveContainer>
    </Box>
  )
}
