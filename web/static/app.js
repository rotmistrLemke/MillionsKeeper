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
  sr_bounce: {
    name: 'S/R Bounce',
    desc: [
      'Отскок от уровней поддержки/сопротивления по подтверждённым свинг-пивотам.',
      '<b>Уровни:</b> swing high/low в окне ±5 баров',
      '<b>Вход:</b>',
      'BUY: Касание поддержки (в пределах 0.3×ATR) + бычье закрытие',
      'SELL: Касание сопротивления (в пределах 0.3×ATR) + медвежье закрытие',
      '<b>SL:</b> за уровнем (1×ATR) &nbsp; <b>TP:</b> противоположный уровень (мин. 1.5×ATR)',
      '<b>Выход:</b> закрытие по другую сторону уровня (пробой)',
      '<b>Таймфрейм:</b> любой',
    ],
    indicators: [
      { col: 'support',    label: 'Support' },
      { col: 'resistance', label: 'Resist'  },
      { col: 'atr',        label: 'ATR'     },
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
  macd_hist: {
    name: 'MACD Histogram',
    desc: [
      'Вход и выход по знаку гистограммы MACD(12, 26, 9).',
      '<b>Вход:</b>',
      'BUY: MACD_hist &gt; 0',
      'SELL: MACD_hist &lt; 0',
      '<b>Выход (переворот):</b>',
      'BUY закрывается при MACD_hist &lt; 0',
      'SELL закрывается при MACD_hist &gt; 0',
      '<b>SL:</b> 0.5 × ATR &nbsp; <b>TP:</b> 1 × ATR',
      '<b>Таймфрейм:</b> любой (по выбору в бэктесте)',
    ],
    indicators: [
      { col: 'macd_line',   label: 'MACD'   },
      { col: 'macd_signal', label: 'Signal' },
      { col: 'macd_hist',   label: 'Hist'   },
      { col: 'atr',         label: 'ATR'    },
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
    if (typeof chartModule !== 'undefined') chartModule.onWsReconnect();
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

  if (msg_type === 'candle_update') {
    chartModule.onCandleUpdate(data);
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
  if (!container) return;
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
async function populateBtSymbols() {
  const sel = document.getElementById('bt-symbol');
  if (!sel) return;
  const preferred = sel.value || 'XAUUSDrfd';
  try {
    const r = await fetch('/api/symbols');
    const d = await r.json();
    const symbols = d.symbols || [];
    if (!symbols.length) return;
    const has = symbols.includes(preferred);
    sel.innerHTML = symbols.map(s =>
      `<option value="${s}" ${s === preferred ? 'selected' : ''}>${s}</option>`
    ).join('');
    if (!has) sel.value = symbols[0];
  } catch {}
}

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
  let macdChart = null;
  let macdLineSeries = null;
  let macdSignalSeries = null;
  let macdHistSeries = null;
  let syncingRange = false;
  let syncingCrosshair = false;
  const overlaySeries = {}; // col -> lineSeries
  let currentSymbol = 'XAUUSDrfd';
  let currentTf = 'H1';
  let currentStrategy = 'default';
  let digits = 5;
  let indicatorTimer = null;
  let lastCandleTime = 0;
  let initialized = false;
  let active = false;

  const OVERLAY_STYLE = {
    ema8:    { color: '#F7A600', lineWidth: 2, title: 'EMA 8' },
    ema21:   { color: '#4A90E2', lineWidth: 2, title: 'EMA 21' },
    ema50:   { color: '#A37CF0', lineWidth: 2, title: 'EMA 50' },
    ema200:  { color: '#EB7531', lineWidth: 2, title: 'EMA 200' },
    sar:     { color: '#848E9C', lineWidth: 1, lineStyle: 2, title: 'SAR' },
    dc_upper:  { color: '#20B26C', lineWidth: 1, lineStyle: 2, title: 'DC Upper' },
    dc_lower:  { color: '#EF454A', lineWidth: 1, lineStyle: 2, title: 'DC Lower' },
    dc_middle: { color: '#4A90E2', lineWidth: 1, lineStyle: 3, title: 'DC Mid' },
    support:    { color: '#20B26C', lineWidth: 2, lineStyle: 2, title: 'Support' },
    resistance: { color: '#EF454A', lineWidth: 2, lineStyle: 2, title: 'Resistance' },
    fib_382_bull: { color: '#A37CF0', lineWidth: 1, lineStyle: 3, title: 'Fib 38.2%' },
    fib_500_bull: { color: '#A37CF0', lineWidth: 1, lineStyle: 2, title: 'Fib 50%' },
    imp_high: { color: '#848E9C', lineWidth: 1, lineStyle: 3, title: 'Imp High' },
    imp_low:  { color: '#848E9C', lineWidth: 1, lineStyle: 3, title: 'Imp Low' },
  };

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
        minimumWidth: 72,
      },
      timeScale: {
        borderColor: '#2B2F36',
        timeVisible: true,
        secondsVisible: false,
        rightOffset: 8,
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
      // Mirror crosshair to MACD pane
      if (macdChart && !syncingCrosshair) {
        syncingCrosshair = true;
        try {
          if (param && param.time && macdLineSeries) {
            const md = param.seriesData.get(macdLineSeries);
            const price = (md && md.value != null)
              ? md.value
              : (macdLineSeries.dataByIndex && macdLineSeries.data()[0]?.value) || 0;
            macdChart.setCrosshairPosition(price, param.time, macdLineSeries);
          } else {
            macdChart.clearCrosshairPosition();
          }
        } finally { syncingCrosshair = false; }
      }
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
        lastCandleTime = last.time;
        setLegend(last, prev);
      }
      scheduleSync();
    } catch (e) {
      console.warn('candles fetch failed:', e);
    }
  }

  /** Обработка live-обновления свечи из WS. */
  function onCandleUpdate(msg) {
    if (!initialized || !candleSeries) return;
    if (!msg || msg.symbol !== currentSymbol || msg.timeframe !== currentTf) return;
    const c = msg.candle;
    if (!c) return;
    // Если пришла новая свеча — фиксируем прошлую и добавим (lightweight-charts делает это сам через update с большим временем)
    try {
      candleSeries.update({
        time: c.time, open: c.open, high: c.high, low: c.low, close: c.close,
      });
      volumeSeries.update({
        time: c.time,
        value: c.volume,
        color: c.close >= c.open ? 'rgba(32,178,108,0.35)' : 'rgba(239,69,74,0.35)',
      });
      // Пересчитываем легенду: prev.close — либо предыдущий бар из series, либо open текущего
      const prevClose = c.time > lastCandleTime ? null
        : (candleSeries.dataByIndex && candleSeries.data().length > 1
            ? candleSeries.data()[candleSeries.data().length - 2].close
            : c.open);
      setLegend(c, prevClose ?? c.open);
      lastCandleTime = c.time;
    } catch (e) {
      console.warn('candle update failed:', e);
    }
  }

  // ── WS subscription ──────────────────────────────────────────
  function subscribeWS() {
    sendCmd({ cmd: 'chart_subscribe', symbol: currentSymbol, timeframe: currentTf });
  }
  function unsubscribeWS() {
    sendCmd({ cmd: 'chart_unsubscribe' });
  }

  // ── Indicators strip ─────────────────────────────────────────
  function fmtIndVal(v, col) {
    if (v == null) return '—';
    if (typeof v === 'boolean') return v ? '✓' : '—';
    if (typeof v !== 'number') return String(v);
    if (col && (col.toLowerCase().includes('rsi') || col.toLowerCase() === 'cci' || col.toLowerCase().includes('adx'))) {
      return v.toFixed(2);
    }
    if (Math.abs(v) >= 100) return v.toFixed(2);
    if (Math.abs(v) >= 1) return v.toFixed(Math.min(digits, 5));
    return v.toFixed(digits);
  }

  function labelFor(col) {
    // Используем STRATEGY_META для человекочитаемых подписей, иначе col.
    const meta = (typeof STRATEGY_META !== 'undefined') ? STRATEGY_META[currentStrategy] : null;
    if (meta && Array.isArray(meta.indicators)) {
      const hit = meta.indicators.find(i => i.col === col);
      if (hit) return hit.label;
    }
    return col.replace(/_/g, ' ').toUpperCase();
  }

  function classifyValue(col, v) {
    if (v == null) return 'muted';
    const c = col.toLowerCase();
    if (c === 'rsi') {
      if (v >= 70) return 'pnl-neg';
      if (v <= 30) return 'pnl-pos';
    }
    if (c.startsWith('macd') || c === 'cci') {
      if (v > 0) return 'pnl-pos';
      if (v < 0) return 'pnl-neg';
    }
    return '';
  }

  // ── Indicator visualization helpers ──────────────────────────
  function sparklinePath(series) {
    const clean = series.map(v => (typeof v === 'number' && isFinite(v)) ? v : null);
    const valid = clean.filter(v => v !== null);
    if (valid.length < 2) return null;
    const min = Math.min(...valid);
    const max = Math.max(...valid);
    const range = (max - min) || 1;
    const W = 120, H = 30;
    const pts = [];
    clean.forEach((v, i) => {
      if (v === null) return;
      const x = (i / (clean.length - 1)) * W;
      const y = H - ((v - min) / range) * (H - 2) - 1;
      pts.push(`${x.toFixed(1)},${y.toFixed(1)}`);
    });
    return { pts: pts.join(' '), W, H, first: valid[0], last: valid[valid.length - 1] };
  }

  function svgSparkline(series) {
    const p = sparklinePath(series);
    if (!p) return '';
    const trend = p.last > p.first ? 'up' : p.last < p.first ? 'down' : 'neut';
    return `<svg class="ind-spark" viewBox="0 0 ${p.W} ${p.H}" preserveAspectRatio="none">
      <polyline class="spark-line ${trend}" points="${p.pts}"/>
    </svg>`;
  }

  function svgZeroHist(series) {
    const vals = (series || []).map(v => (typeof v === 'number' && isFinite(v)) ? v : 0);
    if (!vals.length) return '';
    const maxAbs = Math.max(...vals.map(Math.abs), 1e-9);
    const W = 120, H = 30, mid = H / 2;
    const bw = W / vals.length;
    const rects = vals.map((v, i) => {
      const x = i * bw;
      const barH = (Math.abs(v) / maxAbs) * (H / 2 - 1);
      const y = v >= 0 ? mid - barH : mid;
      const fill = v >= 0 ? 'var(--green)' : 'var(--red)';
      return `<rect x="${x.toFixed(1)}" y="${y.toFixed(1)}" width="${(bw - 0.5).toFixed(1)}" height="${barH.toFixed(1)}" fill="${fill}"/>`;
    }).join('');
    return `<svg class="ind-spark" viewBox="0 0 ${W} ${H}" preserveAspectRatio="none">
      <line x1="0" y1="${mid}" x2="${W}" y2="${mid}" stroke="var(--border-strong)" stroke-width="0.5"/>
      ${rects}
    </svg>`;
  }

  function gaugeLinear(value, { min = 0, max = 100, lo, hi, colors = ['green', 'surface3', 'red'] }) {
    if (value == null || !isFinite(value)) return '';
    const pct = Math.max(0, Math.min(100, ((value - min) / (max - min)) * 100));
    const loPct = ((lo - min) / (max - min)) * 100;
    const hiPct = ((hi - min) / (max - min)) * 100;
    const c0 = `var(--${colors[0]}-soft)`;
    const c1 = colors[1] === 'surface3' ? 'var(--surface3)' : `var(--${colors[1]}-soft)`;
    const c2 = `var(--${colors[2]}-soft)`;
    const bg = `linear-gradient(90deg, ${c0} 0%, ${c0} ${loPct}%, ${c1} ${loPct}%, ${c1} ${hiPct}%, ${c2} ${hiPct}%, ${c2} 100%)`;
    return `
      <div class="ind-gauge" style="background:${bg}">
        <div class="gauge-marker" style="left:${pct}%"></div>
      </div>
      <div class="gauge-labels"><span>${min}</span><span>${lo}</span><span>${hi}</span><span>${max}</span></div>`;
  }

  function gaugeCentered(value, { range = 200, zone = 100 }) {
    if (value == null || !isFinite(value)) return '';
    const clamped = Math.max(-range, Math.min(range, value));
    const pct = ((clamped + range) / (2 * range)) * 100;
    const z1 = ((range - zone) / (2 * range)) * 100;
    const z2 = ((range + zone) / (2 * range)) * 100;
    const bg = `linear-gradient(90deg,
      var(--green-soft) 0%, var(--green-soft) ${z1}%,
      var(--surface3) ${z1}%, var(--surface3) ${z2}%,
      var(--red-soft) ${z2}%, var(--red-soft) 100%)`;
    return `
      <div class="ind-gauge" style="background:${bg}">
        <div class="gauge-marker" style="left:${pct}%"></div>
      </div>
      <div class="gauge-labels"><span>-${range}</span><span>-${zone}</span><span>0</span><span>+${zone}</span><span>+${range}</span></div>`;
  }

  function priceRel(value, price) {
    if (value == null || price == null || !price) {
      return `<div class="ind-price-rel"><span class="muted">—</span></div>`;
    }
    const pct = ((price - value) / value) * 100;
    const above = pct >= 0;
    return `
      <div class="ind-price-rel">
        <span class="ind-arrow ${above ? 'up' : 'down'}"></span>
        <span class="${above ? 'pnl-pos' : 'pnl-neg'}">${above ? '+' : ''}${pct.toFixed(2)}%</span>
        <span class="muted">price ${above ? 'above' : 'below'}</span>
      </div>`;
  }

  function classifyCol(col) {
    const c = col.toLowerCase();
    if (['doji','pin_bull','pin_bear','engulf_bull','engulf_bear'].includes(c)) return 'bool';
    if (c === 'rsi') return 'rsi';
    if (c === 'adx' || c === 'flat_adx') return 'adx';
    if (c === 'plus_di' || c === 'minus_di') return 'di';
    if (c === 'cci') return 'cci';
    if (c.startsWith('macd')) return 'macd';
    if (c.startsWith('ema') || c === 'sar') return 'ema';
    if (c.startsWith('dc_') || c.startsWith('fib_') || c.startsWith('imp_') ||
        c === 'support' || c === 'resistance') return 'price_rel';
    return 'plain';
  }

  function subTag(col, value) {
    if (value == null) return '';
    const c = col.toLowerCase();
    if (c === 'rsi') {
      if (value >= 70) return '<span class="tag tag-bear">overbought</span>';
      if (value <= 30) return '<span class="tag tag-bull">oversold</span>';
      return '<span class="tag tag-neut">neutral</span>';
    }
    if (c === 'adx' || c === 'flat_adx') {
      if (value < 20) return '<span class="tag tag-neut">weak</span>';
      if (value < 40) return '<span class="tag tag-warn">moderate</span>';
      return '<span class="tag tag-bull">strong</span>';
    }
    if (c === 'cci') {
      if (value >= 100)  return '<span class="tag tag-bear">overbought</span>';
      if (value <= -100) return '<span class="tag tag-bull">oversold</span>';
      return '<span class="tag tag-neut">range</span>';
    }
    if (c.startsWith('macd')) {
      return value >= 0
        ? '<span class="tag tag-bull">bullish</span>'
        : '<span class="tag tag-bear">bearish</span>';
    }
    return '';
  }

  function renderCell(col, data) {
    const label = labelFor(col);
    const value = data.values?.[col];
    const series = data.series?.[col] || [];
    const price = data.price;
    const kind = classifyCol(col);
    const fmtVal = fmtIndVal(value, col);
    const tag = subTag(col, value);

    if (kind === 'bool') {
      const on = value != null && value > 0.5;
      const isBear = col.includes('bear');
      const cls = !on ? 'off' : (isBear ? 'on-bear' : 'on-bull');
      const icon = on ? '✓' : '—';
      const txt = on ? (isBear ? 'bearish' : 'bullish') : 'нет';
      return `
        <div class="ind-cell">
          <div class="ind-cell-head"><span class="ind-cell-label">${label}</span></div>
          <div class="ind-bool">
            <div class="bool-dot ${cls}">${icon}</div>
            <span class="ind-cell-value">${txt}</span>
          </div>
        </div>`;
    }

    if (kind === 'rsi') {
      const viz = gaugeLinear(value, { min: 0, max: 100, lo: 30, hi: 70, colors: ['green','surface3','red'] });
      return `
        <div class="ind-cell">
          <div class="ind-cell-head">
            <span class="ind-cell-label">${label}</span>
            <span class="ind-cell-value">${fmtVal}</span>
          </div>
          ${viz}
          <div class="ind-cell-sub">${tag}<span>${svgSparkline(series) ? '' : ''}</span></div>
        </div>`;
    }

    if (kind === 'adx' || kind === 'di') {
      const viz = gaugeLinear(value, { min: 0, max: 100, lo: 20, hi: 40, colors: ['surface3','accent','green'] });
      return `
        <div class="ind-cell">
          <div class="ind-cell-head">
            <span class="ind-cell-label">${label}</span>
            <span class="ind-cell-value">${fmtVal}</span>
          </div>
          ${viz}
          <div class="ind-cell-sub">${tag}</div>
        </div>`;
    }

    if (kind === 'cci') {
      const viz = gaugeCentered(value, { range: 200, zone: 100 });
      return `
        <div class="ind-cell">
          <div class="ind-cell-head">
            <span class="ind-cell-label">${label}</span>
            <span class="ind-cell-value">${fmtVal}</span>
          </div>
          ${viz}
          <div class="ind-cell-sub">${tag}</div>
        </div>`;
    }

    if (kind === 'macd') {
      const viz = svgZeroHist(series);
      return `
        <div class="ind-cell">
          <div class="ind-cell-head">
            <span class="ind-cell-label">${label}</span>
            <span class="ind-cell-value ${value > 0 ? 'pnl-pos' : value < 0 ? 'pnl-neg' : 'muted'}">${fmtVal}</span>
          </div>
          ${viz}
          <div class="ind-cell-sub">${tag}</div>
        </div>`;
    }

    if (kind === 'ema' || kind === 'price_rel') {
      return `
        <div class="ind-cell">
          <div class="ind-cell-head">
            <span class="ind-cell-label">${label}</span>
            <span class="ind-cell-value">${fmtVal}</span>
          </div>
          ${priceRel(value, price)}
          ${svgSparkline(series)}
        </div>`;
    }

    // plain (atr, range_size, flat_bb_width и т.п.)
    return `
      <div class="ind-cell">
        <div class="ind-cell-head">
          <span class="ind-cell-label">${label}</span>
          <span class="ind-cell-value">${fmtVal}</span>
        </div>
        ${svgSparkline(series)}
        <div class="ind-cell-sub">${tag}</div>
      </div>`;
  }

  function renderIndicatorStrip(d) {
    const body = document.getElementById('ind-strip-body');
    const sigEl = document.getElementById('ind-strip-signal');
    const flatEl = document.getElementById('ind-strip-flat');
    const tsEl = document.getElementById('ind-strip-ts');
    const titleEl = document.getElementById('ind-strip-title');
    if (!body) return;

    const priceTxt = d.price != null ? ` · ${d.price.toFixed(digits)}` : '';
    titleEl.textContent = `${d.symbol} · ${d.timeframe}${priceTxt}`;

    if (d.error) {
      body.innerHTML = `<div style="color:var(--red);font-size:12px;padding:12px">Ошибка: ${d.error}</div>`;
      sigEl.textContent = '';
      sigEl.className = 'ind-strip-signal';
      flatEl.classList.remove('active');
      return;
    }

    const sig = d.signal || 'NO_SIGNAL';
    const sigCls = sig === 'BUY' ? 'buy' : sig === 'SELL' ? 'sell' : 'none';
    sigEl.textContent = sig;
    sigEl.className = `ind-strip-signal ${sigCls}`;

    if (d.is_flat === true) {
      flatEl.textContent = 'FLAT · не торгуем';
      flatEl.classList.add('active');
    } else {
      flatEl.classList.remove('active');
    }

    tsEl.textContent = d.time ? new Date(d.time * 1000).toLocaleTimeString('ru-RU') : '';

    const inds = d.indicators || [];
    if (!inds.length) {
      body.innerHTML = `<div style="padding:12px;color:var(--text-dim);font-size:12px">Нет индикаторов для стратегии</div>`;
      return;
    }
    body.innerHTML = inds.map(i => renderCell(i.col, d)).join('');
  }

  // ── Pane width synchronisation ───────────────────────────────
  function syncPaneWidths() {
    if (!chart || !macdChart) return;
    try {
      const w1 = chart.priceScale('right').width();
      const w2 = macdChart.priceScale('right').width();
      const w  = Math.max(w1, w2);
      if (!w) return;
      chart.applyOptions({ rightPriceScale: { minimumWidth: w } });
      macdChart.applyOptions({ rightPriceScale: { minimumWidth: w } });
    } catch {}
  }
  function scheduleSync() {
    requestAnimationFrame(() => requestAnimationFrame(syncPaneWidths));
  }

  function syncTimeRange() {
    if (!chart || !macdChart) return;
    try {
      const range = chart.timeScale().getVisibleLogicalRange();
      if (range) macdChart.timeScale().setVisibleLogicalRange(range);
    } catch {}
  }

  // ── Overlay indicators on main chart ─────────────────────────
  function clearOverlays(keepCols = new Set()) {
    Object.keys(overlaySeries).forEach(col => {
      if (!keepCols.has(col)) {
        try { chart.removeSeries(overlaySeries[col]); } catch {}
        delete overlaySeries[col];
      }
    });
  }

  function applyOverlay(col, times, values) {
    const style = OVERLAY_STYLE[col] || { color: '#848E9C', lineWidth: 1, title: col };
    if (!overlaySeries[col]) {
      overlaySeries[col] = chart.addLineSeries({
        color: style.color,
        lineWidth: style.lineWidth,
        lineStyle: style.lineStyle || 0,
        title: style.title,
        priceLineVisible: false,
        lastValueVisible: true,
        crosshairMarkerVisible: false,
      });
    }
    const data = [];
    for (let i = 0; i < times.length; i++) {
      const v = values[i];
      if (v == null || !isFinite(v)) continue;
      data.push({ time: times[i], value: v });
    }
    overlaySeries[col].setData(data);
  }

  // ── MACD sub-chart ───────────────────────────────────────────
  function ensureMacdChart() {
    if (macdChart) return;
    const el = document.getElementById('macd-container');
    if (!el || !window.LightweightCharts) return;

    macdChart = LightweightCharts.createChart(el, {
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
        scaleMargins: { top: 0.15, bottom: 0.15 },
        minimumWidth: 72,
      },
      timeScale: {
        borderColor: '#2B2F36',
        timeVisible: true,
        secondsVisible: false,
        rightOffset: 8,
      },
      handleScroll: { vertTouchDrag: false },
    });

    macdHistSeries = macdChart.addHistogramSeries({
      priceFormat: { type: 'price', precision: 5, minMove: 0.00001 },
      priceLineVisible: false,
      lastValueVisible: false,
      base: 0,
    });
    macdLineSeries = macdChart.addLineSeries({
      color: '#4A90E2',
      lineWidth: 2,
      priceLineVisible: false,
      lastValueVisible: false,
      crosshairMarkerVisible: true,
      title: 'MACD',
    });
    macdSignalSeries = macdChart.addLineSeries({
      color: '#F7A600',
      lineWidth: 2,
      priceLineVisible: false,
      lastValueVisible: false,
      crosshairMarkerVisible: true,
      title: 'Signal',
    });

    // Mirror crosshair from MACD pane back to the main chart
    macdChart.subscribeCrosshairMove(param => {
      if (syncingCrosshair || !chart || !candleSeries) return;
      syncingCrosshair = true;
      try {
        if (param && param.time) {
          const c = param.seriesData.get(candleSeries);
          const all = candleSeries.data();
          const price = (c && c.close != null)
            ? c.close
            : (all[all.length - 1]?.close ?? 0);
          chart.setCrosshairPosition(price, param.time, candleSeries);
        } else {
          chart.clearCrosshairPosition();
        }
      } finally { syncingCrosshair = false; }
    });

    // Sync time scales bidirectionally
    chart.timeScale().subscribeVisibleLogicalRangeChange(range => {
      if (syncingRange || !macdChart || range == null) return;
      syncingRange = true;
      try { macdChart.timeScale().setVisibleLogicalRange(range); } finally { syncingRange = false; }
    });
    macdChart.timeScale().subscribeVisibleLogicalRangeChange(range => {
      if (syncingRange || range == null) return;
      syncingRange = true;
      try { chart.timeScale().setVisibleLogicalRange(range); } finally { syncingRange = false; }
    });

    const ro = new ResizeObserver(entries => {
      if (!macdChart) return;
      for (const e of entries) {
        macdChart.applyOptions({ width: e.contentRect.width, height: e.contentRect.height });
      }
    });
    ro.observe(el);
  }

  function showMacdPane(show) {
    const wrap = document.getElementById('macd-wrap');
    const mainEl = document.getElementById('chart-container');
    if (!wrap || !mainEl) return;
    if (show) {
      wrap.style.display = '';
      mainEl.classList.add('has-sub');
      ensureMacdChart();
    } else {
      wrap.style.display = 'none';
      mainEl.classList.remove('has-sub');
    }
  }

  function macdHistColor(hist, prev) {
    if (hist == null) return 'rgba(132,142,156,0.35)';
    if (hist >= 0) {
      return (prev == null || hist >= prev) ? '#20B26C' : 'rgba(32,178,108,0.45)';
    }
    return (prev == null || hist <= prev) ? '#EF454A' : 'rgba(239,69,74,0.45)';
  }

  function applyMacd(times, line, signal, hist) {
    if (!macdChart) return;
    const lineData = [], signalData = [], histData = [];
    let prev = null;
    for (let i = 0; i < times.length; i++) {
      const t = times[i];
      const vl = line?.[i], vs = signal?.[i], vh = hist?.[i];
      // Push whitespace points for null/NaN so logical indices stay aligned with the main chart
      lineData.push(vl != null && isFinite(vl) ? { time: t, value: vl } : { time: t });
      signalData.push(vs != null && isFinite(vs) ? { time: t, value: vs } : { time: t });
      if (vh != null && isFinite(vh)) {
        histData.push({ time: t, value: vh, color: macdHistColor(vh, prev) });
        prev = vh;
      } else {
        histData.push({ time: t });
        prev = null;
      }
    }
    macdHistSeries.setData(histData);
    macdLineSeries.setData(lineData);
    macdSignalSeries.setData(signalData);

    // Align time range and price-scale widths with main chart
    syncTimeRange();
    scheduleSync();

    // Header values (last point with a real value — skip whitespace tail)
    const last = (arr) => {
      for (let i = arr.length - 1; i >= 0; i--) {
        const v = arr[i].value;
        if (v != null && isFinite(v)) return v;
      }
      return null;
    };
    const fmt = v => v == null ? '—' : v.toFixed(Math.max(4, digits));
    document.getElementById('macd-val-line').textContent   = fmt(last(lineData));
    document.getElementById('macd-val-signal').textContent = fmt(last(signalData));
    const h = last(histData);
    const histEl = document.getElementById('macd-val-hist');
    histEl.textContent = fmt(h);
    histEl.style.color = h == null ? 'var(--text)' : (h >= 0 ? 'var(--green)' : 'var(--red)');
  }

  function applyChartIndicators(d) {
    if (!chart || !d || !d.series || !d.time_series) return;
    const cols = (d.indicators || []).map(i => i.col);
    const times = d.time_series;

    // Overlays: keep only those present in current strategy
    const overlayCols = new Set(cols.filter(c => OVERLAY_STYLE[c]));
    clearOverlays(overlayCols);
    overlayCols.forEach(col => {
      const series = d.series[col];
      if (series && series.length === times.length) applyOverlay(col, times, series);
    });

    // MACD pane: visible only if strategy has macd cols
    const hasMacd = cols.some(c => c.startsWith('macd'));
    showMacdPane(hasMacd);
    if (hasMacd) {
      applyMacd(
        times,
        d.series['macd_line'],
        d.series['macd_signal'],
        d.series['macd_hist'],
      );
    }
  }

  async function loadIndicators() {
    const url = `/api/indicators?symbol=${encodeURIComponent(currentSymbol)}&timeframe=${currentTf}&strategy=${encodeURIComponent(currentStrategy)}&bars=500`;
    try {
      const r = await fetch(url);
      const d = await r.json();
      renderIndicatorStrip(d);
      applyChartIndicators(d);
    } catch (e) {
      console.warn('indicators fetch failed:', e);
    }
  }

  function startIndicatorRefresh() {
    stopIndicatorRefresh();
    indicatorTimer = setInterval(loadIndicators, 3000);
  }
  function stopIndicatorRefresh() {
    if (indicatorTimer) { clearInterval(indicatorTimer); indicatorTimer = null; }
  }

  // ── Symbol/TF/Strategy changes ───────────────────────────────
  function setSymbol(s) {
    currentSymbol = s;
    lastCandleTime = 0;
    clearOverlays();
    showMacdPane(false);
    load();
    if (active) { subscribeWS(); loadIndicators(); }
  }
  function setTimeframe(tf) {
    currentTf = tf;
    document.querySelectorAll('#chart-tf-buttons .tf-btn').forEach(b =>
      b.classList.toggle('active', b.dataset.tf === tf)
    );
    lastCandleTime = 0;
    clearOverlays();
    showMacdPane(false);
    load();
    if (active) { subscribeWS(); loadIndicators(); }
  }
  function setStrategy(s) {
    currentStrategy = s;
    clearOverlays();
    showMacdPane(false);
    if (active) loadIndicators();
  }

  async function activate() {
    init();
    await populateSymbols();
    if (!candleSeries?.data().length) await load();
    active = true;
    subscribeWS();
    loadIndicators();
    startIndicatorRefresh();
  }
  function deactivate() {
    active = false;
    unsubscribeWS();
    stopIndicatorRefresh();
  }

  /** Вызывается из ws.onopen — восстановить подписку при реконнекте. */
  function onWsReconnect() {
    if (active) {
      subscribeWS();
      loadIndicators();
    }
  }

  function bind() {
    document.getElementById('chart-symbol')?.addEventListener('change', e => setSymbol(e.target.value));
    document.getElementById('chart-strategy')?.addEventListener('change', e => setStrategy(e.target.value));
    document.querySelectorAll('#chart-tf-buttons .tf-btn').forEach(b =>
      b.addEventListener('click', () => setTimeframe(b.dataset.tf))
    );
  }

  return { activate, deactivate, bind, onCandleUpdate, onWsReconnect };
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
  populateBtSymbols();

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
