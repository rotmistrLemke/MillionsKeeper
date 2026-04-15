// ─── Strategy Metadata ────────────────────────────────────────────
const STRATEGY_META = {
  default: {
    name: 'MA + MACD + RSI (основная)',
    desc: [
      '<b>Вход:</b> EMA8 и EMA21 в одном направлении + MACD подтверждает + RSI в зоне',
      'BUY: EMA8 &gt; EMA21 + MACD &gt; 0 и растёт + RSI 55–70',
      'SELL: EMA8 &lt; EMA21 + MACD &lt; 0 и падает + RSI 30–45',
      '<b>Выход:</b> RSI пересекает 45 (BUY) или 55 (SELL)',
      '<b>Таймфрейм:</b> H1',
    ],
    indicators: [
      { col: 'ema8',        label: 'EMA8'     },
      { col: 'ema21',       label: 'EMA21'    },
      { col: 'macd_line',   label: 'MACD'     },
      { col: 'macd_signal', label: 'Signal'   },
      { col: 'rsi',         label: 'RSI'      },
      { col: 'atr',         label: 'ATR'      },
    ],
  },
  range_breakout: {
    name: 'Range Breakout',
    desc: [
      'Пробой 8-барного диапазона консолидации с ATR-фильтром.',
      '<b>Вход:</b>',
      'BUY: Закрытие выше максимума 8 баров + ATR &gt; среднего',
      'SELL: Закрытие ниже минимума 8 баров + ATR &gt; среднего',
      '<b>SL:</b> противоположная граница диапазона',
      '<b>TP:</b> размер диапазона от точки входа',
      '<b>Таймфрейм:</b> H1',
    ],
    indicators: [
      { col: 'range_high', label: 'Rng High' },
      { col: 'range_low',  label: 'Rng Low'  },
      { col: 'range_size', label: 'Rng Size' },
      { col: 'atr',        label: 'ATR'       },
    ],
  },
  ema_pullback: {
    name: 'EMA Pullback (50/200)',
    desc: [
      'Откат к EMA50 в направлении тренда EMA200.',
      '<b>Вход:</b>',
      'BUY: Цена &gt; EMA200 + откат к EMA50 + пин-бар или поглощение',
      'SELL: Цена &lt; EMA200 + откат к EMA50 + пин-бар или поглощение',
      '<b>SL:</b> 1.5 × ATR &nbsp; <b>TP:</b> 2.5 × ATR',
      '<b>Выход:</b> пересечение EMA200',
      '<b>Таймфрейм:</b> H1',
    ],
    indicators: [
      { col: 'ema50',  label: 'EMA50'  },
      { col: 'ema200', label: 'EMA200' },
      { col: 'atr',    label: 'ATR'    },
    ],
  },
  cci_rsi: {
    name: 'CCI + RSI (D1-фильтр)',
    desc: [
      'CCI(20) пересекает ±100, подтверждение RSI и EMA200 как D1-фильтр.',
      '<b>Вход:</b>',
      'BUY: CCI пересёк +100 снизу + RSI &gt; 50 + Цена &gt; EMA200',
      'SELL: CCI пересёк −100 сверху + RSI &lt; 50 + Цена &lt; EMA200',
      '<b>SL:</b> 1.5 × ATR &nbsp; <b>TP:</b> 2.5 × ATR',
      '<b>Выход:</b> CCI возвращается к нулю',
      '<b>Таймфрейм:</b> H1',
    ],
    indicators: [
      { col: 'cci',   label: 'CCI(20)' },
      { col: 'rsi',   label: 'RSI(14)' },
      { col: 'ema200',label: 'EMA200'  },
      { col: 'atr',   label: 'ATR'     },
    ],
  },
  fibonacci_retracement: {
    name: 'Fibonacci Retracement',
    desc: [
      'Откат к уровням Фибоначчи 38.2%–50% после импульсного движения.',
      '<b>Вход:</b>',
      'BUY: Бычий 5-барный импульс → откат 38.2–50% → подтверждающая свеча',
      'SELL: Медвежий 5-барный импульс → откат 38.2–50% → подтверждающая свеча',
      '<b>SL:</b> ниже уровня 61.8% &nbsp; <b>TP:</b> до экстремума импульса',
      '<b>Таймфрейм:</b> H1',
    ],
    indicators: [
      { col: 'imp_high',    label: 'Imp High' },
      { col: 'imp_low',     label: 'Imp Low'  },
      { col: 'fib_382_bull',label: 'Fib 38.2%'},
      { col: 'fib_500_bull',label: 'Fib 50%'  },
      { col: 'atr',         label: 'ATR'       },
    ],
  },
  news_breakout: {
    name: 'Post-News Breakout',
    desc: [
      'Пробой диапазона после волатильного (новостного) бара.',
      '<b>Новостной бар:</b> ATR бара ≥ 2 × среднего ATR(50)',
      '<b>Вход:</b> через 2 бара после шипа',
      'BUY: Пробой максимума шипа',
      'SELL: Пробой минимума шипа',
      '<b>SL:</b> 1.5 × ATR &nbsp; <b>TP:</b> 3 × ATR',
      '<b>Таймфрейм:</b> H1',
    ],
    indicators: [
      { col: 'atr',             label: 'ATR'     },
      { col: 'atr_avg',         label: 'ATR Avg' },
      { col: 'spike_range_high',label: 'Spike H' },
      { col: 'spike_range_low', label: 'Spike L' },
    ],
  },
  candle_reversal: {
    name: 'Candlestick Reversal',
    desc: [
      'Разворотные паттерны свечей после трендового движения.',
      '<b>Условие:</b> 3+ баров тренда + ADX &lt; 35',
      '<b>Паттерны:</b> дожи, пин-бар (молот/повешенный), поглощение',
      '<b>Вход:</b>',
      'BUY: Бычий дожи / пин / поглощение',
      'SELL: Медвежий дожи / пин / поглощение',
      '<b>SL:</b> Экстремум свечи + 0.5 × ATR &nbsp; <b>TP:</b> 2 × ATR',
      '<b>Таймфрейм:</b> H1',
    ],
    indicators: [
      { col: 'adx',         label: 'ADX'      },
      { col: 'atr',         label: 'ATR'      },
      { col: 'doji',        label: 'Дожи'     },
      { col: 'pin_bull',    label: 'PinBull'  },
      { col: 'pin_bear',    label: 'PinBear'  },
      { col: 'engulf_bull', label: 'EngBull'  },
    ],
  },
  sar_adx: {
    name: 'Parabolic SAR + ADX',
    desc: [
      'Разворот Parabolic SAR с фильтром силы тренда ADX(14).',
      '<b>Вход:</b>',
      'BUY: SAR переключился под цену + ADX &gt; 25 + +DI &gt; −DI',
      'SELL: SAR переключился над ценой + ADX &gt; 25 + −DI &gt; +DI',
      '<b>SL:</b> 1.5 × ATR &nbsp; <b>TP:</b> 2.5 × ATR',
      '<b>Выход:</b> обратное переключение SAR',
      '<b>Таймфрейм:</b> H1',
    ],
    indicators: [
      { col: 'sar',      label: 'SAR'     },
      { col: 'adx',      label: 'ADX(14)' },
      { col: 'plus_di',  label: '+DI'     },
      { col: 'minus_di', label: '−DI'     },
      { col: 'atr',      label: 'ATR'     },
    ],
  },
  donchian_breakout: {
    name: 'Donchian Breakout',
    desc: [
      'Пробой канала Дончиана (20 баров) с ATR-фильтром волатильности.',
      '<b>Вход:</b>',
      'BUY: Закрытие выше верхней границы канала + ATR &gt; среднего ATR',
      'SELL: Закрытие ниже нижней границы канала + ATR &gt; среднего ATR',
      '<b>SL:</b> 2 × ATR &nbsp; <b>TP:</b> 3 × ATR',
      '<b>Выход:</b> возврат к средней линии канала',
      '<b>Таймфрейм:</b> H1',
    ],
    indicators: [
      { col: 'dc_upper',  label: 'DC Upper' },
      { col: 'dc_lower',  label: 'DC Lower' },
      { col: 'dc_middle', label: 'DC Mid'   },
      { col: 'atr',       label: 'ATR'      },
    ],
  },
  triple_ema: {
    name: 'Triple EMA Momentum',
    desc: [
      'Тройная EMA-выравненность (8/21/50) с подтверждением MACD.',
      '<b>Вход:</b>',
      'BUY: EMA8 &gt; EMA21 &gt; EMA50 + MACD гистограмма растёт',
      'SELL: EMA8 &lt; EMA21 &lt; EMA50 + MACD гистограмма падает',
      '<b>SL:</b> 1.5 × ATR &nbsp; <b>TP:</b> 2 × ATR',
      '<b>Выход:</b> EMA8 пересекает EMA21 или разворот MACD',
      '<b>Таймфрейм:</b> H1',
    ],
    indicators: [
      { col: 'ema8',      label: 'EMA8'      },
      { col: 'ema21',     label: 'EMA21'     },
      { col: 'ema50',     label: 'EMA50'     },
      { col: 'macd_hist', label: 'MACD Hist' },
      { col: 'atr',       label: 'ATR'       },
    ],
  },
};

