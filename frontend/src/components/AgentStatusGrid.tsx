import { Card, CardContent, Grid, Typography, Box, Chip, LinearProgress, Tooltip } from '@mui/material'
import SmartToyIcon from '@mui/icons-material/SmartToy'
import { useTradingStore } from '../store/tradingStore'
import type { AgentStatusValue } from '../types'

const STATUS_COLOR: Record<AgentStatusValue, 'success' | 'warning' | 'error' | 'default'> = {
  idle: 'default',
  running: 'success',
  error: 'error',
  stopped: 'warning',
}

const STATUS_LABEL: Record<AgentStatusValue, string> = {
  idle: 'IDLE',
  running: 'RUN',
  error: 'ERR',
  stopped: 'STOP',
}

function AgentCard({ name, status, message }: { name: string; status: AgentStatusValue; message: string }) {
  return (
    <Card
      sx={{
        border: '1px solid',
        borderColor: status === 'error' ? 'error.dark' : status === 'running' ? 'success.dark' : 'divider',
        transition: 'border-color 0.3s',
      }}
    >
      <CardContent sx={{ p: '10px 12px !important' }}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5, mb: 0.5 }}>
          <SmartToyIcon sx={{ fontSize: 14, color: 'text.secondary' }} />
          <Typography variant="body2" fontWeight={600} sx={{ flexGrow: 1, fontSize: '0.78rem' }}>
            {name}
          </Typography>
          <Chip
            label={STATUS_LABEL[status]}
            size="small"
            color={STATUS_COLOR[status]}
            sx={{ fontWeight: 700, fontSize: '0.6rem', height: 16 }}
          />
        </Box>

        {status === 'running' && (
          <LinearProgress
            color="success"
            sx={{ height: 2, borderRadius: 1, mb: 0.5 }}
          />
        )}

        <Tooltip title={message} placement="bottom">
          <Typography
            variant="caption"
            color="text.secondary"
            sx={{
              display: 'block',
              overflow: 'hidden',
              whiteSpace: 'nowrap',
              textOverflow: 'ellipsis',
              maxWidth: '100%',
            }}
          >
            {message || '—'}
          </Typography>
        </Tooltip>
      </CardContent>
    </Card>
  )
}

export default function AgentStatusGrid() {
  const agents = useTradingStore((s) => s.agents)

  return (
    <Box>
      <Typography variant="h6" sx={{ mb: 1.5 }}>
        Agents
        <Typography component="span" variant="caption" color="text.secondary" sx={{ ml: 1 }}>
          ({agents.filter((a) => a.status === 'running').length}/{agents.length} running)
        </Typography>
      </Typography>
      <Grid container spacing={1}>
        {agents.length === 0
          ? [...Array(8)].map((_, i) => (
              <Grid key={i} size={{ xs: 6, sm: 4, md: 3 }}>
                <Card sx={{ opacity: 0.4 }}>
                  <CardContent sx={{ p: '10px 12px !important' }}>
                    <Typography variant="caption" color="text.secondary">
                      Loading...
                    </Typography>
                  </CardContent>
                </Card>
              </Grid>
            ))
          : agents.map((agent) => (
              <Grid key={agent.name} size={{ xs: 6, sm: 4, md: 3 }}>
                <AgentCard name={agent.name} status={agent.status} message={agent.message} />
              </Grid>
            ))}
      </Grid>
    </Box>
  )
}
