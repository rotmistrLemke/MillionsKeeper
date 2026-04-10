/**
 * types/index.ts — TypeScript интерфейсы, синхронизированы с backend Pydantic schemas.
 *
 * Все типы соответствуют backend/app/models/schemas.py
 */

// ── Agent ────────────────────────────────────────────────────────

export type AgentStatusValue = 'idle' | 'running' | 'error' | 'stopped'

export interface AgentStatusInfo {
  name: string
  status: AgentStatusValue
  message: string
  last_update: string | null
  metrics: Record<string, unknown>
}

// ── Account ──────────────────────────────────────────────────────

export interface AccountInfo {
  balance: number
  equity: number
  margin: number
  free_margin: number
  margin_level: number
  currency: string
  login: number
  server: string
}

// ── Position ─────────────────────────────────────────────────────

export type OrderType = 'BUY' | 'SELL'

export interface Position {
  ticket: number
  symbol: string
  type: OrderType
  volume: number
  open_price: number
  sl: number
  tp: number
  pnl: number
  open_time: number
}

// ── Trade ─────────────────────────────────────────────────────────

export interface Trade {
  id: number
  ticket: number
  symbol: string
  type: OrderType
  volume: number
  open_price: number
  close_price: number
  sl: number
  tp: number
  pnl: number
  pnl_points: number
  open_time: string
  close_time: string
  strategy: string
}

// ── Backtest ─────────────────────────────────────────────────────

export interface BacktestRequest {
  strategy: string
  symbol: string
  bars?: number
  deposit?: number
  spread?: number
  risk?: number
  timeframe?: string
}

export interface BacktestMetrics {
  total_trades: number
  win_rate: number
  profit_factor: number
  sharpe_ratio: number
  max_drawdown: number
  max_drawdown_money: number
  total_profit: number
  total_profit_points: number
  avg_profit_per_trade: number
  final_balance: number
  return_pct: number
  max_consecutive_losses: number
}

export interface BacktestResult {
  id?: number
  strategy: string
  symbol: string
  timeframe: string
  bars: number
  deposit: number
  metrics: BacktestMetrics
  equity_curve: number[]
  started_at: string
  finished_at: string
}

// ── Strategy ─────────────────────────────────────────────────────

export interface StrategyConfig {
  name: string
  display_name: string
  description: string
  enabled: boolean
  default_timeframe: string
  params: Record<string, number | string | boolean>
}

// ── Event ────────────────────────────────────────────────────────

export interface AgentEvent {
  id: number
  agent_name: string
  event_type: string
  status: AgentStatusValue
  message: string
  created_at: string
  payload: Record<string, unknown>
}

// ── WebSocket messages ───────────────────────────────────────────

export type WsMsgType =
  | 'agent_status'
  | 'account_update'
  | 'position_update'
  | 'agent_event'
  | 'backtest_result'
  | 'ping'

export interface WsMessage {
  type: WsMsgType
  payload?: unknown
}

// ── Trading control ──────────────────────────────────────────────

export interface TradingStatusMap {
  [symbol: string]: number // 0 = enabled, 3 = disabled
}
