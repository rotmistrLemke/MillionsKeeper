import { BrowserRouter, Routes, Route, Navigate, useLocation } from 'react-router-dom'
import {
  AppBar,
  BottomNavigation,
  BottomNavigationAction,
  Box,
  Toolbar,
  Typography,
  useMediaQuery,
  useTheme,
  Drawer,
  List,
  ListItem,
  ListItemButton,
  ListItemIcon,
  ListItemText,
  Chip,
} from '@mui/material'
import DashboardIcon from '@mui/icons-material/Dashboard'
import HistoryIcon from '@mui/icons-material/History'
import PlayCircleIcon from '@mui/icons-material/PlayCircle'
import TuneIcon from '@mui/icons-material/Tune'
import ShowChartIcon from '@mui/icons-material/ShowChart'
import { useNavigate } from 'react-router-dom'

import Dashboard from './pages/Dashboard'
import BacktestPage from './pages/BacktestPage'
import StrategiesPage from './pages/StrategiesPage'
import HistoryPage from './pages/HistoryPage'
import { useWebSocket } from './hooks/useWebSocket'
import { useTradingStore } from './store/tradingStore'

const NAV_ITEMS = [
  { label: 'Dashboard', path: '/', icon: <DashboardIcon /> },
  { label: 'Backtest', path: '/backtest', icon: <PlayCircleIcon /> },
  { label: 'Strategies', path: '/strategies', icon: <TuneIcon /> },
  { label: 'History', path: '/history', icon: <HistoryIcon /> },
]

const SIDEBAR_WIDTH = 220

function Layout() {
  const theme = useTheme()
  const isMobile = useMediaQuery(theme.breakpoints.down('md'))
  const location = useLocation()
  const navigate = useNavigate()
  const wsConnected = useTradingStore((s) => s.wsConnected)

  const currentIndex = NAV_ITEMS.findIndex((item) =>
    item.path === '/' ? location.pathname === '/' : location.pathname.startsWith(item.path)
  )

  return (
    <Box sx={{ display: 'flex', minHeight: '100vh', bgcolor: 'background.default' }}>
      {/* AppBar */}
      <AppBar
        position="fixed"
        elevation={0}
        sx={{
          bgcolor: 'background.paper',
          borderBottom: '1px solid',
          borderColor: 'divider',
          zIndex: (t) => t.zIndex.drawer + 1,
          width: isMobile ? '100%' : `calc(100% - ${SIDEBAR_WIDTH}px)`,
          ml: isMobile ? 0 : `${SIDEBAR_WIDTH}px`,
        }}
      >
        <Toolbar variant="dense">
          <ShowChartIcon sx={{ color: 'primary.main', mr: 1, fontSize: 20 }} />
          <Typography variant="h6" sx={{ flexGrow: 1, fontWeight: 700, fontSize: '1rem' }}>
            MillionsKeeper
          </Typography>
          <Chip
            label={wsConnected ? 'LIVE' : 'OFFLINE'}
            size="small"
            color={wsConnected ? 'success' : 'error'}
            sx={{ fontWeight: 700, fontSize: '0.65rem', height: 20 }}
          />
        </Toolbar>
      </AppBar>

      {/* Desktop Sidebar */}
      {!isMobile && (
        <Drawer
          variant="permanent"
          sx={{
            width: SIDEBAR_WIDTH,
            flexShrink: 0,
            '& .MuiDrawer-paper': {
              width: SIDEBAR_WIDTH,
              boxSizing: 'border-box',
              bgcolor: 'background.paper',
              borderRight: '1px solid',
              borderColor: 'divider',
              pt: '48px',
            },
          }}
        >
          <List dense sx={{ pt: 2 }}>
            {NAV_ITEMS.map((item) => {
              const selected =
                item.path === '/' ? location.pathname === '/' : location.pathname.startsWith(item.path)
              return (
                <ListItem key={item.path} disablePadding sx={{ mb: 0.5 }}>
                  <ListItemButton
                    selected={selected}
                    onClick={() => navigate(item.path)}
                    sx={{
                      mx: 1,
                      borderRadius: 1.5,
                      '&.Mui-selected': {
                        bgcolor: 'primary.main',
                        color: 'primary.contrastText',
                        '& .MuiListItemIcon-root': { color: 'primary.contrastText' },
                        '&:hover': { bgcolor: 'primary.main' },
                      },
                    }}
                  >
                    <ListItemIcon sx={{ minWidth: 36, color: selected ? 'inherit' : 'text.secondary' }}>
                      {item.icon}
                    </ListItemIcon>
                    <ListItemText
                      primary={item.label}
                      primaryTypographyProps={{ fontSize: '0.875rem', fontWeight: selected ? 600 : 400 }}
                    />
                  </ListItemButton>
                </ListItem>
              )
            })}
          </List>
        </Drawer>
      )}

      {/* Main content */}
      <Box
        component="main"
        sx={{
          flexGrow: 1,
          pt: '48px',
          pb: isMobile ? '56px' : 0,
          overflow: 'auto',
          minHeight: '100vh',
        }}
      >
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/backtest" element={<BacktestPage />} />
          <Route path="/strategies" element={<StrategiesPage />} />
          <Route path="/history" element={<HistoryPage />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </Box>

      {/* Mobile Bottom Navigation */}
      {isMobile && (
        <BottomNavigation
          value={currentIndex}
          onChange={(_, idx) => navigate(NAV_ITEMS[idx].path)}
          sx={{
            position: 'fixed',
            bottom: 0,
            left: 0,
            right: 0,
            bgcolor: 'background.paper',
            borderTop: '1px solid',
            borderColor: 'divider',
            zIndex: (t) => t.zIndex.appBar,
            height: 56,
          }}
        >
          {NAV_ITEMS.map((item) => (
            <BottomNavigationAction
              key={item.path}
              label={item.label}
              icon={item.icon}
              sx={{
                minWidth: 0,
                fontSize: '0.65rem',
                '&.Mui-selected': { color: 'primary.main' },
              }}
            />
          ))}
        </BottomNavigation>
      )}
    </Box>
  )
}

function WsProvider({ children }: { children: React.ReactNode }) {
  useWebSocket('/ws/events')
  return <>{children}</>
}

export default function App() {
  return (
    <BrowserRouter>
      <WsProvider>
        <Layout />
      </WsProvider>
    </BrowserRouter>
  )
}