// ─── State ────────────────────────────────────────────────────────
const state = {
  ws: null,
  connected: false,
  agents: {},
  positions: [],
  indicators: {},   // symbol → {ma, macd, rsi, rsi_value, atr, adx, ema8, ema21, signal}
  account: {},
  history: { today: {}, week: {}, month: {} },
  backtest_result: null,
  bt_strategy: 'default',
  log_lines: [],
  MAX_LOG: 200,
};

// ─── WebSocket ────────────────────────────────────────────────────
function connect() {
  const proto = location.protocol === 'https:' ? 'wss' : 'ws';
  state.ws = new WebSocket(`${proto}://${location.host}/ws`);

  state.ws.onopen = () => {
    state.connected = true;
    setConnStatus(true);
  };

  state.ws.onclose = () => {
    state.connected = false;
    setConnStatus(false);
    setTimeout(connect, 3000);
  };

  state.ws.onerror = () => {
    state.ws.close();
  };

  state.ws.onmessage = (e) => {
    try {
      const msg = JSON.parse(e.data);
      handleMessage(msg);
    } catch {}
  };
}

function sendCmd(cmd) {
  if (state.ws && state.ws.readyState === WebSocket.OPEN) {
    state.ws.send(JSON.stringify(cmd));
  }
}

function setConnStatus(ok) {
  const dot = document.getElementById('conn-dot');
  const txt = document.getElementById('conn-text');
  dot.className = ok ? 'connected' : '';
  txt.textContent = ok ? 'Connected' : 'Disconnected';
}

