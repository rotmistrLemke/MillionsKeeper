import { create } from 'zustand'
import type {
  AccountInfo,
  AgentStatusInfo,
  Position,
  AgentEvent,
  BacktestResult,
  WsMessage,
} from '../types'

const MAX_EVENTS = 200

interface TradingState {
  // Connection
  wsConnected: boolean
  setWsConnected: (v: boolean) => void

  // Account
  account: AccountInfo | null
  setAccount: (a: AccountInfo) => void

  // Agents
  agents: AgentStatusInfo[]
  setAgents: (agents: AgentStatusInfo[]) => void
  updateAgent: (agent: AgentStatusInfo) => void

  // Positions
  positions: Position[]
  setPositions: (positions: Position[]) => void

  // Events feed
  events: AgentEvent[]
  addEvent: (event: AgentEvent) => void

  // Last backtest result (realtime)
  lastBacktestResult: BacktestResult | null
  setLastBacktestResult: (r: BacktestResult) => void

  // WS dispatcher
  dispatchWsMessage: (msg: WsMessage) => void
}

export const useTradingStore = create<TradingState>((set, get) => ({
  wsConnected: false,
  setWsConnected: (v) => set({ wsConnected: v }),

  account: null,
  setAccount: (a) => set({ account: a }),

  agents: [],
  setAgents: (agents) => set({ agents }),
  updateAgent: (agent) =>
    set((state) => {
      const idx = state.agents.findIndex((a) => a.name === agent.name)
      if (idx === -1) return { agents: [...state.agents, agent] }
      const agents = [...state.agents]
      agents[idx] = agent
      return { agents }
    }),

  positions: [],
  setPositions: (positions) => set({ positions: Array.isArray(positions) ? positions : [] }),

  events: [],
  addEvent: (event) =>
    set((state) => {
      const keyed = event.id ? event : { ...event, id: Date.now() + Math.random() }
      return { events: [keyed, ...state.events].slice(0, MAX_EVENTS) }
    }),

  lastBacktestResult: null,
  setLastBacktestResult: (r) => set({ lastBacktestResult: r }),

  dispatchWsMessage: (msg) => {
    const { setAccount, updateAgent, setPositions, addEvent, setLastBacktestResult } = get()
    switch (msg.type) {
      case 'account_update':
        setAccount(msg.payload as AccountInfo)
        break
      case 'agent_status': {
        const raw = msg.payload as any
        updateAgent({
          name:        raw.agent ?? raw.name,
          status:      raw.status,
          message:     raw.detail ?? raw.message ?? '',
          metrics:     raw.metrics ?? {},
          last_update: null,
        } as AgentStatusInfo)
        break
      }
      case 'position_update': {
        const raw = msg.payload as any
        setPositions(Array.isArray(raw) ? raw : (raw?.positions ?? []))
        break
      }
      case 'agent_event':
        addEvent(msg.payload as AgentEvent)
        break
      case 'backtest_result':
        setLastBacktestResult(msg.payload as BacktestResult)
        break
      case 'ping':
        break
    }
  },
}))
