import client from './client'
import type {
  AccountInfo,
  AgentStatusInfo,
  Position,
  Trade,
  BacktestRequest,
  BacktestResult,
  StrategyConfig,
  AgentEvent,
} from '../types'

// ── Auth ─────────────────────────────────────────────────────────────────────

export async function login(login: number, password: string, server: string): Promise<{ token: string }> {
  const { data } = await client.post('/auth/login', { login, password, server })
  return data
}

// ── Account ───────────────────────────────────────────────────────────────────

export async function fetchAccount(): Promise<AccountInfo> {
  const { data } = await client.get('/account')
  return data
}

// ── Agents ────────────────────────────────────────────────────────────────────

export async function fetchAgents(): Promise<AgentStatusInfo[]> {
  const { data } = await client.get('/agents')
  return data
}

// ── Positions ─────────────────────────────────────────────────────────────────

export async function fetchPositions(): Promise<Position[]> {
  const { data } = await client.get('/positions')
  return data
}

export async function closePosition(ticket: number): Promise<{ ok: boolean }> {
  const { data } = await client.post(`/positions/${ticket}/close`)
  return data
}

// ── Events ────────────────────────────────────────────────────────────────────

export async function fetchEvents(limit = 50): Promise<AgentEvent[]> {
  const { data } = await client.get('/events', { params: { limit } })
  return data
}

// ── Backtest ──────────────────────────────────────────────────────────────────

export async function startBacktest(req: BacktestRequest): Promise<{ run_id: string }> {
  const { data } = await client.post('/backtest/run', req)
  return data
}

export async function fetchBacktestResults(limit = 20): Promise<BacktestResult[]> {
  const { data } = await client.get('/backtest/results', { params: { limit } })
  return data
}

export async function fetchBacktestResult(id: string): Promise<BacktestResult> {
  const { data } = await client.get(`/backtest/results/${id}`)
  return data
}

// ── Strategies ────────────────────────────────────────────────────────────────

export async function fetchStrategies(): Promise<StrategyConfig[]> {
  const { data } = await client.get('/strategies')
  return data
}

export async function updateStrategy(name: string, config: Partial<StrategyConfig>): Promise<StrategyConfig> {
  const { data } = await client.put(`/strategies/${name}`, config)
  return data
}

// ── History ───────────────────────────────────────────────────────────────────

export async function fetchHistory(params?: {
  symbol?: string
  from?: string
  to?: string
  limit?: number
}): Promise<Trade[]> {
  const { data } = await client.get('/history', { params })
  return data
}