// ─── Message Handlers ─────────────────────────────────────────────
function handleMessage(msg) {
  const { msg_type, data } = msg;

  if (msg_type === 'ping') return;

  if (msg_type === 'agents_snapshot') {
    (data.agents || []).forEach(a => { state.agents[a.name] = a; });
    renderAgents();
    (data.recent_events || []).reverse().forEach(addLogLine);
    return;
  }

  if (msg_type === 'event_stream') {
    const ev = data;
    addLogLine(ev);
    routeEvent(ev);
    return;
  }
}

function routeEvent(ev) {
  const { type, payload } = ev;

  if (type === 'agent.status') {
    const a = state.agents[payload.agent] || {};
    state.agents[payload.agent] = { ...a, ...payload, name: payload.agent };
    renderAgents();
    return;
  }

  if (type === 'account.update') {
    state.account = payload;
    renderAccount();
    return;
  }

  if (type === 'position.update') {
    state.positions = payload.positions || [];
    renderPositions();
    return;
  }

  if (type === 'indicator.ready' || type === 'signal.generated') {
    const sym = payload.symbol;
    if (!state.indicators[sym]) state.indicators[sym] = {};
    if (type === 'indicator.ready') {
      Object.assign(state.indicators[sym], payload);
    } else {
      state.indicators[sym].signal = payload.signal;
      if (payload.indicators) Object.assign(state.indicators[sym], payload.indicators);
    }
    renderIndicators();
    return;
  }

  if (type === 'history.snapshot') {
    state.history = payload;
    renderHistory();
    return;
  }

  if (type === 'backtest.result') {
    state.backtest_result = payload;
    renderBacktestResult(payload);
    return;
  }
}

// ─── Render: Agents sidebar ───────────────────────────────────────
function renderAgents() {
  const container = document.getElementById('agents-list');
  container.innerHTML = '';
  Object.values(state.agents).forEach(a => {
    const div = document.createElement('div');
    div.className = 'agent-card';
    div.dataset.agent = a.name;
    div.innerHTML = `
      <div class="agent-name">${a.name}</div>
      <div class="agent-status-row">
        <div class="status-dot ${a.status || 'idle'}"></div>
        <div class="agent-detail">${a.detail || a.status || 'idle'}</div>
      </div>
    `;
    container.appendChild(div);
  });
}

// ─── Render: Account bar ──────────────────────────────────────────
function renderAccount() {
  const a = state.account;
  document.getElementById('acc-balance').innerHTML  = `Balance: <b>${fmt(a.balance)} ${a.currency || ''}</b>`;
  document.getElementById('acc-equity').innerHTML   = `Equity: <b>${fmt(a.equity)}</b>`;
  document.getElementById('acc-margin').innerHTML   = `Margin: <b>${fmt(a.margin)}</b>`;
  document.getElementById('acc-free').innerHTML     = `Free: <b>${fmt(a.free_margin)}</b>`;
}

