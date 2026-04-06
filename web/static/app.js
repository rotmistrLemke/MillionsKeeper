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

// ─── Backtest ─────────────────────────────────────────────────────
function runBacktest() {
  const symbol  = document.getElementById('bt-symbol').value;
  const bars    = parseInt(document.getElementById('bt-bars').value);
  const deposit = parseFloat(document.getElementById('bt-deposit').value);
  const volume  = parseFloat(document.getElementById('bt-volume').value);
  sendCmd({ cmd: 'run_backtest', symbol, bars, deposit, spread: 0, volume });
  document.getElementById('bt-result').innerHTML = '<div style="color:var(--text-muted)">Выполняется...</div>';
}

function renderBacktestResult(payload) {
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
}

function renderBtTrades(trades) {
  if (!trades || !trades.length) return '';
  return `
    <div class="card">
      <div class="card-title">Последние сделки</div>
      <table>
        <tr>
          <th>Тип</th><th>Вход</th><th>Выход</th><th>Цена входа</th><th>Цена выхода</th>
          <th>P&L pts</th><th>P&L $</th><th>Выход по</th>
          <th>EMA8</th><th>EMA21</th><th>MACD</th><th>RSI</th><th>ATR</th>
        </tr>
        ${trades.slice(-30).reverse().map(t => {
          const pc = t.pnl_points >= 0 ? 'pnl-pos' : 'pnl-neg';
          const ind = t.indicators || {};
          return `<tr>
            <td><span class="badge badge-${(t.type||'').toLowerCase()}">${t.type}</span></td>
            <td>${(t.entry_time||'').toString().substring(0,16)}</td>
            <td>${(t.exit_time||'').toString().substring(0,16)}</td>
            <td>${(t.entry_price||0).toFixed(5)}</td>
            <td>${(t.exit_price||0).toFixed(5)}</td>
            <td class="${pc}">${t.pnl_points>=0?'+':''}${(t.pnl_points||0).toFixed(1)}</td>
            <td class="${pc}">${t.pnl_money!=null?(t.pnl_money>=0?'+':'')+fmt(t.pnl_money)+'$':'—'}</td>
            <td style="color:var(--text-muted)">${t.exit_reason||''}</td>
            <td style="color:var(--text-muted)">${ind.ema8!=null?ind.ema8.toFixed(5):'—'}</td>
            <td style="color:var(--text-muted)">${ind.ema21!=null?ind.ema21.toFixed(5):'—'}</td>
            <td style="color:var(--text-muted)">${ind.macd_line!=null?ind.macd_line.toFixed(5):'—'}</td>
            <td style="color:var(--text-muted)">${ind.rsi!=null?ind.rsi.toFixed(1):'—'}</td>
            <td style="color:var(--text-muted)">${ind.atr!=null?ind.atr.toFixed(5):'—'}</td>
          </tr>`;
        }).join('')}
      </table>
    </div>
  `;
}

// ─── Tabs ─────────────────────────────────────────────────────────
function switchTab(name) {
  document.querySelectorAll('.tab').forEach(t => t.classList.toggle('active', t.dataset.tab === name));
  document.querySelectorAll('.content').forEach(c => c.classList.toggle('active', c.id === `tab-${name}`));
}

// ─── Init ─────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  // Tabs
  document.querySelectorAll('.tab').forEach(t => {
    t.addEventListener('click', () => switchTab(t.dataset.tab));
  });

  // Backtest button
  document.getElementById('btn-run-bt')?.addEventListener('click', runBacktest);

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
