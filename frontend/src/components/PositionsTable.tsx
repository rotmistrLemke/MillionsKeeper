import {
  Card,
  CardContent,
  Typography,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Chip,
  IconButton,
  Box,
  Tooltip,
} from '@mui/material'
import CloseIcon from '@mui/icons-material/Close'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useTradingStore } from '../store/tradingStore'
import { closePosition } from '../api/endpoints'

export default function PositionsTable() {
  const positions = useTradingStore((s) => s.positions)
  const qc = useQueryClient()

  const closeMutation = useMutation({
    mutationFn: (ticket: number) => closePosition(ticket),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['positions'] }),
  })

  const fmt = (v: number, d = 5) => v.toFixed(d)
  const fmtMoney = (v: number) => (v >= 0 ? '+' : '') + v.toFixed(2)

  return (
    <Card>
      <CardContent sx={{ pb: '12px !important' }}>
        <Box sx={{ display: 'flex', alignItems: 'center', mb: 1.5 }}>
          <Typography variant="h6">Open Positions</Typography>
          <Chip
            label={positions.length}
            size="small"
            sx={{ ml: 1, height: 18, fontSize: '0.7rem' }}
            color={positions.length > 0 ? 'primary' : 'default'}
          />
        </Box>

        {positions.length === 0 ? (
          <Typography variant="body2" color="text.secondary" sx={{ py: 2, textAlign: 'center' }}>
            No open positions
          </Typography>
        ) : (
          <TableContainer>
            <Table size="small">
              <TableHead>
                <TableRow>
                  <TableCell>Symbol</TableCell>
                  <TableCell>Type</TableCell>
                  <TableCell align="right">Volume</TableCell>
                  <TableCell align="right">Open</TableCell>
                  <TableCell align="right">SL</TableCell>
                  <TableCell align="right">TP</TableCell>
                  <TableCell align="right">P&L</TableCell>
                  <TableCell align="center">Close</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {positions.map((pos) => (
                  <TableRow key={pos.ticket} hover>
                    <TableCell>
                      <Typography variant="body2" fontWeight={500}>
                        {pos.symbol}
                      </Typography>
                    </TableCell>
                    <TableCell>
                      <Chip
                        label={pos.type}
                        size="small"
                        color={pos.type === 'BUY' ? 'success' : 'error'}
                        sx={{ fontWeight: 700, fontSize: '0.65rem', height: 18 }}
                      />
                    </TableCell>
                    <TableCell align="right">
                      <Typography variant="subtitle2">{pos.volume}</Typography>
                    </TableCell>
                    <TableCell align="right">
                      <Typography variant="subtitle2">{fmt(pos.open_price)}</Typography>
                    </TableCell>
                    <TableCell align="right">
                      <Typography variant="subtitle2" color="error.light">
                        {pos.sl ? fmt(pos.sl) : '—'}
                      </Typography>
                    </TableCell>
                    <TableCell align="right">
                      <Typography variant="subtitle2" color="success.light">
                        {pos.tp ? fmt(pos.tp) : '—'}
                      </Typography>
                    </TableCell>
                    <TableCell align="right">
                      <Typography
                        variant="subtitle2"
                        color={pos.pnl >= 0 ? 'success.main' : 'error.main'}
                        fontWeight={600}
                      >
                        {fmtMoney(pos.pnl)}
                      </Typography>
                    </TableCell>
                    <TableCell align="center">
                      <Tooltip title="Close position">
                        <IconButton
                          size="small"
                          color="error"
                          onClick={() => closeMutation.mutate(pos.ticket)}
                          disabled={closeMutation.isPending}
                        >
                          <CloseIcon fontSize="small" />
                        </IconButton>
                      </Tooltip>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </TableContainer>
        )}
      </CardContent>
    </Card>
  )
}