function fmt(v) {
  if (v == null) return '—';
  return Number(v).toLocaleString('ru-RU', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

// ─── Render: Positions ────────────────────────────────────────────
function renderPositions() {
  const container = document.getElementById('positions-list');
  if (!state.positions.length) {
    container.innerHTML = '<div style="color:var(--text-muted);padding:20px">Нет открытых позиций</div>';
    return;
  }
  container.innerHTML = state.positions.map(p => {
    const pnlClass = p.pnl >= 0 ? 'pnl-pos' : 'pnl-neg';
    const sign = p.pnl >= 0 ? '+' : '';
    return `
      <div class="pos-card">
        <div class="pos-symbol">${p.symbol}</div>
        <div>
          <span class="badge badge-${p.type.toLowerCase()}">${p.type}</span>
          <span class="pos-meta" style="margin-left:8px">${p.volume} лот</span>
        </div>
        <div class="pos-meta">Вход: ${p.open_price?.toFixed(5)}</div>
        <div class="pos-meta">SL: ${p.sl?.toFixed(5) || '—'}</div>
        <div class="pos-pnl ${pnlClass}">${sign}${fmt(p.pnl)}$</div>
        <button class="btn-close" onclick="closePosition(${p.ticket},'${p.symbol}')">✕ Закрыть</button>
      </div>
    `;
  }).join('');
}

function closePosition(ticket, symbol) {
  if (!confirm(`Закрыть позицию ${symbol} #${ticket}?`)) return;
  sendCmd({ cmd: 'close_position', ticket, symbol });
}

// ─── Render: Indicators ───────────────────────────────────────────
function renderIndicators() {
  const container = document.getElementById('indicators-grid');
  const entries = Object.entries(state.indicators);
  if (!entries.length) {
    container.innerHTML = '<div style="color:var(--text-muted)">Нет данных</div>';
    return;
  }
  container.innerHTML = entries.map(([sym, d]) => {
    const sig = d.signal || 'NO_SIGNAL';
    const sigClass = sig === 'BUY' ? 'buy' : sig === 'SELL' ? 'sell' : 'none';
    const maB  = badge(d.signal_ma || d.ma);
    const macdB = badge(d.macd_signal || d.macd);
    const rsiB = badge(d.rsi_signal || d.rsi);
    const rsiVal = d.rsi_value != null ? `RSI ${d.rsi_value?.toFixed(1)}` : '';
    return `
      <div class="ind-row">
        <div class="ind-symbol">${sym}</div>
        <div class="ind-badges">
          <span title="MA">${maB}</span>
          <span title="MACD">${macdB}</span>
          <span title="RSI">${rsiB}</span>
          ${rsiVal ? `<span style="color:var(--text-muted);font-size:11px">${rsiVal}</span>` : ''}
        </div>
        <div class="ind-signal"><span class="badge badge-${sigClass}">${sig}</span></div>
      </div>
    `;
  }).join('');
}

function badge(val) {
  if (val === 'BUY')  return `<span class="badge badge-buy">BUY</span>`;
  if (val === 'SELL') return `<span class="badge badge-sell">SELL</span>`;
  return `<span class="badge badge-none">—</span>`;
}

// ─── Render: History ─────────────────────────────────────────────
function renderHistory() {
  const h = state.history;
  const todayP = h.today?.profit ?? 0;
  const weekP  = h.week?.profit ?? 0;
  const monthP = h.month?.profit ?? 0;
  document.getElementById('hist-today').innerHTML = `<div class="stat-label">Сегодня</div><div class="stat-value ${todayP>=0?'pnl-pos':'pnl-neg'}">${todayP>=0?'+':''}${fmt(todayP)}$</div>`;
  document.getElementById('hist-week').innerHTML  = `<div class="stat-label">Неделя</div><div class="stat-value ${weekP>=0?'pnl-pos':'pnl-neg'}">${weekP>=0?'+':''}${fmt(weekP)}$</div>`;
  document.getElementById('hist-month').innerHTML = `<div class="stat-label">Месяц</div><div class="stat-value ${monthP>=0?'pnl-pos':'pnl-neg'}">${monthP>=0?'+':''}${fmt(monthP)}$</div>`;
}

// ─── Render: Event Log ────────────────────────────────────────────
function addLogLine(ev) {
  state.log_lines.unshift(ev);
  if (state.log_lines.length > state.MAX_LOG) state.log_lines.pop();
  renderLog();
}

function renderLog() {
  const container = document.getElementById('event-log');
  const autoScroll = document.getElementById('auto-scroll')?.checked !== false;
  container.innerHTML = state.log_lines.slice(0, 100).map(ev => {
    const t = ev.timestamp ? ev.timestamp.substring(11, 19) : '';
    const payload = JSON.stringify(ev.payload || {}).substring(0, 120);
    return `<div class="log-line">
      <span class="log-time">${t}</span>
      <span class="log-source">${ev.source || ''}</span>
      <span class="log-type">${ev.type || ''}</span>
      <span class="log-payload">${payload}</span>
    </div>`;
  }).join('');
}

// ─── Strategy Description ─────────────────────────────────────────
function renderStrategyDesc(stratKey, containerId) {
  const el = document.getElementById(containerId);
  if (!el) return;
  const meta = STRATEGY_META[stratKey] || STRATEGY_META.default;
  el.innerHTML = `
    <div class="strat-desc-name">${meta.name}</div>
    <div class="strat-desc-body">${meta.desc.join('<br>')}</div>
    ${meta.indicators.length ? `<div class="strat-desc-ind">Индикаторы: ${meta.indicators.map(i => `<span class="strat-ind-tag">${i.label}</span>`).join('')}</div>` : ''}
  `;
}

function onBtStrategyChange() {
  const val = document.getElementById('bt-strategy').value;
  renderStrategyDesc(val, 'bt-strategy-desc');
}

function onActiveStrategyChange() {
  const val = document.getElementById('active-strategy').value;
  renderStrategyDesc(val, 'active-strategy-desc');
}

function setActiveStrategy() {
  const strategy = document.getElementById('active-strategy').value;
  sendCmd({ cmd: 'set_active_strategy', strategy });
  const btn = document.getElementById('btn-set-strategy');
  if (btn) { btn.textContent = '✓ Применено'; setTimeout(() => { btn.textContent = '✓ Применить'; }, 2000); }
}

// ─── Backtest ─────────────────────────────────────────────────────
function toggleBarsVisibility() {
  const start = document.getElementById('bt-start').value;
  const end = document.getElementById('bt-end').value;
  const barsLabel = document.getElementById('bt-bars-label');
  barsLabel.style.display = (start || end) ? 'none' : '';
}

function runBacktest() {
  const strategy  = document.getElementById('bt-strategy').value;
  const symbol    = document.getElementById('bt-symbol').value;
  const timeframe = document.getElementById('bt-timeframe').value;
  const bars      = parseInt(document.getElementById('bt-bars').value);
  const deposit   = parseFloat(document.getElementById('bt-deposit').value);
  const volume    = parseFloat(document.getElementById('bt-volume').value);
  const start     = document.getElementById('bt-start').value || null;
  const end       = document.getElementById('bt-end').value || null;
  sendCmd({ cmd: 'run_backtest', strategy, symbol, timeframe, bars, deposit, spread: 0, volume, start, end });
  document.getElementById('bt-result').innerHTML = '<div style="color:var(--text-muted)">Выполняется...</div>';
}

function renderBacktestResult(payload) {
  state.bt_strategy = payload.strategy || 'default';
  const r = payload.result;
  if (!r || !r.total_trades) {
    document.getElementById('bt-result').innerHTML = '<div style="color:var(--text-muted)">Нет сделок</div>';
    return;
  }
  const wr = (r.win_rate * 100).toFixed(1);
  const ret = (r.return_pct || 0).toFixed(2);
  const dd  = (r.max_drawdown_pct || 0).toFixed(2);
  const pf  = (r.profit_factor || 0).toFixed(2);
  document.getElementById('bt-result').innerHTML = `
    <div class="stats-grid">
      <div class="stat-box"><div class="stat-label">Сделок</div><div class="stat-value">${r.total_trades}</div></div>
      <div class="stat-box"><div class="stat-label">Win Rate</div><div class="stat-value ${parseFloat(wr)>=50?'pnl-pos':'pnl-neg'}">${wr}%</div></div>
      <div class="stat-box"><div class="stat-label">Profit Factor</div><div class="stat-value ${parseFloat(pf)>=1?'pnl-pos':'pnl-neg'}">${pf}</div></div>
      <div class="stat-box"><div class="stat-label">P&L</div><div class="stat-value ${r.total_pnl_points>=0?'pnl-pos':'pnl-neg'}">${r.total_pnl_points>=0?'+':''}${(r.total_pnl_points||0).toFixed(0)} pt</div></div>
      ${payload.deposit > 0 ? `
        <div class="stat-box"><div class="stat-label">Итог</div><div class="stat-value ${r.total_pnl_money>=0?'pnl-pos':'pnl-neg'}">${r.total_pnl_money>=0?'+':''}${fmt(r.total_pnl_money)}$</div></div>
        <div class="stat-box"><div class="stat-label">Доходность</div><div class="stat-value ${parseFloat(ret)>=0?'pnl-pos':'pnl-neg'}">${ret}%</div></div>
        <div class="stat-box"><div class="stat-label">Просадка</div><div class="stat-value pnl-neg">-${dd}%</div></div>
        <div class="stat-box"><div class="stat-label">Баланс</div><div class="stat-value">${fmt(r.final_balance)}$</div></div>
      ` : ''}
    </div>
    ${renderBtTrades(r.trades)}
  `;
  renderBtPage();
}

let btPage = 0;
const BT_PER_PAGE = 20;

function renderBtTrades(trades) {
  if (!trades || !trades.length) return '';
  // Храним в хронологическом порядке для правильной нумерации и баланса
  state.btTrades = trades.slice();
  btPage = 0;
  return `
    <div class="card">
      <div class="card-title">Сделки (${trades.length})</div>
      <div id="bt-trades-table"></div>
      <div id="bt-pagination" class="bt-pagination"></div>
    </div>
  `;
}

function renderBtPage() {
  const trades = state.btTrades;
  if (!trades) return;

  const stratKey  = state.bt_strategy || 'default';
  const indCols   = (STRATEGY_META[stratKey] || STRATEGY_META.default).indicators;

  const totalPages = Math.ceil(trades.length / BT_PER_PAGE);
  const start = btPage * BT_PER_PAGE;
  const page = trades.slice(start, start + BT_PER_PAGE);
  const hasBalance = trades.some(t => t.balance_after != null && t.balance_after !== 0);

  // colspan for summary "Итого:" = 6 fixed cols + indicator cols + P&L pts col
  const summaryColspan = 7 + indCols.length;

  document.getElementById('bt-trades-table').innerHTML = `
    <table>
      <tr>
        <th>#</th><th>Тип</th><th>Вход</th><th>Выход</th><th>Цена входа</th><th>Цена выхода</th>
        ${indCols.map(ic => `<th>${ic.label}</th>`).join('')}
        <th>P&L pts</th><th>P&L $</th>${hasBalance ? '<th>Баланс</th>' : ''}
        <th>Баров</th><th>Выход по</th>
      </tr>
      ${page.map((t, i) => {
        const globalIdx = start + i + 1;
        const pc  = t.pnl_points >= 0 ? 'pnl-pos' : 'pnl-neg';
        const bal = t.balance_after;
        const prevBal = globalIdx > 1 ? (trades[start + i - 1]?.balance_after ?? bal) : bal;
        const balClass = bal != null && bal >= prevBal ? 'pnl-pos' : 'pnl-neg';
        const indCells = indCols.map(ic => {
          const v = t.indicators?.[ic.col];
          const s = v != null ? Number(v).toFixed(2) : '—';
          return `<td style="color:var(--text-muted);font-size:11px">${s}</td>`;
        }).join('');
        return `<tr>
          <td style="color:var(--text-muted)">${globalIdx}</td>
          <td><span class="badge badge-${(t.type||'').toLowerCase()}">${t.type}</span></td>
          <td>${(t.entry_time||'').toString().substring(0,16)}</td>
          <td>${(t.exit_time||'').toString().substring(0,16)}</td>
          <td>${(t.entry_price||0).toFixed(5)}</td>
          <td>${(t.exit_price||0).toFixed(5)}</td>
          ${indCells}
          <td class="${pc}">${t.pnl_points>=0?'+':''}${(t.pnl_points||0).toFixed(1)}</td>
          <td class="${pc}">${t.pnl_money!=null?(t.pnl_money>=0?'+':'')+fmt(t.pnl_money)+'$':'—'}</td>
          ${hasBalance ? `<td class="${balClass}" style="font-weight:600">${bal!=null?fmt(bal)+'$':'—'}</td>` : ''}
          <td style="color:var(--text-muted)">${t.bars_held??'—'}</td>
          <td style="color:var(--text-muted)">${t.exit_reason||''}</td>
        </tr>`;
      }).join('')}
      ${hasBalance && btPage === totalPages - 1 ? (() => {
        const last = trades[trades.length - 1];
        const first = trades[0];
        const finalBal = last?.balance_after;
        const initBal = first?.balance_after != null ? (first.balance_after - (first.pnl_money||0)) : null;
        const totalPnl = finalBal != null && initBal != null ? finalBal - initBal : null;
        const balClass = totalPnl >= 0 ? 'pnl-pos' : 'pnl-neg';
        return `<tr style="border-top:2px solid var(--border);font-weight:600">
          <td colspan="${summaryColspan}" style="text-align:right;color:var(--text-muted)">Итого:</td>
          <td class="${balClass}">${totalPnl!=null?(totalPnl>=0?'+':'')+fmt(totalPnl)+'$':'—'}</td>
          <td class="${balClass}" style="font-weight:700">${finalBal!=null?fmt(finalBal)+'$':'—'}</td>
          <td colspan="2"></td>
        </tr>`;
      })() : ''}
    </table>
  `;

  const pag = document.getElementById('bt-pagination');
  if (totalPages <= 1) { pag.innerHTML = ''; return; }

  let html = `<button onclick="btGoPage(0)" ${btPage===0?'disabled':''}>&#171;</button>`;
  html += `<button onclick="btGoPage(${btPage-1})" ${btPage===0?'disabled':''}>&#8249;</button>`;

  const range = 2;
  let from = Math.max(0, btPage - range);
  let to = Math.min(totalPages - 1, btPage + range);
  if (from > 0) html += `<span class="bt-page-dots">...</span>`;
  for (let i = from; i <= to; i++) {
    html += `<button onclick="btGoPage(${i})" class="${i===btPage?'active':''}">${i+1}</button>`;
  }
  if (to < totalPages - 1) html += `<span class="bt-page-dots">...</span>`;

  html += `<button onclick="btGoPage(${btPage+1})" ${btPage>=totalPages-1?'disabled':''}>&#8250;</button>`;
  html += `<button onclick="btGoPage(${totalPages-1})" ${btPage>=totalPages-1?'disabled':''}>&#187;</button>`;
  pag.innerHTML = html;
}

function btGoPage(p) {
  const totalPages = Math.ceil((state.btTrades||[]).length / BT_PER_PAGE);
  btPage = Math.max(0, Math.min(p, totalPages - 1));
  renderBtPage();
}

// ─── Chart (Lightweight Charts) ───────────────────────────────────
const chartModule = (() => {
  let chart = null;
  let candleSeries = null;
  let volumeSeries = null;
  let currentSymbol = 'XAUUSDrfd';
  let currentTf = 'H1';
  let digits = 5;
  let refreshTimer = null;
  let initialized = false;

  function fmtPrice(v) {
    return v == null ? '—' : Number(v).toFixed(digits);
  }

  function setLegend(c, prevClose) {
    if (!c) return;
    document.getElementById('leg-open').textContent  = fmtPrice(c.open);
    document.getElementById('leg-high').textContent  = fmtPrice(c.high);
    document.getElementById('leg-low').textContent   = fmtPrice(c.low);
    document.getElementById('leg-close').textContent = fmtPrice(c.close);
    const chEl = document.getElementById('leg-change');
    if (prevClose != null) {
      const diff = c.close - prevClose;
      const pct  = (diff / prevClose) * 100;
      const up   = diff >= 0;
      chEl.textContent = `${up ? '+' : ''}${diff.toFixed(digits)} (${up ? '+' : ''}${pct.toFixed(2)}%)`;
      chEl.style.color = up ? 'var(--green)' : 'var(--red)';
      chEl.style.background = up ? 'var(--green-soft)' : 'var(--red-soft)';
    } else {
      chEl.textContent = '—';
      chEl.style.background = 'transparent';
      chEl.style.color = 'var(--text)';
    }
  }

  function init() {
    if (initialized) return;
    if (!window.LightweightCharts) {
      console.warn('LightweightCharts не загружен');
      return;
    }
    const el = document.getElementById('chart-container');
    if (!el) return;

    chart = LightweightCharts.createChart(el, {
      layout: {
        background: { type: 'solid', color: '#17181F' },
        textColor:  '#848E9C',
        fontFamily: "'Inter', system-ui, sans-serif",
        fontSize:   11,
      },
      grid: {
        vertLines: { color: '#2B2F36', style: 1 },
        horzLines: { color: '#2B2F36', style: 1 },
      },
      crosshair: {
        mode: LightweightCharts.CrosshairMode.Normal,
        vertLine: { color: '#5E6673', labelBackgroundColor: '#F7A600' },
        horzLine: { color: '#5E6673', labelBackgroundColor: '#F7A600' },
      },
      rightPriceScale: {
        borderColor: '#2B2F36',
        scaleMargins: { top: 0.08, bottom: 0.25 },
      },
      timeScale: {
        borderColor: '#2B2F36',
        timeVisible: true,
        secondsVisible: false,
      },
      handleScroll: { vertTouchDrag: false },
    });

    candleSeries = chart.addCandlestickSeries({
      upColor:       '#20B26C',
      downColor:     '#EF454A',
      borderUpColor: '#20B26C',
      borderDownColor: '#EF454A',
      wickUpColor:   '#20B26C',
      wickDownColor: '#EF454A',
      priceFormat:   { type: 'price', precision: digits, minMove: Math.pow(10, -digits) },
    });

    volumeSeries = chart.addHistogramSeries({
      priceFormat: { type: 'volume' },
      priceScaleId: '',
      color: 'rgba(132,142,156,0.35)',
    });
    volumeSeries.priceScale().applyOptions({
      scaleMargins: { top: 0.82, bottom: 0 },
    });

    chart.subscribeCrosshairMove(param => {
      if (!param || !param.time || !param.seriesData.size) return;
      const c = param.seriesData.get(candleSeries);
      if (!c) return;
      const all = candleSeries.data();
      const idx = all.findIndex(x => x.time === c.time);
      const prev = idx > 0 ? all[idx - 1].close : null;
      setLegend(c, prev);
    });

    const ro = new ResizeObserver(entries => {
      if (!chart) return;
      for (const e of entries) {
        chart.applyOptions({ width: e.contentRect.width, height: e.contentRect.height });
      }
    });
    ro.observe(el);

    initialized = true;
  }

  async function populateSymbols() {
    const sel = document.getElementById('chart-symbol');
    if (!sel || sel.options.length) return;
    try {
      const r = await fetch('/api/symbols');
      const d = await r.json();
      const symbols = d.symbols || [currentSymbol];
      sel.innerHTML = symbols.map(s =>
        `<option value="${s}" ${s === currentSymbol ? 'selected' : ''}>${s}</option>`
      ).join('');
    } catch {
      sel.innerHTML = `<option value="${currentSymbol}">${currentSymbol}</option>`;
    }
  }

  async function load() {
    if (!initialized) return;
    const url = `/api/candles?symbol=${encodeURIComponent(currentSymbol)}&timeframe=${currentTf}&bars=500`;
    try {
      const r = await fetch(url);
      const d = await r.json();
      if (d.error || !d.candles) {
        console.warn('candles error:', d.error);
        return;
      }
      digits = d.digits ?? 5;
      candleSeries.applyOptions({
        priceFormat: { type: 'price', precision: digits, minMove: Math.pow(10, -digits) },
      });
      const candles = d.candles.map(c => ({
        time: c.time, open: c.open, high: c.high, low: c.low, close: c.close,
      }));
      const volumes = d.candles.map(c => ({
        time: c.time,
        value: c.volume,
        color: c.close >= c.open ? 'rgba(32,178,108,0.35)' : 'rgba(239,69,74,0.35)',
      }));
      candleSeries.setData(candles);
      volumeSeries.setData(volumes);
      if (candles.length) {
        const last = candles[candles.length - 1];
        const prev = candles.length > 1 ? candles[candles.length - 2].close : null;
        setLegend(last, prev);
      }
    } catch (e) {
      console.warn('candles fetch failed:', e);
    }
  }

  function setSymbol(s) {
    currentSymbol = s;
    load();
  }

  function setTimeframe(tf) {
    currentTf = tf;
    document.querySelectorAll('#chart-tf-buttons .tf-btn').forEach(b =>
      b.classList.toggle('active', b.dataset.tf === tf)
    );
    load();
  }

  function startAutoRefresh() {
    stopAutoRefresh();
    refreshTimer = setInterval(() => load(), 15000);
  }
  function stopAutoRefresh() {
    if (refreshTimer) { clearInterval(refreshTimer); refreshTimer = null; }
  }

  async function activate() {
    init();
    await populateSymbols();
    if (!candleSeries?.data().length) await load();
    startAutoRefresh();
  }
  function deactivate() { stopAutoRefresh(); }

  function bind() {
    document.getElementById('chart-symbol')?.addEventListener('change', e => setSymbol(e.target.value));
    document.querySelectorAll('#chart-tf-buttons .tf-btn').forEach(b =>
      b.addEventListener('click', () => setTimeframe(b.dataset.tf))
    );
  }

  return { activate, deactivate, bind };
})();

// ─── Tabs ─────────────────────────────────────────────────────────
function switchTab(name) {
  document.querySelectorAll('.tab').forEach(t => t.classList.toggle('active', t.dataset.tab === name));
  document.querySelectorAll('.content').forEach(c => c.classList.toggle('active', c.id === `tab-${name}`));
  if (name === 'indicators') chartModule.activate();
  else chartModule.deactivate();
}

// ─── Init ─────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  // Tabs
  document.querySelectorAll('.tab').forEach(t => {
    t.addEventListener('click', () => switchTab(t.dataset.tab));
  });

  // Backtest
  document.getElementById('btn-run-bt')?.addEventListener('click', runBacktest);
  document.getElementById('bt-start')?.addEventListener('change', toggleBarsVisibility);
  document.getElementById('bt-end')?.addEventListener('change', toggleBarsVisibility);

  // Strategy descriptions — initial render
  onBtStrategyChange();

  // Chart toolbar bindings
  chartModule.bind();

  // Fetch account periodically
  setInterval(async () => {
    try {
      const r = await fetch('/api/account');
      const d = await r.json();
      if (!d.error) { state.account = d; renderAccount(); }
    } catch {}
  }, 15000);

  // Fetch positions periodically
  setInterval(async () => {
    try {
      const r = await fetch('/api/positions');
      const d = await r.json();
      state.positions = d.positions || [];
      renderPositions();
    } catch {}
  }, 5000);

  // Connect WS
  connect();

  // Initial tab
  switchTab('positions');
});
