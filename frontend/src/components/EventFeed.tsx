import { Box, Card, CardContent, Chip, Typography } from '@mui/material'
import { useTradingStore } from '../store/tradingStore'
import type { AgentStatusValue } from '../types'

const STATUS_COLOR: Record<AgentStatusValue, string> = {
  idle: '#8a8d9a',
  running: '#26a69a',
  error: '#ef5350',
  stopped: '#ff9800',
}

const EVENT_BG: Record<string, string> = {
  ORDER_OPENED: 'rgba(38,166,154,0.08)',
  ORDER_CLOSED: 'rgba(239,83,80,0.08)',
  BACKTEST_RESULT: 'rgba(245,200,66,0.08)',
  ORDER_ERROR: 'rgba(239,83,80,0.12)',
}

function relTime(ts: string) {
  const diff = Date.now() - new Date(ts).getTime()
  const sec = Math.floor(diff / 1000)
  if (sec < 60) return `${sec}s ago`
  const min = Math.floor(sec / 60)
  if (min < 60) return `${min}m ago`
  return `${Math.floor(min / 60)}h ago`
}

export default function EventFeed() {
  const events = useTradingStore((s) => s.events)

  return (
    <Card sx={{ height: '100%' }}>
      <CardContent sx={{ pb: '12px !important' }}>
        <Typography variant="h6" sx={{ mb: 1.5 }}>
          Event Feed
          <Typography component="span" variant="caption" color="text.secondary" sx={{ ml: 1 }}>
            (last {events.length})
          </Typography>
        </Typography>

        <Box
          sx={{
            maxHeight: 360,
            overflowY: 'auto',
            display: 'flex',
            flexDirection: 'column',
            gap: 0.5,
            '&::-webkit-scrollbar': { width: 4 },
            '&::-webkit-scrollbar-thumb': { bgcolor: 'divider', borderRadius: 2 },
          }}
        >
          {events.length === 0 ? (
            <Typography variant="body2" color="text.secondary" sx={{ textAlign: 'center', py: 3 }}>
              Waiting for events...
            </Typography>
          ) : (
            events.map((ev) => (
              <Box
                key={ev.id}
                sx={{
                  px: 1.5,
                  py: 0.75,
                  borderRadius: 1,
                  bgcolor: EVENT_BG[ev.event_type] ?? 'background.default',
                  borderLeft: '3px solid',
                  borderColor: STATUS_COLOR[ev.status] ?? 'divider',
                }}
              >
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 0.25 }}>
                  <Chip
                    label={ev.agent_name}
                    size="small"
                    sx={{ fontSize: '0.6rem', height: 16, fontWeight: 600 }}
                  />
                  <Typography variant="overline" sx={{ fontSize: '0.6rem', color: 'text.secondary' }}>
                    {ev.event_type}
                  </Typography>
                  <Typography variant="caption" color="text.secondary" sx={{ ml: 'auto' }}>
                    {relTime(ev.created_at)}
                  </Typography>
                </Box>
                <Typography variant="body2" color="text.primary" sx={{ fontSize: '0.78rem' }}>
                  {ev.message}
                </Typography>
              </Box>
            ))
          )}
        </Box>
      </CardContent>
    </Card>
  )
}
