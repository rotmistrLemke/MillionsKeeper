import {
  Box,
  Card,
  CardContent,
  Chip,
  Grid,
  Switch,
  Typography,
  TextField,
  Button,
  Divider,
  Alert,
} from '@mui/material'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { fetchStrategies, updateStrategy } from '../api/endpoints'
import type { StrategyConfig } from '../types'

function ParamEditor({
  params,
  onChange,
}: {
  params: Record<string, number | string | boolean>
  onChange: (key: string, val: number | string | boolean) => void
}) {
  return (
    <Grid container spacing={1} sx={{ mt: 1 }}>
      {Object.entries(params).map(([key, val]) => (
        <Grid key={key} size={{ xs: 6, sm: 4 }}>
          <TextField
            size="small"
            label={key}
            value={val}
            type={typeof val === 'number' ? 'number' : 'text'}
            onChange={(e) =>
              onChange(key, typeof val === 'number' ? Number(e.target.value) : e.target.value)
            }
            fullWidth
            inputProps={{ step: 'any' }}
          />
        </Grid>
      ))}
    </Grid>
  )
}

function StrategyCard({ strategy }: { strategy: StrategyConfig }) {
  const qc = useQueryClient()
  const [params, setParams] = useState(strategy.params)
  const [dirty, setDirty] = useState(false)
  const [success, setSuccess] = useState(false)

  const mutation = useMutation({
    mutationFn: (config: Partial<StrategyConfig>) => updateStrategy(strategy.name, config),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['strategies'] })
      setDirty(false)
      setSuccess(true)
      setTimeout(() => setSuccess(false), 3000)
    },
  })

  const handleToggle = () =>
    mutation.mutate({ enabled: !strategy.enabled })

  const handleParamChange = (key: string, val: number | string | boolean) => {
    setParams((p) => ({ ...p, [key]: val }))
    setDirty(true)
  }

  const handleSave = () => mutation.mutate({ params })

  return (
    <Card
      sx={{
        border: '1px solid',
        borderColor: strategy.enabled ? 'primary.dark' : 'divider',
        transition: 'border-color 0.3s',
      }}
    >
      <CardContent>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 0.5 }}>
          <Typography variant="h6" sx={{ flexGrow: 1, fontSize: '0.95rem' }}>
            {strategy.display_name || strategy.name}
          </Typography>
          <Chip
            label={strategy.default_timeframe}
            size="small"
            variant="outlined"
            sx={{ fontSize: '0.65rem', height: 18 }}
          />
          <Switch
            checked={strategy.enabled}
            onChange={handleToggle}
            color="primary"
            size="small"
          />
        </Box>

        <Typography variant="caption" color="text.secondary" display="block" sx={{ mb: 1 }}>
          {strategy.description}
        </Typography>

        <Divider />

        <ParamEditor params={params} onChange={handleParamChange} />

        {(dirty || success) && (
          <Box sx={{ mt: 1.5, display: 'flex', gap: 1, alignItems: 'center' }}>
            {dirty && (
              <Button
                size="small"
                variant="contained"
                onClick={handleSave}
                disabled={mutation.isPending}
              >
                Save Params
              </Button>
            )}
            {success && (
              <Alert severity="success" sx={{ py: 0, fontSize: '0.75rem' }}>
                Saved
              </Alert>
            )}
          </Box>
        )}
      </CardContent>
    </Card>
  )
}

export default function StrategiesPage() {
  const { data: strategies = [], isLoading } = useQuery({
    queryKey: ['strategies'],
    queryFn: fetchStrategies,
  })

  return (
    <Box sx={{ p: { xs: 1.5, md: 2 } }}>
      <Box sx={{ display: 'flex', alignItems: 'baseline', gap: 2, mb: 2 }}>
        <Typography variant="h5">Strategies</Typography>
        <Typography variant="caption" color="text.secondary">
          {strategies.filter((s) => s.enabled).length}/{strategies.length} enabled
        </Typography>
      </Box>

      {isLoading ? (
        <Typography color="text.secondary">Loading...</Typography>
      ) : (
        <Grid container spacing={2}>
          {strategies.map((s) => (
            <Grid key={s.name} size={{ xs: 12, sm: 6, lg: 4 }}>
              <StrategyCard strategy={s} />
            </Grid>
          ))}
        </Grid>
      )}
    </Box>
  )
}
