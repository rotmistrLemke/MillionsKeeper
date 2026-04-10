import { Card, CardContent, Grid, Typography, Box, Divider, Skeleton } from '@mui/material'
import AccountBalanceWalletIcon from '@mui/icons-material/AccountBalanceWallet'
import { useTradingStore } from '../store/tradingStore'

function Stat({ label, value, color }: { label: string; value: string; color?: string }) {
  return (
    <Box>
      <Typography variant="overline" color="text.secondary">
        {label}
      </Typography>
      <Typography variant="subtitle2" color={color ?? 'text.primary'} sx={{ fontSize: '1rem', fontWeight: 600 }}>
        {value}
      </Typography>
    </Box>
  )
}

export default function AccountCard() {
  const account = useTradingStore((s) => s.account)

  const fmt = (v: number, decimals = 2) =>
    v.toLocaleString('en-US', { minimumFractionDigits: decimals, maximumFractionDigits: decimals })

  const marginLevel = account?.margin_level ?? 0

  return (
    <Card>
      <CardContent>
        <Box sx={{ display: 'flex', alignItems: 'center', mb: 1.5, gap: 1 }}>
          <AccountBalanceWalletIcon sx={{ color: 'primary.main', fontSize: 20 }} />
          <Typography variant="h6">Account</Typography>
          {account && (
            <Typography variant="caption" sx={{ ml: 'auto', color: 'text.secondary' }}>
              #{account.login} · {account.server}
            </Typography>
          )}
        </Box>

        <Divider sx={{ mb: 2 }} />

        {!account ? (
          <Grid container spacing={2}>
            {[...Array(4)].map((_, i) => (
              <Grid key={i} size={{ xs: 6, sm: 3 }}>
                <Skeleton variant="text" width="60%" />
                <Skeleton variant="text" width="80%" height={28} />
              </Grid>
            ))}
          </Grid>
        ) : (
          <Grid container spacing={2}>
            <Grid size={{ xs: 6, sm: 3 }}>
              <Stat label="Balance" value={`${fmt(account.balance)} ${account.currency}`} color="text.primary" />
            </Grid>
            <Grid size={{ xs: 6, sm: 3 }}>
              <Stat
                label="Equity"
                value={`${fmt(account.equity)} ${account.currency}`}
                color={account.equity >= account.balance ? 'success.main' : 'error.main'}
              />
            </Grid>
            <Grid size={{ xs: 6, sm: 3 }}>
              <Stat label="Free Margin" value={`${fmt(account.free_margin)} ${account.currency}`} />
            </Grid>
            <Grid size={{ xs: 6, sm: 3 }}>
              <Stat
                label="Margin Level"
                value={account.margin > 0 ? `${fmt(marginLevel, 0)}%` : '—'}
                color={marginLevel > 200 ? 'success.main' : marginLevel > 100 ? 'warning.main' : 'error.main'}
              />
            </Grid>
          </Grid>
        )}
      </CardContent>
    </Card>
  )
}
