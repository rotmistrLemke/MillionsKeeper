import { useState } from 'react'
import { Box, Button, Card, CardContent, CircularProgress, TextField, Typography, Alert } from '@mui/material'
import ShowChartIcon from '@mui/icons-material/ShowChart'
import { login } from '../api/endpoints'

export default function LoginPage({ onLogin }: { onLogin: () => void }) {
  const [mt5Login, setMt5Login] = useState('')
  const [password, setPassword] = useState('')
  const [server, setServer] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError(null)
    setLoading(true)
    try {
      const data = await login(Number(mt5Login), password, server)
      sessionStorage.setItem('mk_token', data.token)
      onLogin()
    } catch {
      setError('Неверный логин, пароль или сервер MT5')
    } finally {
      setLoading(false)
    }
  }

  return (
    <Box
      sx={{
        minHeight: '100vh',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        bgcolor: 'background.default',
        p: 2,
      }}
    >
      <Card sx={{ width: '100%', maxWidth: 380 }}>
        <CardContent sx={{ p: 4 }}>
          <Box sx={{ display: 'flex', alignItems: 'center', mb: 3, gap: 1 }}>
            <ShowChartIcon sx={{ color: 'primary.main', fontSize: 28 }} />
            <Typography variant="h6" fontWeight={700}>
              MillionsKeeper
            </Typography>
          </Box>

          <Typography variant="body2" color="text.secondary" mb={3}>
            Войдите с данными MT5 аккаунта
          </Typography>

          <Box component="form" onSubmit={handleSubmit} sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
            <TextField
              label="Логин MT5"
              type="number"
              value={mt5Login}
              onChange={(e) => setMt5Login(e.target.value)}
              required
              size="small"
              autoFocus
            />
            <TextField
              label="Пароль"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              size="small"
            />
            <TextField
              label="Сервер"
              placeholder="AlfaForexRU-Real"
              value={server}
              onChange={(e) => setServer(e.target.value)}
              required
              size="small"
            />

            {error && <Alert severity="error" sx={{ py: 0.5 }}>{error}</Alert>}

            <Button
              type="submit"
              variant="contained"
              disabled={loading}
              sx={{ mt: 1, fontWeight: 700 }}
            >
              {loading ? <CircularProgress size={20} color="inherit" /> : 'Войти'}
            </Button>
          </Box>
        </CardContent>
      </Card>
    </Box>
  )
}
