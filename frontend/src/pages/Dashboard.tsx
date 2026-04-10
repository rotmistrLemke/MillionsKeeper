import { Box, Grid } from '@mui/material'
import { useQuery } from '@tanstack/react-query'
import { useEffect } from 'react'
import AccountCard from '../components/AccountCard'
import PositionsTable from '../components/PositionsTable'
import AgentStatusGrid from '../components/AgentStatusGrid'
import EventFeed from '../components/EventFeed'
import { fetchAccount, fetchPositions, fetchAgents, fetchEvents } from '../api/endpoints'
import { useTradingStore } from '../store/tradingStore'

export default function Dashboard() {
  const setAccount = useTradingStore((s) => s.setAccount)
  const setPositions = useTradingStore((s) => s.setPositions)
  const setAgents = useTradingStore((s) => s.setAgents)

  const { data: account } = useQuery({
    queryKey: ['account'],
    queryFn: fetchAccount,
    refetchInterval: 5_000,
  })
  const { data: positions } = useQuery({
    queryKey: ['positions'],
    queryFn: fetchPositions,
    refetchInterval: 3_000,
  })
  const { data: agents } = useQuery({
    queryKey: ['agents'],
    queryFn: fetchAgents,
    refetchInterval: 5_000,
  })
  useQuery({
    queryKey: ['events'],
    queryFn: () => fetchEvents(50),
    staleTime: Infinity, // updated via WS
  })

  useEffect(() => { if (account) setAccount(account) }, [account, setAccount])
  useEffect(() => { if (positions) setPositions(positions) }, [positions, setPositions])
  useEffect(() => { if (agents) setAgents(agents) }, [agents, setAgents])

  return (
    <Box sx={{ p: { xs: 1.5, md: 2 } }}>
      <Grid container spacing={2}>
        {/* Account */}
        <Grid size={{ xs: 12 }}>
          <AccountCard />
        </Grid>

        {/* Positions */}
        <Grid size={{ xs: 12 }}>
          <PositionsTable />
        </Grid>

        {/* Agents + Events */}
        <Grid size={{ xs: 12, md: 7 }}>
          <AgentStatusGrid />
        </Grid>
        <Grid size={{ xs: 12, md: 5 }}>
          <EventFeed />
        </Grid>
      </Grid>
    </Box>
  )
}
