import { createTheme, alpha } from '@mui/material/styles'

const BRAND = {
  gold: '#f5c842',
  green: '#26a69a',
  red: '#ef5350',
  blue: '#42a5f5',
}

const theme = createTheme({
  palette: {
    mode: 'dark',
    primary: {
      main: BRAND.gold,
      contrastText: '#0a0a0f',
    },
    secondary: {
      main: BRAND.green,
    },
    error: {
      main: BRAND.red,
    },
    info: {
      main: BRAND.blue,
    },
    success: {
      main: BRAND.green,
    },
    background: {
      default: '#0a0a0f',
      paper: '#12121a',
    },
    text: {
      primary: '#e8eaf0',
      secondary: '#8a8d9a',
    },
    divider: alpha('#ffffff', 0.08),
  },
  typography: {
    fontFamily: '"Inter", "Roboto", "Helvetica", "Arial", sans-serif',
    fontWeightLight: 300,
    fontWeightRegular: 400,
    fontWeightMedium: 500,
    fontWeightBold: 600,
    h1: { fontSize: '1.75rem', fontWeight: 600 },
    h2: { fontSize: '1.5rem', fontWeight: 600 },
    h3: { fontSize: '1.25rem', fontWeight: 600 },
    h4: { fontSize: '1.1rem', fontWeight: 500 },
    h5: { fontSize: '1rem', fontWeight: 500 },
    h6: { fontSize: '0.875rem', fontWeight: 500 },
    body1: { fontSize: '0.9rem' },
    body2: { fontSize: '0.8rem' },
    caption: { fontSize: '0.75rem', color: '#8a8d9a' },
    overline: {
      fontSize: '0.65rem',
      fontWeight: 600,
      letterSpacing: '0.08em',
      textTransform: 'uppercase',
    },
    // Monospace for prices/numbers
    subtitle2: {
      fontFamily: '"JetBrains Mono", "Courier New", monospace',
      fontSize: '0.85rem',
      fontWeight: 500,
    },
  },
  shape: {
    borderRadius: 8,
  },
  components: {
    MuiCard: {
      defaultProps: { elevation: 0 },
      styleOverrides: {
        root: {
          border: `1px solid ${alpha('#ffffff', 0.08)}`,
          backgroundImage: 'none',
        },
      },
    },
    MuiPaper: {
      defaultProps: { elevation: 0 },
      styleOverrides: {
        root: { backgroundImage: 'none' },
      },
    },
    MuiButton: {
      defaultProps: { disableElevation: true },
      styleOverrides: {
        root: {
          textTransform: 'none',
          fontWeight: 500,
          borderRadius: 6,
        },
        containedPrimary: {
          '&:hover': { backgroundColor: '#e6b800' },
        },
      },
    },
    MuiChip: {
      styleOverrides: {
        root: { borderRadius: 6, fontWeight: 500 },
      },
    },
    MuiTableCell: {
      styleOverrides: {
        head: {
          fontWeight: 600,
          fontSize: '0.72rem',
          textTransform: 'uppercase',
          letterSpacing: '0.05em',
          color: '#8a8d9a',
          borderBottom: `1px solid ${alpha('#ffffff', 0.08)}`,
        },
        body: {
          fontSize: '0.85rem',
          borderBottom: `1px solid ${alpha('#ffffff', 0.05)}`,
        },
      },
    },
    MuiLinearProgress: {
      styleOverrides: {
        root: { borderRadius: 4, height: 6 },
      },
    },
    MuiTooltip: {
      defaultProps: { arrow: true },
    },
  },
})

export default theme
export { BRAND }
