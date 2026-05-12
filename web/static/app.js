// ─── Auth: bootstrap ──────────────────────────────────────────────
// Если токена нет — сразу уходим на /login. Иначе оставляем его в
// памяти для заголовка Authorization и WS-auth.
const AUTH_TOKEN = localStorage.getItem('th_token');
let AUTH_USER = null;
try { AUTH_USER = JSON.parse(localStorage.getItem('th_user') || 'null'); } catch {}

if (!AUTH_TOKEN) {
  window.location.replace('/login');
}

function isAdmin() {
  return AUTH_USER && AUTH_USER.role === 'admin';
}

function logout() {
  localStorage.removeItem('th_token');
  localStorage.removeItem('th_user');
  window.location.replace('/login');
}

// Обёртка fetch — автоматически добавляет Authorization и
// редиректит на /login при 401.
const _rawFetch = window.fetch.bind(window);
window.fetch = async function(input, init) {
  init = init || {};
  init.headers = new Headers(init.headers || {});
  if (AUTH_TOKEN && !init.headers.has('Authorization')) {
    init.headers.set('Authorization', 'Bearer ' + AUTH_TOKEN);
  }
  const res = await _rawFetch(input, init);
  if (res.status === 401) {
    logout();
  }
  return res;
};

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
  ema_cross: {
    name: 'EMA 50/200 Cross',
    desc: [
      'Взаимное положение быстрой EMA50 и медленной EMA200. Позиция всегда по направлению быстрой.',
      '<b>Вход</b> (на открытии новой свечи):',
      'BUY: EMA50 выше EMA200',
      'SELL: EMA50 ниже EMA200',
      '<b>Выход:</b>',
      'По SL/TP (задаются множителями ATR в форме — 0 = выкл)',
      'Либо по противоположному сигналу: BUY закрывается при EMA50 < EMA200, SELL — при EMA50 > EMA200',
      '<b>SL по умолчанию:</b> 2 × ATR &nbsp; <b>TP по умолчанию:</b> 3 × ATR',
      '<b>Таймфрейм:</b> любой (EMA200 требует достаточно истории)',
    ],
    indicators: [
      { col: 'ema50',  label: 'EMA50'  },
      { col: 'ema200', label: 'EMA200' },
      { col: 'atr',    label: 'ATR'    },
    ],
  },
  ema_cross_inverse: {
    name: 'EMA 8/21 Cross Inverse',
    desc: [
      'Инверсия EMA Cross — сделки открываются в противоположную сторону.',
      '<b>Вход:</b>',
      'SELL: EMA8 пересекает EMA21 снизу вверх',
      'BUY: EMA8 пересекает EMA21 сверху вниз',
      '<b>Выход:</b>',
      'SELL: EMA8 пересекает EMA21 сверху вниз',
      'BUY: EMA8 пересекает EMA21 снизу вверх',
      '<b>SL:</b> 3 × ATR &nbsp; <b>TP:</b> выключен',
      '<b>Таймфрейм:</b> любой',
    ],
    indicators: [
      { col: 'ema8',  label: 'EMA8'  },
      { col: 'ema21', label: 'EMA21' },
      { col: 'atr',   label: 'ATR'   },
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
  default_hedge: {
    name: 'Default + Hedge',
    desc: [
      'Основная (MA + MACD + RSI). При входе открываются ОБЕ стороны (хедж).',
      '<b>Вход как у default:</b>',
      'BUY: EMA8 &gt; EMA21 + MACD бычий + RSI 55..70, растёт',
      'SELL: EMA8 &lt; EMA21 + MACD медвежий + RSI 30..45, падает',
      '<b>Выход основной (закрывает обе):</b>',
      'BUY: RSI был ≥ 70, стал &lt; 70',
      'SELL: RSI был ≤ 30, стал &gt; 30',
      '<b>Выход хеджа (только хедж):</b>',
      'SELL-хедж при BUY: RSI &gt; 60',
      'BUY-хедж при SELL: RSI &lt; 40',
      '<b>SL/TP:</b> нет, управление только по RSI',
      '<b>Таймфрейм:</b> любой',
    ],
    indicators: [
      { col: 'ema8',        label: 'EMA8'   },
      { col: 'ema21',       label: 'EMA21'  },
      { col: 'macd_line',   label: 'MACD'   },
      { col: 'macd_signal', label: 'Signal' },
      { col: 'rsi',         label: 'RSI'    },
      { col: 'atr',         label: 'ATR'    },
    ],
  },
  default_inverse: {
    name: 'Default Inverse (MA+MACD+RSI reverse)',
    desc: [
      'Инверсия основной стратегии: когда фильтры MA + MACD + RSI согласованы,',
      'открываем позицию в противоположную сторону.',
      '<b>Вход:</b>',
      'SELL: EMA8 &gt; EMA21 + MACD бычий + RSI 55..70, растёт',
      'BUY:  EMA8 &lt; EMA21 + MACD медвежий + RSI 30..45, падает',
      '<b>Выход (инверсия RSI-выхода default):</b>',
      'BUY закрывается при RSI &gt; 50',
      'SELL закрывается при RSI &lt; 50',
      '<b>Флэт-фильтр (инвертирован):</b> торгуем ТОЛЬКО во флэте.',
      'Флэт = 2 из 3: ADX &lt; 20, BB-ширина ниже средней, ATR ниже среднего.',
      '<b>SL/TP:</b> не заданы стратегией — управляются множителями SL/TP (×ATR).',
      '<b>Таймфрейм:</b> H1 (рекомендуется)',
    ],
    indicators: [
      { col: 'ema8',        label: 'EMA8'   },
      { col: 'ema21',       label: 'EMA21'  },
      { col: 'macd_line',   label: 'MACD'   },
      { col: 'macd_signal', label: 'Signal' },
      { col: 'rsi',         label: 'RSI'    },
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
  mean_revert_ema: {
    name: 'Mean Revert 10/20 EMA',
    desc: [
      'Возврат к среднему: зона 10/20 EMA как справедливая цена в тренде.',
      '<b>Контекст:</b>',
      'BUY: EMA10 &gt; EMA20 &nbsp; SELL: EMA10 &lt; EMA20',
      '<b>Триггер</b> (свеча в зоне EMA):',
      'BUY: бычий пин-бар ≥3× или поглощение ≥80%',
      'SELL: медвежий пин-бар или поглощение',
      '<b>Фильтр:</b> не входим, если цена &gt; 3×ATR от EMA10',
      '<b>SL:</b> 1.5 × ATR &nbsp; <b>Выход:</b> трейл (закрытие свечи за EMA20)',
      '<b>Таймфрейм:</b> H4/D1',
    ],
    indicators: [
      { col: 'ema10', label: 'EMA10' },
      { col: 'ema20', label: 'EMA20' },
      { col: 'atr',   label: 'ATR'   },
    ],
  },
  ema50_pullback: {
    name: 'EMA50 Pullback',
    desc: [
      'Трендовая торговля на откатах к 50 EMA в тренде 200 EMA.',
      '<b>Фильтр тренда:</b> close vs EMA200',
      '<b>Касание:</b> low ≤ EMA50 + 0.5×ATR (BUY) / зеркально (SELL)',
      '<b>Триггер:</b> пин-бар ≥3× или поглощение ≥80%',
      '<b>SL:</b> консервативный из (1×ATR от low сигнальной свечи, 1×ATR от цены входа)',
      '<b>Выход:</b> трейл (закрытие свечи за EMA50)',
      '<b>Таймфрейм:</b> D1 свинг / H4 активный',
    ],
    indicators: [
      { col: 'ema50',  label: 'EMA50'  },
      { col: 'ema200', label: 'EMA200' },
      { col: 'atr',    label: 'ATR'    },
    ],
  },
  ema_triple_touch: {
    name: 'EMA 20/50 Triple Touch',
    desc: [
      'После пересечения EMA20/50 ждём 3 теста зоны перед входом.',
      '<b>Глобальный тренд:</b> цена vs EMA200',
      '<b>Тест зоны</b> [EMA20..EMA50] = касание + закрытие свечи ВНУТРИ зоны',
      '<b>Вход:</b> на 3-м или последующем тесте в направлении кросса',
      '<b>Сброс:</b> обратный кросс 20/50 или пробой EMA200',
      '<b>SL:</b> 2 × ATR &nbsp; <b>Выход:</b> трейл (закрытие свечи за EMA50)',
      '<b>Таймфрейм:</b> H4/D1',
    ],
    indicators: [
      { col: 'ema20',  label: 'EMA20'  },
      { col: 'ema50',  label: 'EMA50'  },
      { col: 'ema200', label: 'EMA200' },
      { col: 'atr',    label: 'ATR'    },
    ],
  },
  market_phase: {
    name: '200 MA + Market Phase',
    desc: [
      'Классификатор фазы по наклону 200 MA, торговля уровней по фазе.',
      '<b>Фаза:</b>',
      'RANGE (|slope| &lt; 0.1°) — пробой последних фрактальных уровней ± 0.2×ATR',
      'TREND_UP — пробой fractal-resistance (продолжение)',
      'TREND_DOWN — пробой fractal-support (продолжение)',
      '<b>Уровни:</b> фракталы Билла Вильямса в окне 40 баров',
      '<b>SL:</b> противоположный уровень ± 0.2×ATR',
      '<b>Выход:</b> трейл (закрытие свечи за 200 MA)',
      '<b>Таймфрейм:</b> D1 / H4',
    ],
    indicators: [
      { col: 'ema200',            label: 'EMA200' },
      { col: 'ma200_slope',       label: 'Slope°' },
      { col: 'level_resistance',  label: 'R'      },
      { col: 'level_support',     label: 'S'      },
      { col: 'atr',               label: 'ATR'    },
    ],
  },
  combined_a_plus: {
    name: 'Combined A+ (5 факторов)',
    desc: [
      'Сигнал проходит только при score ≥ 4 из 5 факторов.',
      '<b>1. Направление:</b> close vs EMA200',
      '<b>2. Касание EMA50:</b> low ≤ EMA50 + 0.5×ATR (BUY)',
      '<b>3. Price action:</b> пин-бар ≥3× или поглощение ≥80%',
      '<b>4. Горизонтальный уровень</b> (фрактал) совпадает с EMA50 или low/high свечи',
      '<b>5. ATR в норме:</b> 0.5× ≤ atr/atr_avg_50 ≤ 2×',
      '<b>SL:</b> 2 × ATR &nbsp; <b>Выход:</b> трейл (закрытие свечи за EMA50)',
      '<b>Таймфрейм:</b> H4/D1',
    ],
    indicators: [
      { col: 'ema50',      label: 'EMA50'   },
      { col: 'ema200',     label: 'EMA200'  },
      { col: 'atr',        label: 'ATR'     },
      { col: 'level_up',   label: 'R'       },
      { col: 'level_down', label: 'S'       },
    ],
  },
  ema50_rejection: {
    name: 'EMA50 Rejection (2×ATR)',
    desc: [
      'Торгуем только в сильном тренде, где EMA50 отстоит от EMA200 ≥ 2×ATR.',
      '<b>BUY:</b>',
      '1. EMA50 − EMA200 ≥ 2×ATR (сильный up-тренд)',
      '2. Ждём закрытия свечи НИЖЕ EMA50 (откат)',
      '3. Вход при закрытии следующей свечи ВЫШЕ EMA50',
      '<b>SELL:</b> зеркально (EMA200 − EMA50 ≥ 2×ATR, откат выше, вход ниже)',
      '<b>Выход:</b> только по установленным SL и TP',
      '<b>Дефолт:</b> SL 1.5×ATR &nbsp; TP 3×ATR (перекрываются из формы)',
      '<b>Таймфрейм:</b> H1 и выше',
    ],
    indicators: [
      { col: 'ema50',  label: 'EMA50'  },
      { col: 'ema200', label: 'EMA200' },
      { col: 'atr',    label: 'ATR'    },
    ],
  },
  ema50_overstretch: {
    name: 'EMA50 Overstretch (4.5×ATR фейд)',
    desc: [
      'Контртренд: фейдим перерастяжение цены от EMA50 в EMA-контексте.',
      '<b>SELL:</b> EMA50 &gt; EMA200 и закрытие ≥ 4.5×ATR ВЫШЕ EMA50',
      '<b>BUY:</b> EMA50 &lt; EMA200 и закрытие ≥ 4.5×ATR НИЖЕ EMA50',
      '<b>Выход:</b> только по установленным SL и TP',
      '<b>Дефолт:</b> SL 1.5×ATR &nbsp; TP 3×ATR (перекрываются из формы)',
      '<b>Таймфрейм:</b> H1 и выше',
    ],
    indicators: [
      { col: 'ema50',  label: 'EMA50'  },
      { col: 'ema200', label: 'EMA200' },
      { col: 'atr',    label: 'ATR'    },
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
  active_strategy: null,
  streams: [],
  streams_max: 10,
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
    // Первым сообщением отправляем токен — до ответа auth_ok сервер
    // не принимает команды и не шлёт события.
    if (AUTH_TOKEN) {
      state.ws.send(JSON.stringify({ cmd: 'auth', token: AUTH_TOKEN }));
    }
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

  if (msg_type === 'auth_ok') {
    // Сервер подтвердил токен и пришлёт agents_snapshot следом.
    if (data && data.user) {
      AUTH_USER = data.user;
      localStorage.setItem('th_user', JSON.stringify(data.user));
      applyRoleVisibility();
    }
    return;
  }

  if (msg_type === 'auth_error' || msg_type === 'auth_required') {
    logout();
    return;
  }

  if (msg_type === 'forbidden') {
    alert((data && data.error) || 'Действие запрещено для вашей роли');
    return;
  }

  if (msg_type === 'agents_snapshot') {
    (data.agents || []).forEach(a => { state.agents[a.name] = a; });
    renderAgents();
    (data.recent_events || []).reverse().forEach(addLogLine);
    renderLog();
    if (data.active_strategy) {
      state.active_strategy = data.active_strategy;
      renderActiveStrategy();
      syncActiveStrategyForm();
    }
    return;
  }

  if (msg_type === 'active_strategy_changed') {
    if (data && !data.error) {
      state.active_strategy = data;
      renderActiveStrategy();
      syncActiveStrategyForm();
    }
    return;
  }

  if (msg_type === 'streams_changed') {
    state.streams = data.streams || [];
    renderStreams();
    renderPositions();
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
    // обновляем маркеры сделок на графике
    try { chartModule.refreshMarkers && chartModule.refreshMarkers(); } catch {}
    return;
  }

  if (type === 'backtest.result') {
    state.backtest_result = payload;
    renderBacktestResult(payload);
    return;
  }

  if (type === 'anomaly.opened' || type === 'anomaly.updated' || type === 'anomaly.closed') {
    Anomalies.onEventStream(ev);
    return;
  }
}

// ─── Render: Agents sidebar ───────────────────────────────────────
function renderAgents() {
  const container = document.getElementById('agents-list');
  if (!container) return;
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
    const pnl = (p.pnl != null) ? p.pnl : p.pnl_money;
    const pnlClass = pnl >= 0 ? 'pnl-pos' : 'pnl-neg';
    const sign = pnl >= 0 ? '+' : '';
    return `
      <div class="pos-card">
        <div class="pos-symbol">${p.symbol}</div>
        <div>
          <span class="badge badge-${p.type.toLowerCase()}">${p.type}</span>
          <span class="pos-meta" style="margin-left:8px">${p.volume} лот</span>
        </div>
        <div class="pos-meta">Вход: ${p.open_price?.toFixed(5)}</div>
        <div class="pos-meta">SL: ${p.sl?.toFixed(5) || '—'}</div>
        <div class="pos-pnl ${pnlClass}">${sign}${fmt(pnl)}$</div>
        <button class="btn-close admin-only" onclick="closePosition(${p.ticket},'${p.symbol}')">✕ Закрыть</button>
      </div>
    `;
  }).join('');
  applyRoleVisibility();
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
let histPeriod = 'today';
let histSymbol = '';
let histOnlyChartSymbol = false;
let histPage = 0;
const HIST_PER_PAGE = 20;

/** Эффективный фильтр символа: явный селект или "только текущий символ графика". */
function _effectiveHistSymbol() {
  if (histOnlyChartSymbol && typeof chartModule !== 'undefined') {
    try { return chartModule.getSymbol() || ''; } catch { /* ignore */ }
  }
  return histSymbol;
}

function _histDealsFor(period) {
  const all = state.history?.[period]?.deals || [];
  const sym = _effectiveHistSymbol();
  if (!sym) return all;
  return all.filter(d => (d.symbol || '') === sym);
}

function _histProfitFor(period) {
  const sym = _effectiveHistSymbol();
  if (!sym) return state.history?.[period]?.profit ?? 0;
  return _histDealsFor(period).reduce((s, d) => s + (d.profit || 0), 0);
}

function refreshHistSymbolFilter() {
  const sel = document.getElementById('hist-symbol-filter');
  if (!sel) return;
  const h = state.history || {};
  const symbols = new Set();
  ['today', 'week', 'month'].forEach(p => {
    (h[p]?.deals || []).forEach(d => { if (d.symbol) symbols.add(d.symbol); });
  });
  const sorted = Array.from(symbols).sort();
  if (histSymbol && !symbols.has(histSymbol)) histSymbol = '';
  const current = histSymbol;
  sel.innerHTML = '<option value="">Все пары</option>' +
    sorted.map(s => `<option value="${s}" ${s === current ? 'selected' : ''}>${s}</option>`).join('');
}

function renderHistory() {
  refreshHistSymbolFilter();
  const todayP = _histProfitFor('today');
  const weekP  = _histProfitFor('week');
  const monthP = _histProfitFor('month');
  const todayN = _histDealsFor('today').length;
  const weekN  = _histDealsFor('week').length;
  const monthN = _histDealsFor('month').length;
  document.getElementById('hist-today').innerHTML = `<div class="stat-label">Сегодня · ${todayN}</div><div class="stat-value ${todayP>=0?'pnl-pos':'pnl-neg'}">${todayP>=0?'+':''}${fmt(todayP)}$</div>`;
  document.getElementById('hist-week').innerHTML  = `<div class="stat-label">Неделя · ${weekN}</div><div class="stat-value ${weekP>=0?'pnl-pos':'pnl-neg'}">${weekP>=0?'+':''}${fmt(weekP)}$</div>`;
  document.getElementById('hist-month').innerHTML = `<div class="stat-label">Месяц · ${monthN}</div><div class="stat-value ${monthP>=0?'pnl-pos':'pnl-neg'}">${monthP>=0?'+':''}${fmt(monthP)}$</div>`;
  renderHistDeals();
}

function renderHistDeals() {
  const deals = _histDealsFor(histPeriod);
  const table = document.getElementById('hist-deals-table');
  const pag   = document.getElementById('hist-pagination');
  if (!table) return;

  if (!deals.length) {
    table.innerHTML = '<div style="color:var(--text-muted);padding:12px">Нет сделок</div>';
    if (pag) pag.innerHTML = '';
    return;
  }

  // Сортируем по времени убывающе (свежие вверху)
  const sorted = deals.slice().sort((a, b) => (b.time || '').localeCompare(a.time || ''));
  const totalPages = Math.ceil(sorted.length / HIST_PER_PAGE);
  if (histPage >= totalPages) histPage = 0;
  const start = histPage * HIST_PER_PAGE;
  const page  = sorted.slice(start, start + HIST_PER_PAGE);

  const totalProfit = sorted.reduce((s, d) => s + (d.profit || 0), 0);
  const totalClass  = totalProfit >= 0 ? 'pnl-pos' : 'pnl-neg';

  table.innerHTML = `
    <table>
      <tr>
        <th>#</th><th>Время</th><th>Тип</th><th>Символ</th><th>Объём</th><th>Тикет</th><th>Причина</th><th>P&L $</th>
      </tr>
      ${page.map((d, i) => {
        const globalIdx = start + i + 1;
        const pc = (d.profit || 0) >= 0 ? 'pnl-pos' : 'pnl-neg';
        const time = (d.time || '').toString().substring(0, 16);
        const type = d.type || '';
        const sign = (d.profit || 0) >= 0 ? '+' : '';
        const reason = d.reason || '—';
        const reasonClass = /^(SL|Stop Out)$/i.test(reason)   ? 'pnl-neg'
                          : /^TP$/i.test(reason)               ? 'pnl-pos'
                          : /^(SIGNAL|RSI|MANUAL)$/i.test(reason) ? 'hist-reason-info'
                          : '';
        return `<tr>
          <td style="color:var(--text-muted)">${globalIdx}</td>
          <td>${time}</td>
          <td><span class="badge badge-${type.toLowerCase()}">${type}</span></td>
          <td>${d.symbol || ''}</td>
          <td>${d.volume != null ? d.volume : ''}</td>
          <td style="color:var(--text-muted)">${d.ticket || ''}</td>
          <td class="${reasonClass}">${escapeHtml(reason)}</td>
          <td class="${pc}">${sign}${fmt(d.profit || 0)}$</td>
        </tr>`;
      }).join('')}
      <tr style="border-top:2px solid var(--border);font-weight:600">
        <td colspan="7" style="text-align:right;color:var(--text-muted)">Итого:</td>
        <td class="${totalClass}">${totalProfit>=0?'+':''}${fmt(totalProfit)}$</td>
      </tr>
    </table>
  `;

  if (!pag) return;
  if (totalPages <= 1) { pag.innerHTML = ''; return; }

  let html = `<button onclick="histGoPage(0)" ${histPage===0?'disabled':''}>&#171;</button>`;
  html += `<button onclick="histGoPage(${histPage-1})" ${histPage===0?'disabled':''}>&#8249;</button>`;
  const range = 2;
  const from = Math.max(0, histPage - range);
  const to   = Math.min(totalPages - 1, histPage + range);
  if (from > 0) html += `<span class="bt-page-dots">...</span>`;
  for (let i = from; i <= to; i++) {
    html += `<button onclick="histGoPage(${i})" class="${i===histPage?'active':''}">${i+1}</button>`;
  }
  if (to < totalPages - 1) html += `<span class="bt-page-dots">...</span>`;
  html += `<button onclick="histGoPage(${histPage+1})" ${histPage>=totalPages-1?'disabled':''}>&#8250;</button>`;
  html += `<button onclick="histGoPage(${totalPages-1})" ${histPage>=totalPages-1?'disabled':''}>&#187;</button>`;
  pag.innerHTML = html;
}

function histGoPage(p) {
  const deals = _histDealsFor(histPeriod);
  const totalPages = Math.ceil(deals.length / HIST_PER_PAGE);
  histPage = Math.max(0, Math.min(p, totalPages - 1));
  renderHistDeals();
}

function histSetPeriod(period) {
  histPeriod = period;
  histPage = 0;
  document.querySelectorAll('#hist-period-tabs .hist-period-btn').forEach(b => {
    b.classList.toggle('active', b.dataset.period === period);
  });
  renderHistDeals();
}

function histSetSymbol(symbol) {
  histSymbol = symbol || '';
  histPage = 0;
  renderHistory();
}

// ─── Render: Event Log ────────────────────────────────────────────
const PER_AGENT_LOG_LIMIT = 80;

function addLogLine(ev) {
  state.log_lines.unshift(ev);
  if (state.log_lines.length > state.MAX_LOG) state.log_lines.pop();

  const src = ev.source || 'System';
  if (!state.agent_logs) state.agent_logs = {};
  if (!state.agent_logs[src]) state.agent_logs[src] = [];
  state.agent_logs[src].unshift(ev);
  if (state.agent_logs[src].length > PER_AGENT_LOG_LIMIT) state.agent_logs[src].pop();

  renderLog();
}

function escapeHtml(s) {
  return String(s)
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;').replace(/'/g, '&#039;');
}

function renderLog() {
  const container = document.getElementById('agent-log-panels');
  if (!container) return;
  const autoScroll = document.getElementById('auto-scroll')?.checked !== false;

  // Источник списка агентов: статусный реестр + любые источники событий, которые там не числятся.
  const agentNames = new Set(Object.keys(state.agents || {}));
  Object.keys(state.agent_logs || {}).forEach(n => agentNames.add(n));
  const ordered = Array.from(agentNames).sort();

  // Убираем панели агентов, которых больше нет в списке.
  Array.from(container.children).forEach(panel => {
    if (!agentNames.has(panel.dataset.agent)) panel.remove();
  });

  ordered.forEach(name => {
    const info    = state.agents[name] || { name, description: '', status: 'idle' };
    const lines   = state.agent_logs?.[name] || [];
    let panel     = container.querySelector(`.agent-log-panel[data-agent="${CSS.escape(name)}"]`);
    const exists  = !!panel;
    if (!panel) {
      panel = document.createElement('div');
      panel.className = 'agent-log-panel';
      panel.dataset.agent = name;
      panel.innerHTML = `
        <div class="agent-log-header">
          <div class="agent-log-title-row">
            <span class="agent-log-status-dot"></span>
            <span class="agent-log-name"></span>
            <span class="agent-log-count"></span>
          </div>
          <div class="agent-log-desc"></div>
        </div>
        <div class="agent-log-body"></div>`;
      container.appendChild(panel);
    }

    panel.querySelector('.agent-log-status-dot').className =
      'agent-log-status-dot ' + (info.status || 'idle');
    panel.querySelector('.agent-log-name').textContent  = name;
    panel.querySelector('.agent-log-count').textContent = `${lines.length} событий`;
    panel.querySelector('.agent-log-desc').textContent  = info.description || '';

    const body = panel.querySelector('.agent-log-body');
    const prevScrollTop    = body.scrollTop;
    const prevScrollHeight = body.scrollHeight;

    if (!lines.length) {
      body.innerHTML = `<div class="agent-log-empty">Нет событий</div>`;
    } else {
      body.innerHTML = lines.map(ev => {
        const t = ev.timestamp ? ev.timestamp.substring(11, 19) : '';
        const payload = JSON.stringify(ev.payload || {});
        return `<div class="log-line">
          <div class="log-line-head">
            <span class="log-time">${escapeHtml(t)}</span>
            <span class="log-type">${escapeHtml(ev.type || '')}</span>
          </div>
          <div class="log-payload">${escapeHtml(payload)}</div>
        </div>`;
      }).join('');
    }

    if (autoScroll) {
      body.scrollTop = 0;
    } else if (exists) {
      const heightDiff = body.scrollHeight - prevScrollHeight;
      body.scrollTop = prevScrollTop + heightDiff;
    }
  });
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
  const strategy  = document.getElementById('active-strategy').value;
  const timeframe = document.getElementById('active-timeframe')?.value || 'H1';
  const symbol    = document.getElementById('active-symbol')?.value || 'XAUUSDrfd';
  const volume    = parseFloat(document.getElementById('active-volume')?.value || '0') || 0;
  const sl_atr    = parseFloat(document.getElementById('active-sl-atr')?.value || '0') || 0;
  const tp_atr    = parseFloat(document.getElementById('active-tp-atr')?.value || '0') || 0;
  sendCmd({ cmd: 'set_active_strategy', strategy, timeframe, symbol, volume, sl_atr, tp_atr });
  const btn = document.getElementById('btn-set-strategy');
  if (btn) { btn.textContent = '✓ Применено'; setTimeout(() => { btn.textContent = '✓ Применить'; }, 2000); }
}

function renderActiveStrategy() {
  const s = state.active_strategy;
  if (!s) return;
  const meta = STRATEGY_META[s.strategy] || { name: s.strategy };
  const labelEl = document.getElementById('asp-strategy');
  const symEl   = document.getElementById('asp-symbol');
  const tfEl    = document.getElementById('asp-timeframe');
  const volEl   = document.getElementById('asp-volume');
  const slEl    = document.getElementById('asp-sl');
  const tpEl    = document.getElementById('asp-tp');
  if (labelEl) labelEl.textContent = meta.name || s.strategy || '—';
  if (symEl)   symEl.textContent   = s.symbol || '—';
  if (tfEl)    tfEl.textContent    = s.timeframe || '—';
  if (volEl) {
    const v = Number(s.volume || 0);
    volEl.textContent = v > 0 ? `${v.toFixed(2)} лот` : 'Авто';
  }
  const fmtAtr = (v) => {
    const n = Number(v || 0);
    return n > 0 ? `${n}×ATR` : 'выкл';
  };
  if (slEl) slEl.textContent = fmtAtr(s.sl_atr);
  if (tpEl) tpEl.textContent = fmtAtr(s.tp_atr);
}

function syncActiveStrategyForm() {
  const s = state.active_strategy;
  if (!s) return;
  const stratSel = document.getElementById('active-strategy');
  const tfSel    = document.getElementById('active-timeframe');
  const symSel   = document.getElementById('active-symbol');
  const volInp   = document.getElementById('active-volume');
  const slInp    = document.getElementById('active-sl-atr');
  const tpInp    = document.getElementById('active-tp-atr');
  if (stratSel && s.strategy) stratSel.value = s.strategy;
  if (tfSel && s.timeframe)   tfSel.value    = s.timeframe;
  if (symSel && s.symbol) {
    const has = Array.from(symSel.options).some(o => o.value === s.symbol);
    if (has) symSel.value = s.symbol;
  }
  if (volInp && s.volume != null) volInp.value = s.volume;
  if (slInp  && s.sl_atr != null) slInp.value  = s.sl_atr;
  if (tpInp  && s.tp_atr != null) tpInp.value  = s.tp_atr;
}

async function populateActiveSymbols() {
  const sel = document.getElementById('active-symbol');
  if (!sel) return;
  try {
    const r = await fetch('/api/symbols');
    const d = await r.json();
    const symbols = d.symbols || [];
    if (!symbols.length) return;
    const current = state.active_strategy?.symbol || 'XAUUSDrfd';
    sel.innerHTML = symbols.map(s =>
      `<option value="${s}" ${s === current ? 'selected' : ''}>${s}</option>`
    ).join('');
  } catch {}
}

// ─── Streams (мульти-поточная торговля) ──────────────────────────
const STREAM_TF_OPTIONS = ['M1','M5','M15','M30','H1','H4','D1'];
const STREAM_STRATEGY_OPTIONS = [
  ['default',              'MA + MACD + RSI (основная)'],
  ['sr_bounce',            'S/R Bounce'],
  ['ema_pullback',         'EMA Pullback (50/200)'],
  ['ema_cross',            'EMA 50/200 Cross'],
  ['ema_cross_inverse',    'EMA 8/21 Cross Inverse'],
  ['cci_rsi',              'CCI + RSI (D1-фильтр)'],
  ['fibonacci_retracement','Fibonacci Retracement'],
  ['macd_hist',            'MACD Histogram'],
  ['default_hedge',        'Default + Hedge'],
  ['default_inverse',      'Default Inverse (MA+MACD+RSI reverse)'],
  ['candle_reversal',      'Candlestick Reversal'],
  ['sar_adx',              'Parabolic SAR + ADX'],
  ['donchian_breakout',    'Donchian Breakout'],
  ['triple_ema',           'Triple EMA Momentum'],
  ['mean_revert_ema',      'Mean Revert 10/20 EMA'],
  ['ema50_pullback',       'EMA50 Pullback (D1/H4)'],
  ['ema_triple_touch',     'EMA 20/50 Triple Touch'],
  ['market_phase',         '200 MA + Market Phase'],
  ['combined_a_plus',      'Combined A+ (5 факторов)'],
  ['ema50_rejection',      'EMA50 Rejection (2×ATR)'],
  ['ema50_overstretch',    'EMA50 Overstretch (4.5×ATR фейд)'],
];

async function loadStreams() {
  try {
    const r = await fetch('/api/streams');
    const d = await r.json();
    state.streams = d.streams || [];
    state.streams_max = d.max || 10;
    renderStreams();
  } catch (e) {
    console.error('loadStreams failed', e);
  }
}

function _strategyLabel(key) {
  const pair = STREAM_STRATEGY_OPTIONS.find(p => p[0] === key);
  return pair ? pair[1] : key;
}

function renderStreams() {
  const box = document.getElementById('streams-table');
  if (!box) return;
  const streams = state.streams || [];
  const badge = document.getElementById('streams-count-badge');
  if (badge) badge.textContent = `${streams.length} / ${state.streams_max || 10}`;

  const addBtn = document.getElementById('btn-add-stream');
  if (addBtn) addBtn.disabled = streams.length >= (state.streams_max || 10);

  if (!streams.length) {
    box.innerHTML = '<div class="streams-empty">Потоков пока нет — нажмите «+ Добавить поток», чтобы создать первый.</div>';
    return;
  }

  const rows = streams.map(s => {
    const vol = Number(s.volume || 0);
    const volTxt = vol > 0 ? `${vol.toFixed(2)}` : 'авто';
    const slTxt = Number(s.sl_atr || 0) > 0 ? `${s.sl_atr}×` : '—';
    const tpTxt = Number(s.tp_atr || 0) > 0 ? `${s.tp_atr}×` : '—';
    const beTxt = Number(s.breakeven_atr || 0) > 0 ? `${s.breakeven_atr}×` : '—';
    const trTxt = Number(s.trail_atr || 0) > 0 ? `${s.trail_atr}×` : '—';
    const dep = Number(s.deposit || 0);
    const depTxt = dep > 0 ? `$${dep.toLocaleString('ru-RU')}` : '—';
    const stateClass = s.enabled ? 'is-on' : 'is-off';
    const stateLabel = s.enabled ? 'Вкл' : 'Выкл';
    return `
      <tr data-stream-id="${s.id}">
        <td class="st-name">${escapeHtml(s.name)}</td>
        <td title="${escapeHtml(_strategyLabel(s.strategy))}">${escapeHtml(_strategyLabel(s.strategy))}</td>
        <td class="st-sym">${s.symbol}</td>
        <td>${s.timeframe}</td>
        <td>${volTxt}</td>
        <td>${slTxt}</td>
        <td>${tpTxt}</td>
        <td title="Breakeven × ATR">${beTxt}</td>
        <td title="Trailing SL × ATR">${trTxt}</td>
        <td>${depTxt}</td>
        <td><span class="st-state ${stateClass}">${stateLabel}</span></td>
        <td class="st-actions admin-only">
          <button class="btn-ghost" title="${s.enabled ? 'Выключить' : 'Включить'}" onclick="toggleStream('${s.id}', ${!s.enabled})">${s.enabled ? '⏸' : '▶'}</button>
          <button class="btn-ghost" title="Редактировать" onclick="openStreamForm('${s.id}')">✎</button>
          <button class="btn-ghost btn-danger" title="Удалить" onclick="deleteStream('${s.id}')">✕</button>
        </td>
      </tr>
    `;
  }).join('');

  box.innerHTML = `
    <table class="streams-grid">
      <thead>
        <tr>
          <th>Название</th>
          <th>Стратегия</th>
          <th>Пара</th>
          <th>TF</th>
          <th>Объём</th>
          <th>SL</th>
          <th>TP</th>
          <th>BE</th>
          <th>Trail</th>
          <th>Депозит</th>
          <th>Статус</th>
          <th class="admin-only"></th>
        </tr>
      </thead>
      <tbody>${rows}</tbody>
    </table>
  `;
  applyRoleVisibility();
}

function escapeHtml(s) {
  return String(s == null ? '' : s)
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
}

async function openStreamForm(stream_id) {
  const wrap = document.getElementById('stream-form-wrap');
  if (!wrap) return;
  const editing = stream_id ? (state.streams || []).find(s => s.id === stream_id) : null;

  // Список пар: всё из /api/symbols минус уже занятые (кроме редактируемого).
  let symbols = [];
  try {
    const r = await fetch('/api/symbols');
    const d = await r.json();
    symbols = d.symbols || [];
  } catch {}
  const takenSymbols = new Set((state.streams || [])
    .filter(s => !editing || s.id !== editing.id)
    .map(s => s.symbol));
  const symOptions = symbols
    .filter(sym => !takenSymbols.has(sym) || (editing && editing.symbol === sym))
    .map(sym => `<option value="${sym}" ${editing && editing.symbol === sym ? 'selected' : ''}>${sym}</option>`)
    .join('');

  const stratOptions = STREAM_STRATEGY_OPTIONS.map(([v, l]) =>
    `<option value="${v}" ${editing && editing.strategy === v ? 'selected' : ''}>${escapeHtml(l)}</option>`
  ).join('');

  const tfOptions = STREAM_TF_OPTIONS.map(tf =>
    `<option value="${tf}" ${(editing ? editing.timeframe : 'H1') === tf ? 'selected' : ''}>${tf}</option>`
  ).join('');

  const titleTxt = editing ? `Редактирование потока «${escapeHtml(editing.name)}»` : 'Новый поток';
  wrap.hidden = false;
  wrap.innerHTML = `
    <div class="stream-form">
      <div class="stream-form-title">${titleTxt}</div>
      <div class="bt-form">
        <label>Название
          <input id="sf-name" type="text" value="${editing ? escapeHtml(editing.name) : ''}" placeholder="например, XAU H1 скальп" style="width:200px">
        </label>
        <label>Стратегия
          <select id="sf-strategy" style="min-width:240px">${stratOptions}</select>
        </label>
        <label>Пара
          <select id="sf-symbol" style="min-width:130px">${symOptions}</select>
        </label>
        <label>Таймфрейм
          <select id="sf-timeframe">${tfOptions}</select>
        </label>
        <label>Объём (0 = авто)
          <input id="sf-volume" type="number" value="${editing ? editing.volume : 0}" min="0" step="0.01" style="width:100px">
        </label>
        <label>SL (×ATR)
          <input id="sf-sl-atr" type="number" value="${editing ? editing.sl_atr : 0}" min="0" step="0.1" style="width:90px">
        </label>
        <label>TP (×ATR)
          <input id="sf-tp-atr" type="number" value="${editing ? editing.tp_atr : 0}" min="0" step="0.1" style="width:90px">
        </label>
        <label title="Выделенный депозит потока. Просадка > 35% блокирует поток до понедельника.">
          Депозит ($)
          <input id="sf-deposit" type="number" value="${editing ? (editing.deposit || 0) : 0}" min="0" step="100" style="width:110px">
        </label>
        <label title="После прохода +N×ATR в нашу сторону двигает SL в точку входа. 0 = выкл.">
          BE (×ATR)
          <input id="sf-be-atr" type="number" value="${editing ? (editing.breakeven_atr || 0) : 0}" min="0" step="0.1" style="width:90px">
        </label>
        <label title="Трейлинг SL по ATR. SL только ужесточается. 0 = выкл.">
          Trail (×ATR)
          <input id="sf-trail-atr" type="number" value="${editing ? (editing.trail_atr || 0) : 0}" min="0" step="0.1" style="width:90px">
        </label>
        <label class="sf-enabled-label">
          <input id="sf-enabled" type="checkbox" ${!editing || editing.enabled ? 'checked' : ''}>
          Включён
        </label>
        <button class="btn-primary" onclick="submitStreamForm('${editing ? editing.id : ''}')">
          ${editing ? 'Сохранить' : 'Создать'}
        </button>
        <button class="btn-ghost btn-ghost-lg" onclick="closeStreamForm()">Отмена</button>
        <span id="sf-error" class="sf-error"></span>
      </div>
    </div>
  `;
  setTimeout(() => document.getElementById('sf-name')?.focus(), 50);
}

function closeStreamForm() {
  const wrap = document.getElementById('stream-form-wrap');
  if (wrap) { wrap.hidden = true; wrap.innerHTML = ''; }
}

async function submitStreamForm(stream_id) {
  const body = {
    name:      document.getElementById('sf-name').value.trim(),
    strategy:  document.getElementById('sf-strategy').value,
    symbol:    document.getElementById('sf-symbol').value,
    timeframe: document.getElementById('sf-timeframe').value,
    volume:        parseFloat(document.getElementById('sf-volume').value   || '0') || 0,
    sl_atr:        parseFloat(document.getElementById('sf-sl-atr').value   || '0') || 0,
    tp_atr:        parseFloat(document.getElementById('sf-tp-atr').value   || '0') || 0,
    deposit:       parseFloat(document.getElementById('sf-deposit').value  || '0') || 0,
    breakeven_atr: parseFloat(document.getElementById('sf-be-atr').value   || '0') || 0,
    trail_atr:     parseFloat(document.getElementById('sf-trail-atr').value|| '0') || 0,
    enabled:       document.getElementById('sf-enabled').checked,
  };
  const errEl = document.getElementById('sf-error');
  if (errEl) errEl.textContent = '';
  const url    = stream_id ? `/api/streams/${stream_id}` : '/api/streams';
  const method = stream_id ? 'PATCH' : 'POST';
  try {
    const r = await fetch(url, {
      method,
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
    const d = await r.json();
    if (!r.ok) {
      if (errEl) errEl.textContent = d.detail || 'Ошибка';
      return;
    }
    closeStreamForm();
    await loadStreams();
  } catch (e) {
    if (errEl) errEl.textContent = e.message || 'Ошибка сети';
  }
}

async function toggleStream(stream_id, enabled) {
  try {
    await fetch(`/api/streams/${stream_id}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ enabled }),
    });
    await loadStreams();
  } catch (e) { console.error(e); }
}

async function deleteStream(stream_id) {
  const s = (state.streams || []).find(x => x.id === stream_id);
  const label = s ? `«${s.name}» (${s.symbol})` : stream_id;
  if (!confirm(`Удалить поток ${label}? Открытые позиции этого потока не закрываются автоматически.`)) return;
  try {
    await fetch(`/api/streams/${stream_id}`, { method: 'DELETE' });
    await loadStreams();
  } catch (e) { console.error(e); }
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

/**
 * Заполняет селект стратегий бэктеста из /api/strategies. Вызывается при
 * инициализации, чтобы новые стратегии появлялись без правки HTML.
 * Группируем по семейству, чтобы было удобно ориентироваться.
 */
async function populateBtStrategies() {
  const sel = document.getElementById('bt-strategy');
  if (!sel) return;
  const preferred = sel.value || 'default';
  try {
    const r = await fetch('/api/strategies');
    const d = await r.json();
    const items = d.strategies || [];
    if (!items.length) return;

    const groups = {};
    for (const s of items) (groups[s.family] = groups[s.family] || []).push(s);

    // Сохраняем «default» (он не в STRATEGIES, но есть в backend как ветвь "default")
    let html = `<option value="default">MA + MACD + RSI (основная)</option>`;
    const order = ['candle','mean_revert','trend_follow','breakout','scalp','momentum','hedge','custom'];
    const seen = new Set();
    const fams = order.filter(f => groups[f]).concat(Object.keys(groups).filter(f => !order.includes(f)));
    for (const fam of fams) {
      const arr = groups[fam] || [];
      if (!arr.length) continue;
      const label = (typeof STRAT_FAMILY_LABEL !== 'undefined' && STRAT_FAMILY_LABEL[fam]) || fam;
      html += `<optgroup label="${escapeHtml(label)}">`;
      for (const s of arr.sort((a,b)=>a.key.localeCompare(b.key))) {
        if (seen.has(s.key)) continue;
        seen.add(s.key);
        const desc = s.description ? ` — ${s.description}` : '';
        html += `<option value="${escapeHtml(s.key)}">${escapeHtml(s.key)}${escapeHtml(desc)}</option>`;
      }
      html += `</optgroup>`;
    }
    sel.innerHTML = html;
    // Восстанавливаем предыдущий выбор, если возможно
    if ([...sel.options].some(o => o.value === preferred)) sel.value = preferred;
    // Триггерим зависимый рендер описания
    try { onBtStrategyChange(); } catch {}
  } catch (e) {
    console.warn('populateBtStrategies failed:', e);
  }
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
  const sl_atr    = parseFloat(document.getElementById('bt-sl-atr')?.value || '0') || 0;
  const tp_atr    = parseFloat(document.getElementById('bt-tp-atr')?.value || '0') || 0;
  const spread    = parseInt(document.getElementById('bt-spread')?.value || '0', 10) || 0;
  const breakeven_atr = parseFloat(document.getElementById('bt-be-atr')?.value    || '0') || 0;
  const trail_atr     = parseFloat(document.getElementById('bt-trail-atr')?.value || '0') || 0;
  const start     = document.getElementById('bt-start').value || null;
  const end       = document.getElementById('bt-end').value || null;
  sendCmd({ cmd: 'run_backtest', strategy, symbol, timeframe, bars, deposit, spread, volume, sl_atr, tp_atr, breakeven_atr, trail_atr, start, end });
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
    <div id="bt-chart-card" class="card" style="display:none">
      <div class="card-title">График сделок</div>
      <div id="bt-chart-container" style="position:relative;width:100%;height:380px"></div>
    </div>
    ${renderBtTrades(r.trades)}
  `;
  renderBtPage();
  // График свечей со сделками бэктеста (асинхронно — может потребовать запрос /api/candles)
  try { renderBtChart(payload); } catch (e) { console.warn('bt chart failed:', e); }
}

// ─── Backtest: candle chart with trades ───────────────────────────
let _btChart = null;
let _btCandleSeries = null;
const _btTradeLines = [];

function _btDestroyChart() {
  while (_btTradeLines.length) {
    const s = _btTradeLines.pop();
    try { _btChart.removeSeries(s); } catch {}
  }
  if (_btChart) {
    try { _btChart.remove(); } catch {}
    _btChart = null;
    _btCandleSeries = null;
  }
}

/** Парсит "YYYY-MM-DD HH:MM:SS" → unix-секунды (UTC). */
function _btTimeToUnix(s) {
  if (!s) return null;
  const m = String(s).match(/^(\d{4})-(\d{2})-(\d{2})[ T](\d{2}):(\d{2}):(\d{2})/);
  if (!m) return null;
  return Math.floor(Date.UTC(+m[1], +m[2]-1, +m[3], +m[4], +m[5], +m[6]) / 1000);
}

/** Снап ts на ближайший бар (бин-поиск по массиву candles). */
function _btSnapToBar(ts, candles) {
  if (!candles.length) return null;
  let lo = 0, hi = candles.length - 1;
  if (ts <= candles[0].time) return candles[0].time;
  if (ts >= candles[hi].time) return candles[hi].time;
  while (lo < hi - 1) {
    const mid = (lo + hi) >> 1;
    if (candles[mid].time <= ts) lo = mid; else hi = mid;
  }
  return candles[lo].time;
}

async function renderBtChart(payload) {
  const card = document.getElementById('bt-chart-card');
  const el   = document.getElementById('bt-chart-container');
  if (!card || !el || typeof LightweightCharts === 'undefined') return;
  const r = payload?.result;
  const trades = r?.trades || [];
  if (!trades.length) { card.style.display = 'none'; return; }

  const symbol    = payload.symbol || document.getElementById('bt-symbol')?.value;
  const timeframe = (document.getElementById('bt-timeframe')?.value || 'H1').toUpperCase();
  if (!symbol) return;

  // Диапазон дат: первая запись entry → последняя exit, плюс паддинг.
  const tsList = [];
  for (const t of trades) {
    const a = _btTimeToUnix(t.entry_time); if (a) tsList.push(a);
    const b = _btTimeToUnix(t.exit_time);  if (b) tsList.push(b);
  }
  if (!tsList.length) { card.style.display = 'none'; return; }
  const minTs = Math.min(...tsList);
  const maxTs = Math.max(...tsList);
  // паддинг: 5% диапазона по краям, минимум 1 день
  const pad = Math.max(86400, Math.floor((maxTs - minTs) * 0.05));
  const fmtDate = (ts) => {
    const d = new Date((ts - pad) * 1000);
    const pad2 = (n) => String(n).padStart(2, '0');
    return `${d.getUTCFullYear()}-${pad2(d.getUTCMonth()+1)}-${pad2(d.getUTCDate())}`;
  };
  const dateFrom = fmtDate(minTs);
  const dateTo   = (() => {
    const d = new Date((maxTs + pad) * 1000);
    const pad2 = (n) => String(n).padStart(2, '0');
    return `${d.getUTCFullYear()}-${pad2(d.getUTCMonth()+1)}-${pad2(d.getUTCDate())}`;
  })();

  card.style.display = '';
  el.innerHTML = '<div style="position:absolute;inset:0;display:flex;align-items:center;justify-content:center;color:var(--text-muted)">Загрузка свечей…</div>';

  let candles = [];
  try {
    const url = `/api/candles?symbol=${encodeURIComponent(symbol)}&timeframe=${encodeURIComponent(timeframe)}&date_from=${dateFrom}&date_to=${dateTo}`;
    const resp = await fetch(url);
    const data = await resp.json();
    if (data.error) throw new Error(data.error);
    candles = (data.candles || []).map(c => ({
      time: c.time, open: c.open, high: c.high, low: c.low, close: c.close,
    }));
  } catch (e) {
    el.innerHTML = `<div style="position:absolute;inset:0;display:flex;align-items:center;justify-content:center;color:var(--text-danger,#e66)">Ошибка загрузки свечей: ${escapeHtml(String(e.message||e))}</div>`;
    return;
  }
  if (!candles.length) {
    el.innerHTML = '<div style="position:absolute;inset:0;display:flex;align-items:center;justify-content:center;color:var(--text-muted)">Нет данных за период</div>';
    return;
  }

  // Пересоздаём график начисто
  _btDestroyChart();
  el.innerHTML = '';
  _btChart = LightweightCharts.createChart(el, {
    width:  el.clientWidth,
    height: el.clientHeight,
    layout: {
      background: { color: 'transparent' },
      textColor: getComputedStyle(document.body).getPropertyValue('--text-primary')?.trim() || '#d1d4dc',
    },
    grid: {
      vertLines: { color: 'rgba(120,120,120,0.10)' },
      horzLines: { color: 'rgba(120,120,120,0.10)' },
    },
    rightPriceScale: { borderVisible: false },
    timeScale: { borderVisible: false, timeVisible: true, secondsVisible: false },
    crosshair: { mode: 1 },
  });
  _btCandleSeries = _btChart.addCandlestickSeries({
    upColor: '#20B26C', downColor: '#EF454A',
    borderUpColor: '#20B26C', borderDownColor: '#EF454A',
    wickUpColor: '#20B26C', wickDownColor: '#EF454A',
  });
  _btCandleSeries.setData(candles);

  // Маркеры + пунктирные линии open→close
  const fmtMoney = (v) => (v >= 0 ? '+' : '') + (Number(v) || 0).toFixed(2) + '$';
  const fmtPts   = (v) => (v >= 0 ? '+' : '') + (Number(v) || 0).toFixed(0);
  const markers = [];
  for (const t of trades) {
    const entryTs = _btTimeToUnix(t.entry_time);
    const exitTs  = _btTimeToUnix(t.exit_time);
    if (entryTs == null || exitTs == null) continue;
    const entryBar = _btSnapToBar(entryTs, candles);
    const exitBar  = _btSnapToBar(exitTs,  candles);
    const type = (t.type || '').toUpperCase();
    const isBuy = type === 'BUY';
    const pnl = (t.pnl_money != null) ? Number(t.pnl_money) : Number(t.pnl_points || 0);
    const pos = pnl >= 0;
    const color = isBuy ? '#20B26C' : '#EF454A';

    // Маркер входа
    markers.push({
      time:     entryBar,
      position: isBuy ? 'belowBar' : 'aboveBar',
      shape:    isBuy ? 'arrowUp'  : 'arrowDown',
      color,
      text:     type,
    });
    // Маркер выхода (цвет по знаку P&L)
    markers.push({
      time:     exitBar,
      position: isBuy ? 'aboveBar' : 'belowBar',
      shape:    'circle',
      color:    pos ? '#20B26C' : '#EF454A',
      text:     (t.pnl_money != null) ? fmtMoney(t.pnl_money) : fmtPts(t.pnl_points),
    });

    // Пунктирная линия entry→exit
    let t1 = entryBar, t2 = exitBar;
    if (t2 <= t1) t2 = t1 + 1;
    try {
      const line = _btChart.addLineSeries({
        color,
        lineWidth: 1.5,
        lineStyle: 2,
        priceLineVisible: false,
        lastValueVisible: false,
        crosshairMarkerVisible: false,
      });
      line.setData([
        { time: t1, value: Number(t.entry_price) },
        { time: t2, value: Number(t.exit_price)  },
      ]);
      _btTradeLines.push(line);
    } catch {}
  }
  markers.sort((a, b) => a.time - b.time);
  try { _btCandleSeries.setMarkers(markers); } catch {}

  _btChart.timeScale().fitContent();

  // Ресайз
  if (!el._btResizeBound) {
    new ResizeObserver((entries) => {
      for (const e of entries) {
        if (_btChart) try { _btChart.applyOptions({ width: e.contentRect.width, height: e.contentRect.height }); } catch {}
      }
    }).observe(el);
    el._btResizeBound = true;
  }
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
  const tradeLineSeries = []; // линии open→close для каждой сделки
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
      // Маркеры сделок поверх свечей (для текущего символа)
      try { refreshMarkers(); } catch {}
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
    const lc = col ? col.toLowerCase() : '';
    if (lc.includes('rsi') || lc === 'cci' || lc.includes('adx')) {
      return v.toFixed(2);
    }
    // Ценовые уровни (EMA/MA/SMA) — формат как у инструмента, до 5 знаков.
    if (/^(ema|ma|sma|wma)\d*$/.test(lc) || lc === 'price' || lc === 'close') {
      return v.toFixed(Math.min(digits, 5));
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
      const barW = Math.max(0.1, bw > 1 ? bw - 0.5 : bw * 0.9);
      return `<rect x="${x.toFixed(1)}" y="${y.toFixed(1)}" width="${barW.toFixed(2)}" height="${barH.toFixed(1)}" fill="${fill}"/>`;
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
    // Если в истории включён режим "только текущий символ" — перерисовать
    try { if (typeof histOnlyChartSymbol !== 'undefined' && histOnlyChartSymbol) renderHistory(); } catch {}
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
    document.querySelectorAll('#chart-tf-buttons .tf-btn').forEach(b =>
      b.addEventListener('click', () => setTimeframe(b.dataset.tf))
    );
  }

  /** Возвращает символ текущего графика (для маркеров сделок и фильтра истории). */
  function getSymbol() { return currentSymbol; }

  /** Преобразует "YYYY-MM-DD HH:MM:SS" → unix-секунды (UTC-trick для корректной шкалы LWC). */
  function _dealTimeToUnix(s) {
    if (!s) return null;
    const m = String(s).match(/^(\d{4})-(\d{2})-(\d{2})[ T](\d{2}):(\d{2}):(\d{2})/);
    if (!m) return null;
    return Math.floor(Date.UTC(+m[1], +m[2]-1, +m[3], +m[4], +m[5], +m[6]) / 1000);
  }

  /** Снап сделки на ближайший бар графика (бин-поиск). */
  function _snapToBar(dealTs, candles) {
    if (!candles.length) return null;
    let lo = 0, hi = candles.length - 1;
    if (dealTs <= candles[0].time) return candles[0].time;
    if (dealTs >= candles[hi].time) return candles[hi].time;
    while (lo < hi - 1) {
      const mid = (lo + hi) >> 1;
      if (candles[mid].time <= dealTs) lo = mid; else hi = mid;
    }
    return candles[lo].time;
  }

  /** Удаляет все нарисованные ранее линии трейдов с графика. */
  function _clearTradeLines() {
    while (tradeLineSeries.length) {
      const s = tradeLineSeries.pop();
      try { chart.removeSeries(s); } catch {}
    }
  }

  /**
   * Рисует маркеры + пунктирные линии open→close по каждой закрытой сделке
   * (как в MetaTrader). BUY-линии зелёные, SELL — красные. Маркеры:
   * BUY → arrowUp снизу бара, SELL → arrowDown сверху; цвет по знаку P&L.
   */
  function refreshMarkers() {
    if (!candleSeries) return;
    const candles = candleSeries.data();
    _clearTradeLines();
    if (!candles.length) { try { candleSeries.setMarkers([]); } catch {} return; }
    const minT = candles[0].time, maxT = candles[candles.length-1].time;

    // Берём максимально широкий период (месяц) — он содержит и неделю, и сегодня
    const all = (state?.history?.month?.deals) || [];
    const fmtUSD = (v) => (v >= 0 ? '+' : '') + (Number(v) || 0).toFixed(2) + '$';

    const markers = [];
    for (const d of all) {
      if (!d || d.symbol !== currentSymbol) continue;
      // Предпочитаем сырой unix-таймстемп от бэкенда (без сдвигов TZ).
      const closeTs = (d.time_ts != null) ? Number(d.time_ts) : _dealTimeToUnix(d.time);
      if (closeTs == null || closeTs < minT - 86400 || closeTs > maxT + 86400) continue;
      const barT = _snapToBar(closeTs, candles);
      if (barT == null) continue;

      // Маркер закрытия (в духе уже принятого UX: цвет по P&L)
      const closingType = (d.type || '').toUpperCase();
      const profit = Number(d.profit) || 0;
      const profitPos = profit >= 0;
      markers.push({
        time:     barT,
        // closingType — это ПРОТИВОПОЛОЖНОЕ направление позиции
        // (BUY-позиция закрывается SELL-сделкой). Стрелка = направление позиции.
        position: closingType === 'SELL' ? 'belowBar' : 'aboveBar',
        shape:    closingType === 'SELL' ? 'arrowUp'  : 'arrowDown',
        color:    profitPos ? '#20B26C' : '#EF454A',
        text:     fmtUSD(profit),
      });

      // Пунктирная линия от точки входа до закрытия — стиль MetaTrader.
      // Используем position_type (направление позиции) из IN-сделки.
      const openTs = (d.open_time_ts != null) ? Number(d.open_time_ts) : _dealTimeToUnix(d.open_time);
      const openP  = (d.open_price  != null) ? Number(d.open_price)  : null;
      const closeP = (d.close_price != null) ? Number(d.close_price) : null;
      const posType = (d.position_type || '').toUpperCase();
      if (openTs != null && openP != null && closeP != null && posType) {
        // Гарантируем строго возрастающий порядок (LWC требует уникальных time).
        let t1 = openTs;
        let t2 = closeTs;
        if (t2 <= t1) t2 = t1 + 1;
        try {
          const color = posType === 'BUY' ? '#20B26C' : '#EF454A';
          const line = chart.addLineSeries({
            color,
            lineWidth: 1.5,
            lineStyle: 2, // 2 = Dashed (LightweightCharts.LineStyle.Dashed)
            priceLineVisible: false,
            lastValueVisible: false,
            crosshairMarkerVisible: false,
          });
          line.setData([
            { time: t1, value: openP },
            { time: t2, value: closeP },
          ]);
          tradeLineSeries.push(line);
        } catch (e) {
          // молча — не ломаем график из-за одной плохой сделки
        }
      }
    }
    // LWC требует возрастающий порядок по time
    markers.sort((a, b) => a.time - b.time);
    try { candleSeries.setMarkers(markers); } catch (e) { console.warn('setMarkers failed:', e); }
  }

  return { activate, deactivate, bind, onCandleUpdate, onWsReconnect, refreshMarkers, getSymbol };
})();

// ─── Tabs ─────────────────────────────────────────────────────────
function switchTab(name) {
  // Совместимость: старая вкладка 'history' теперь живёт внутри 'indicators'
  if (name === 'history') name = 'indicators';
  document.querySelectorAll('.tab').forEach(t => t.classList.toggle('active', t.dataset.tab === name));
  document.querySelectorAll('.content').forEach(c => c.classList.toggle('active', c.id === `tab-${name}`));
  if (name === 'indicators') {
    chartModule.activate();
    // Подсветить историю и нарисовать маркеры на графике
    try { renderHistory(); } catch {}
    try { chartModule.refreshMarkers && chartModule.refreshMarkers(); } catch {}
  } else {
    chartModule.deactivate();
  }
  if (name === 'strategies') {
    try { loadStrategiesTab(); } catch (e) { console.warn('strategies load failed:', e); }
  }
}

// ─── Strategies catalog ───────────────────────────────────────────
const _stratState = { items: [], selected: null, loaded: false };
const STRAT_FAMILY_LABEL = {
  candle:       'Свечные паттерны',
  mean_revert:  'Возврат к среднему',
  trend_follow: 'Тренд',
  breakout:     'Пробой / отскок S/R',
  scalp:        'Скальпинг',
  momentum:     'Моментум',
  hedge:        'Хедж / инверсия',
  custom:       'Прочее',
};

async function loadStrategiesTab() {
  if (_stratState.loaded) return;
  try {
    const r = await fetch('/api/strategies');
    const d = await r.json();
    _stratState.items  = d.strategies || [];
    _stratState.loaded = true;
    renderStrategyList();
    if (_stratState.items.length) selectStrategy(_stratState.items[0].key);
  } catch (e) {
    document.getElementById('strat-list').innerHTML =
      `<div style="color:var(--text-danger,#e66);padding:12px">Ошибка загрузки: ${escapeHtml(String(e))}</div>`;
  }
  // Поиск
  const search = document.getElementById('strat-search');
  if (search && !search._bound) {
    search.addEventListener('input', () => renderStrategyList(search.value.trim().toLowerCase()));
    search._bound = true;
  }
}

function renderStrategyList(filter = '') {
  const list = document.getElementById('strat-list');
  if (!list) return;
  const items = !filter ? _stratState.items : _stratState.items.filter(s =>
    s.key.toLowerCase().includes(filter) ||
    (s.description || '').toLowerCase().includes(filter) ||
    (s.doc || '').toLowerCase().includes(filter)
  );
  if (!items.length) {
    list.innerHTML = '<div style="color:var(--text-muted);padding:12px">Ничего не найдено</div>';
    return;
  }
  // Группируем по семейству
  const groups = {};
  for (const s of items) (groups[s.family] = groups[s.family] || []).push(s);
  let html = '';
  for (const fam of Object.keys(groups)) {
    html += `<div class="strat-list-group">${escapeHtml(STRAT_FAMILY_LABEL[fam] || fam)}</div>`;
    for (const s of groups[fam]) {
      const active = (_stratState.selected === s.key) ? ' active' : '';
      html += `<div class="strat-list-item${active}" data-key="${escapeHtml(s.key)}" onclick="selectStrategy('${s.key}')">
        <span>${escapeHtml(s.key)}</span>
        <span class="tf-badge">${escapeHtml(s.timeframe)}</span>
      </div>`;
    }
  }
  list.innerHTML = html;
}

function selectStrategy(key) {
  _stratState.selected = key;
  renderStrategyList(document.getElementById('strat-search')?.value?.trim()?.toLowerCase() || '');
  const s = _stratState.items.find(x => x.key === key);
  if (!s) return;
  const detail = document.getElementById('strat-detail');
  if (!detail) return;

  const params = (s.indicators || []).map(c => `<span class="pill">${escapeHtml(c)}</span>`).join(' ');

  detail.innerHTML = `
    <h2>${escapeHtml(s.key)}</h2>
    <div class="strat-meta">
      <span class="pill">TF: ${escapeHtml(s.timeframe)}</span>
      <span class="pill">${escapeHtml(STRAT_FAMILY_LABEL[s.family] || s.family)}</span>
      ${s.description ? `<span class="pill">${escapeHtml(s.description)}</span>` : ''}
    </div>

    <div class="strat-section-title">Описание</div>
    <div class="strat-doc">${escapeHtml(s.doc)}</div>

    ${params ? `<div class="strat-section-title">Индикаторы / выходные колонки</div>
                <div style="display:flex;gap:6px;flex-wrap:wrap">${params}</div>` : ''}

    <div class="strat-section-title">Иллюстрация паттерна</div>
    <div id="strat-svg-host"></div>

    <div class="strat-actions">
      <button class="btn-primary" onclick="openInBacktest('${s.key}')">Открыть в бэктесте</button>
    </div>
  `;
  document.getElementById('strat-svg-host').innerHTML = drawStrategyExampleSVG(s);
}

/** Открыть стратегию во вкладке «Бэктест»: переключиться, заполнить селект, проскроллить. */
function openInBacktest(key) {
  switchTab('backtest');
  setTimeout(() => {
    const sel = document.getElementById('bt-strategy');
    if (sel) {
      sel.value = key;
      sel.dispatchEvent(new Event('change'));
    }
    document.getElementById('bt-result')?.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }, 50);
}

/**
 * Синтетический SVG-пример: рисует ряд свечей под архетип семейства стратегии,
 * накладывает линию (например, EMA) и помечает вход. Чисто иллюстративно.
 */
function drawStrategyExampleSVG(s) {
  const W = 720, H = 240, PAD = 24;
  const N = 36;
  // Семейные генераторы цены (детерминированные, чтобы пример не "прыгал")
  function gen() {
    const rng = (function (seed) {
      let x = seed | 0; return () => { x = (x * 9301 + 49297) % 233280; return x / 233280; };
    })((s.key || 'x').split('').reduce((a, c) => a + c.charCodeAt(0), 0));
    const arr = [];
    let p = 100;
    for (let i = 0; i < N; i++) {
      let drift = 0;
      switch (s.family) {
        case 'candle':
          // Затухание тренда → разворотная свеча → откат
          drift = (i < N * 0.50 ? -0.5 : i < N * 0.56 ? -0.05 : 0.6);
          break;
        case 'mean_revert':
          // Сильный отскок от средней: рост → шип вверх → возврат
          drift = (i < N * 0.45 ? 0.6 : i < N * 0.55 ? 1.6 : -1.0);
          break;
        case 'trend_follow':
          // Прямой uptrend с откатом ~середины
          drift = (i > N * 0.40 && i < N * 0.55) ? -0.6 : 0.55;
          break;
        case 'breakout':
          // Боковик → прорыв
          drift = (i < N * 0.62 ? (rng() - 0.5) * 0.5 : 1.1);
          break;
        case 'scalp':
          // Микро-импульсы вверх с короткими откатами
          drift = (i % 4 === 0 ? -0.4 : 0.35);
          break;
        case 'momentum':
          drift = Math.sin(i / 5) * 0.6 + 0.25;
          break;
        case 'hedge':
          drift = (rng() - 0.45) * 0.9;
          break;
        default:
          drift = (rng() - 0.5) * 0.8;
      }
      const open = p;
      p += drift + (rng() - 0.5) * 0.6;
      const close = p;
      const high = Math.max(open, close) + rng() * 0.5;
      const low  = Math.min(open, close) - rng() * 0.5;
      arr.push({ open, high, low, close });
    }
    return arr;
  }
  const data = gen();
  const minP = Math.min(...data.map(c => c.low));
  const maxP = Math.max(...data.map(c => c.high));
  const range = (maxP - minP) || 1;
  const cw = (W - PAD * 2) / N;
  const yOf = (p) => PAD + (1 - (p - minP) / range) * (H - PAD * 2);

  // EMA(9) для иллюстрации
  const ema = []; const k = 2 / (9 + 1);
  for (let i = 0; i < N; i++) {
    const c = data[i].close;
    ema.push(i === 0 ? c : ema[i-1] + k * (c - ema[i-1]));
  }

  let svg = `<svg class="strat-svg" viewBox="0 0 ${W} ${H}" preserveAspectRatio="none" xmlns="http://www.w3.org/2000/svg">`;
  // Фон-сетка
  for (let g = 1; g < 4; g++) {
    const y = PAD + (H - PAD * 2) * g / 4;
    svg += `<line x1="${PAD}" y1="${y}" x2="${W-PAD}" y2="${y}" stroke="rgba(120,120,120,0.10)" />`;
  }
  // Свечи
  for (let i = 0; i < N; i++) {
    const c = data[i];
    const x = PAD + i * cw + cw / 2;
    const up = c.close >= c.open;
    const col = up ? '#20B26C' : '#EF454A';
    svg += `<line x1="${x}" y1="${yOf(c.high)}" x2="${x}" y2="${yOf(c.low)}" stroke="${col}" stroke-width="1" />`;
    const yo = yOf(c.open), yc = yOf(c.close);
    const top = Math.min(yo, yc), height = Math.max(2, Math.abs(yo - yc));
    svg += `<rect x="${x - cw*0.35}" y="${top}" width="${cw*0.7}" height="${height}" fill="${col}" />`;
  }
  // EMA линия
  let path = '';
  for (let i = 0; i < N; i++) {
    const x = PAD + i * cw + cw / 2;
    path += (i ? ' L ' : 'M ') + x.toFixed(1) + ' ' + yOf(ema[i]).toFixed(1);
  }
  svg += `<path d="${path}" fill="none" stroke="#F7A600" stroke-width="1.5" />`;

  // Точка входа: семейно-зависимая
  let entryIdx = Math.floor(N * 0.55);
  if (s.family === 'mean_revert')  entryIdx = Math.floor(N * 0.55);
  if (s.family === 'trend_follow') entryIdx = Math.floor(N * 0.50);
  if (s.family === 'breakout')     entryIdx = Math.floor(N * 0.66);
  if (s.family === 'scalp')        entryIdx = Math.floor(N * 0.40);
  if (s.family === 'momentum')     entryIdx = Math.floor(N * 0.55);
  if (s.family === 'candle')       entryIdx = Math.floor(N * 0.55);
  const ex = PAD + entryIdx * cw + cw / 2;
  const ec = data[entryIdx].close;
  // Для свечных и mean-revert — пример SELL у вершины; для остальных — BUY.
  const isSell = (s.family === 'mean_revert');
  const arrowY = isSell ? yOf(ec) - 14 : yOf(ec) + 14;
  const aColor = isSell ? '#EF454A' : '#20B26C';
  const arrow  = isSell
    ? `M ${ex} ${arrowY-8} L ${ex-6} ${arrowY+2} L ${ex+6} ${arrowY+2} Z`
    : `M ${ex} ${arrowY+8} L ${ex-6} ${arrowY-2} L ${ex+6} ${arrowY-2} Z`;
  svg += `<path d="${arrow}" fill="${aColor}" />`;
  svg += `<text x="${ex + 10}" y="${arrowY + 4}" fill="${aColor}" font-size="11" font-family="Inter, sans-serif" font-weight="600">${isSell ? 'SELL' : 'BUY'}</text>`;

  // Подпись TF справа сверху
  svg += `<text x="${W - PAD}" y="${PAD - 4}" text-anchor="end" fill="rgba(255,255,255,0.45)" font-size="10" font-family="JetBrains Mono, monospace">${escapeHtml(s.timeframe)} • ${escapeHtml(s.family)}</text>`;
  svg += `</svg>`;
  return svg;
}

// ─── Role-based visibility & auth bindings ────────────────────────
function applyRoleVisibility() {
  const admin = isAdmin();
  document.querySelectorAll('.admin-only').forEach(el => {
    el.style.display = admin ? '' : 'none';
  });
  const nameEl = document.getElementById('user-name');
  const roleEl = document.getElementById('user-role');
  if (nameEl && AUTH_USER) nameEl.textContent = AUTH_USER.username;
  if (roleEl && AUTH_USER) {
    roleEl.textContent = admin ? 'admin' : 'user';
    roleEl.classList.toggle('is-admin', admin);
  }
}

// ─── Users tab (admin only) ───────────────────────────────────────
async function loadUsers() {
  try {
    const r = await fetch('/api/users');
    if (!r.ok) return;
    const d = await r.json();
    state.users = d.users || [];
    renderUsers();
  } catch {}
}

function renderUsers() {
  const box = document.getElementById('users-table');
  if (!box) return;
  const users = state.users || [];
  if (!users.length) {
    box.innerHTML = '<div style="color:var(--text-muted);padding:16px">Нет пользователей</div>';
    return;
  }
  const rows = users.map(u => {
    const isSelf = AUTH_USER && u.username === AUTH_USER.username;
    return `
      <tr>
        <td class="st-name">${escapeHtml(u.username)}</td>
        <td><span class="st-state ${u.role === 'admin' ? 'is-on' : 'is-off'}">${u.role}</span></td>
        <td style="color:var(--text-muted);font-size:11.5px">${(u.created_at||'').substring(0,10)}</td>
        <td class="st-actions">
          <button class="btn-ghost" title="Сменить пароль" onclick="changeUserPassword('${escapeHtml(u.username)}')">🔑</button>
          <button class="btn-ghost" title="Сменить роль" onclick="toggleUserRole('${escapeHtml(u.username)}', '${u.role}')">${u.role === 'admin' ? '▼' : '▲'}</button>
          <button class="btn-ghost btn-danger" title="${isSelf ? 'Нельзя удалить себя' : 'Удалить'}" ${isSelf ? 'disabled' : ''} onclick="deleteUser('${escapeHtml(u.username)}')">✕</button>
        </td>
      </tr>
    `;
  }).join('');
  box.innerHTML = `
    <table class="streams-grid">
      <thead>
        <tr>
          <th>Логин</th>
          <th>Роль</th>
          <th>Создан</th>
          <th></th>
        </tr>
      </thead>
      <tbody>${rows}</tbody>
    </table>
  `;
}

function openUserForm() {
  const wrap = document.getElementById('user-form-wrap');
  if (!wrap) return;
  wrap.hidden = false;
  wrap.innerHTML = `
    <div class="stream-form">
      <div class="stream-form-title">Новый пользователь</div>
      <div class="bt-form">
        <label>Логин
          <input id="uf-username" type="text" style="width:160px">
        </label>
        <label>Пароль
          <input id="uf-password" type="password" style="width:160px">
        </label>
        <label>Роль
          <select id="uf-role">
            <option value="user" selected>user</option>
            <option value="admin">admin</option>
          </select>
        </label>
        <button class="btn-primary" onclick="submitUserForm()">Создать</button>
        <button class="btn-ghost btn-ghost-lg" onclick="closeUserForm()">Отмена</button>
        <span id="uf-error" class="sf-error"></span>
      </div>
    </div>
  `;
  setTimeout(() => document.getElementById('uf-username')?.focus(), 50);
}

function closeUserForm() {
  const wrap = document.getElementById('user-form-wrap');
  if (wrap) { wrap.hidden = true; wrap.innerHTML = ''; }
}

async function submitUserForm() {
  const body = {
    username: document.getElementById('uf-username').value.trim(),
    password: document.getElementById('uf-password').value,
    role:     document.getElementById('uf-role').value,
  };
  const errEl = document.getElementById('uf-error');
  errEl.textContent = '';
  try {
    const r = await fetch('/api/users', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
    const d = await r.json();
    if (!r.ok) {
      errEl.textContent = d.detail || 'Ошибка';
      return;
    }
    closeUserForm();
    await loadUsers();
  } catch (e) { errEl.textContent = 'Сеть недоступна'; }
}

async function changeUserPassword(username) {
  const newPw = prompt(`Новый пароль для ${username} (минимум 6 символов):`);
  if (!newPw) return;
  const r = await fetch(`/api/users/${encodeURIComponent(username)}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ password: newPw }),
  });
  if (!r.ok) {
    const d = await r.json().catch(() => ({}));
    alert(d.detail || 'Ошибка смены пароля');
    return;
  }
  await loadUsers();
}

async function toggleUserRole(username, currentRole) {
  const newRole = currentRole === 'admin' ? 'user' : 'admin';
  if (!confirm(`Сменить роль ${username}: ${currentRole} → ${newRole}?`)) return;
  const r = await fetch(`/api/users/${encodeURIComponent(username)}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ role: newRole }),
  });
  if (!r.ok) {
    const d = await r.json().catch(() => ({}));
    alert(d.detail || 'Ошибка смены роли');
    return;
  }
  await loadUsers();
}

async function deleteUser(username) {
  if (!confirm(`Удалить пользователя ${username}?`)) return;
  const r = await fetch(`/api/users/${encodeURIComponent(username)}`, { method: 'DELETE' });
  if (!r.ok) {
    const d = await r.json().catch(() => ({}));
    alert(d.detail || 'Ошибка удаления');
    return;
  }
  await loadUsers();
}

// ─── Calculator ───────────────────────────────────────────────────
async function calcLoadSymbols() {
  try {
    const r = await fetch('/api/symbols');
    const d = await r.json();
    const sel = document.getElementById('calc-symbol');
    if (!sel) return;
    const symbols = d.symbols || [];
    sel.innerHTML = symbols.map(s => `<option value="${escapeHtml(s)}">${escapeHtml(s)}</option>`).join('');
    if (symbols.includes('EURUSDrfd')) sel.value = 'EURUSDrfd';
    else if (symbols.includes('XAUUSDrfd')) sel.value = 'XAUUSDrfd';
  } catch (e) {
    console.error('calcLoadSymbols', e);
  }
}

async function calcRun() {
  const out = document.getElementById('calc-result');
  if (!out) return;
  const symbol  = document.getElementById('calc-symbol')?.value;
  const deposit = parseFloat(document.getElementById('calc-deposit').value);
  const pct     = parseFloat(document.getElementById('calc-pct').value);

  if (!symbol || !(deposit > 0) || !(pct > 0)) {
    out.innerHTML = '<div class="card" style="color:var(--text-danger,#e66)">Заполните все поля корректно (положительные значения)</div>';
    return;
  }

  out.innerHTML = '<div class="card" style="color:var(--text-muted)">Расчёт...</div>';
  try {
    const url = `/api/calc/safe_volume?symbol=${encodeURIComponent(symbol)}`
              + `&deposit=${deposit}&pct=${pct}`;
    const r = await fetch(url);
    const d = await r.json();
    if (!r.ok) {
      out.innerHTML = `<div class="card" style="color:var(--text-danger,#e66)">Ошибка: ${escapeHtml(d.detail || r.statusText)}</div>`;
      return;
    }
    calcRender(d);
  } catch (e) {
    out.innerHTML = `<div class="card" style="color:var(--text-danger,#e66)">Сбой запроса: ${escapeHtml(String(e))}</div>`;
  }
}

function calcRender(d) {
  const out = document.getElementById('calc-result');
  if (!out) return;
  const fmt = (n, p=2) => (typeof n === 'number' && isFinite(n)) ? n.toFixed(p) : '—';

  let warn = '';
  if (d.reason === 'below_volume_min') {
    warn += `<div style="margin-top:12px;padding:10px 12px;background:rgba(230,80,80,0.10);border-left:3px solid #e65050;border-radius:4px;font-size:12.5px">
      «Сырой» объём (<b>${fmt(d.raw_volume, 4)}</b>) меньше минимального лота (${d.volume_min}).
      Увеличьте депозит или процент.
    </div>`;
  } else if (d.reason === 'capped_to_volume_max') {
    warn += `<div style="margin-top:12px;padding:10px 12px;background:rgba(230,180,40,0.08);border-left:3px solid #e6b428;border-radius:4px;font-size:12.5px">
      Расчётный объём превысил максимальный (${d.volume_max}) и был обрезан.
    </div>`;
  }

  // Подсказки по SL: какая будет потеря при типичных значениях SL в пунктах
  const slGrid = [10, 20, 50, 100, 200, 500];
  const slRows = slGrid.map(n => {
    const loss = d.pip_value_for_trade * n;
    const dd   = (loss / d.deposit) * 100;
    return `<tr><td style="padding:3px 10px">${n}</td>
                <td style="padding:3px 10px;text-align:right">${fmt(loss, 2)} USD</td>
                <td style="padding:3px 10px;text-align:right;color:var(--text-muted)">${fmt(dd, 2)} %</td></tr>`;
  }).join('');

  out.innerHTML = `
    <div class="card">
      <div class="card-title">${escapeHtml(d.symbol)} — результат</div>
      <div class="stats-grid">
        <div class="stat-box">
          <div class="stat-label">Объём сделки</div>
          <div class="stat-value">${fmt(d.volume, 2)} лот</div>
        </div>
        <div class="stat-box">
          <div class="stat-label">Стоимость 1 пункта</div>
          <div class="stat-value">${fmt(d.pip_value_for_trade, 2)} USD</div>
        </div>
        <div class="stat-box">
          <div class="stat-label">Плечо</div>
          <div class="stat-value">1:${d.leverage}</div>
        </div>
        <div class="stat-box">
          <div class="stat-label">Маржа MT5</div>
          <div class="stat-value">${d.margin_mt5 !== null ? fmt(d.margin_mt5, 2) + ' ' + escapeHtml(d.account_currency || '') : '—'}</div>
        </div>
      </div>

      <div style="margin-top:16px;display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:14px;font-size:12.5px;line-height:1.7">
        <div>
          <div style="color:var(--text-muted);margin-bottom:4px"><b>Расчёт объёма</b></div>
          <div>Депозит × % = ${fmt(d.deposit, 2)} × ${fmt(d.pct, 2)}/100 = <b>${fmt(d.margin_share, 2)}</b> USD</div>
          <div>÷ цена (ask) = ${fmt(d.margin_share, 2)} ÷ ${fmt(d.ask, d.digits)} = <b>${fmt(d.margin_share / d.ask, 4)}</b></div>
          <div>× плечо = × ${d.leverage} = <b>${fmt(d.margin_share / d.ask * d.leverage, 2)}</b></div>
          <div>÷ contract_size (${d.contract_size}) = <b>${fmt(d.raw_volume, 4)}</b> лот</div>
          <div>Округлено к шагу ${d.volume_step} → <b>${fmt(d.volume, 2)}</b> лот</div>
        </div>
        <div>
          <div style="color:var(--text-muted);margin-bottom:4px"><b>Стоимость 1 пункта</b></div>
          <div>На 1 лот: <b>${fmt(d.pip_value_per_lot_usd, 4)}</b> USD/пункт</div>
          <div>На ${fmt(d.volume, 2)} лот: <b>${fmt(d.pip_value_for_trade, 2)}</b> USD/пункт</div>
          <div style="color:var(--text-muted);font-size:11.5px">метод: ${escapeHtml(d.pip_method)}</div>
        </div>
        <div>
          <div style="color:var(--text-muted);margin-bottom:4px"><b>Параметры</b></div>
          <div>Цена ask: ${fmt(d.ask, d.digits)} &nbsp; Point: ${d.point}</div>
          <div>Contract: ${d.contract_size}</div>
          <div>Base/Profit: ${escapeHtml(d.currency_base || '?')}/${escapeHtml(d.currency_profit || '?')}</div>
          <div>Lot: ${d.volume_min} … ${d.volume_max} (шаг ${d.volume_step})</div>
        </div>
      </div>

      <div class="card-title" style="margin-top:18px;font-size:13px">Подсказка по стоп-лоссу (для текущего объёма)</div>
      <table style="width:100%;font-size:12.5px;border-collapse:collapse;margin-top:6px">
        <thead>
          <tr style="color:var(--text-muted)">
            <th style="padding:3px 10px;text-align:left">SL, пунктов</th>
            <th style="padding:3px 10px;text-align:right">Потеря</th>
            <th style="padding:3px 10px;text-align:right">% от депозита</th>
          </tr>
        </thead>
        <tbody>${slRows}</tbody>
      </table>

      ${warn}
    </div>
  `;
}

// ─── Init ─────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  applyRoleVisibility();
  document.getElementById('btn-logout')?.addEventListener('click', logout);

  // Tabs
  document.querySelectorAll('.tab').forEach(t => {
    t.addEventListener('click', () => {
      switchTab(t.dataset.tab);
      if (t.dataset.tab === 'users' && isAdmin()) loadUsers();
      if (t.dataset.tab === 'calculator') calcLoadSymbols();
      if (t.dataset.tab === 'anomalies') Anomalies.onTabOpened();
    });
  });

  // Calculator
  document.getElementById('btn-calc-run')?.addEventListener('click', calcRun);

  // Backtest
  document.getElementById('btn-run-bt')?.addEventListener('click', runBacktest);
  document.getElementById('bt-start')?.addEventListener('change', toggleBarsVisibility);
  document.getElementById('bt-end')?.addEventListener('change', toggleBarsVisibility);
  populateBtSymbols();
  populateBtStrategies();

  // Trading streams
  loadStreams();

  // History period tabs
  document.querySelectorAll('#hist-period-tabs .hist-period-btn').forEach(b => {
    b.addEventListener('click', () => histSetPeriod(b.dataset.period));
  });
  document.getElementById('hist-symbol-filter')?.addEventListener('change', (e) => {
    histSetSymbol(e.target.value);
  });
  document.getElementById('hist-only-chart-symbol')?.addEventListener('change', (e) => {
    histOnlyChartSymbol = !!e.target.checked;
    // Если активен «только текущий», блокируем явный селект
    const sel = document.getElementById('hist-symbol-filter');
    if (sel) sel.disabled = histOnlyChartSymbol;
    histPage = 0;
    renderHistory();
  });

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

// ─── Anomalies module ─────────────────────────────────────────────
const Anomalies = (() => {
  'use strict';

  // ── State ──────────────────────────────────────────────────────
  const _state = {
    active: new Map(),      // symbol → anomaly object
    historyOffset: 0,
    historyExhausted: false,
    filters: { symbol: '', type: '', period: '' },
  };

  const HISTORY_LIMIT = 50;

  // ── Helpers ────────────────────────────────────────────────────
  function _fmtNum(v, dec) {
    if (v == null || v === '') return '—';
    return Number(v).toLocaleString('ru-RU', {
      minimumFractionDigits: dec ?? 2,
      maximumFractionDigits: dec ?? 2,
    });
  }

  function _fmtTs(ts) {
    if (!ts) return '—';
    try {
      const d = new Date(ts);
      return d.toLocaleString('ru-RU', {
        day: '2-digit', month: '2-digit',
        hour: '2-digit', minute: '2-digit', second: '2-digit',
      });
    } catch { return ts; }
  }

  function _dirClass(types) {
    if (!types || types.length === 0) return '';
    const arr = Array.isArray(types) ? types : [types];
    const set = new Set(arr);
    const up   = set.has('EMA_FAR_UP')   || set.has('STOCH_OB');
    const down = set.has('EMA_FAR_DOWN') || set.has('STOCH_OS');
    if (up && down) return 'mixed';
    if (up)   return 'up';
    if (down) return 'down';
    return '';
  }

  function _periodToFrom(period) {
    if (!period) return null;
    const now = Date.now();
    const map = { '1h': 3600, '6h': 21600, '24h': 86400, '7d': 604800 };
    const sec = map[period];
    if (!sec) return null;
    return new Date(now - sec * 1000).toISOString();
  }

  // ── Render: cards ──────────────────────────────────────────────
  function _renderCards() {
    const grid = document.getElementById('anomaly-cards');
    if (!grid) return;
    if (_state.active.size === 0) {
      grid.innerHTML = '<div style="color:var(--text-muted);font-size:13px;padding:8px 0">Активных аномалий нет</div>';
      return;
    }
    // Sort: most recently opened first
    const sorted = Array.from(_state.active.values()).sort((a, b) => {
      return (b.opened_at || '') > (a.opened_at || '') ? 1 : -1;
    });
    grid.innerHTML = sorted.map(a => _cardHtml(a)).join('');
  }

  function _cardHtml(a) {
    const typesArr = Array.isArray(a.types) ? a.types : (a.types ? [a.types] : []);
    const dir = _dirClass(typesArr);
    return `<div class="anomaly-card ${dir}" data-symbol="${a.symbol}">
  <div class="ac-symbol">${a.symbol || '—'}</div>
  <div class="ac-types">${typesArr.join(', ') || '—'}</div>
  <div class="ac-row"><span>Цена</span><span>${_fmtNum(a.price)}</span></div>
  <div class="ac-row"><span>EMA50</span><span>${_fmtNum(a.ema50)}</span></div>
  <div class="ac-row"><span>ATR</span><span>${_fmtNum(a.atr)}</span></div>
  <div class="ac-row"><span>Dist/ATR</span><span>${_fmtNum(a.dist_atr)}</span></div>
  <div class="ac-row"><span>StochK</span><span>${_fmtNum(a.stoch_k, 1)}</span></div>
  <div class="ac-row"><span>StochD</span><span>${_fmtNum(a.stoch_d, 1)}</span></div>
  <div class="ac-time">Открыта: ${_fmtTs(a.opened_at)}</div>
</div>`;
  }

  function _updateBadge() {
    const badge = document.getElementById('anomalies-badge');
    const count = document.getElementById('anomaly-active-count');
    const n = _state.active.size;
    if (badge) {
      badge.textContent = n;
      badge.classList.toggle('hidden', n === 0);
    }
    if (count) count.textContent = n;
  }

  // ── Render: history rows ───────────────────────────────────────
  function _historyRowHtml(item) {
    const typesArr = Array.isArray(item.types) ? item.types : (item.types ? [item.types] : []);
    const typesHtml = typesArr.map(t => `<span class="type-badge">${t}</span>`).join(' ');
    return `<tr>
  <td>${item.symbol || '—'}</td>
  <td>${typesHtml || '—'}</td>
  <td>${_fmtNum(item.price)}</td>
  <td>${_fmtNum(item.ema50)}</td>
  <td>${_fmtNum(item.atr)}</td>
  <td>${_fmtNum(item.dist_atr)}</td>
  <td>${_fmtNum(item.stoch_k, 1)}</td>
  <td>${_fmtNum(item.stoch_d, 1)}</td>
  <td>${_fmtTs(item.opened_at)}</td>
  <td>${_fmtTs(item.closed_at)}</td>
</tr>`;
  }

  // ── API calls ──────────────────────────────────────────────────
  async function loadActive() {
    try {
      const r = await fetch('/api/anomalies/active');
      if (!r.ok) return;
      const items = await r.json();
      _state.active.clear();
      (Array.isArray(items) ? items : (items.items || [])).forEach(a => {
        _state.active.set(a.symbol, a);
      });
      _renderCards();
      _updateBadge();
    } catch (e) {
      console.warn('[Anomalies] loadActive error:', e);
    }
  }

  async function loadHistory(append) {
    if (!append) {
      _state.historyOffset = 0;
      _state.historyExhausted = false;
    }
    if (_state.historyExhausted) return;

    const f = _state.filters;
    const params = new URLSearchParams({
      limit: HISTORY_LIMIT,
      offset: _state.historyOffset,
    });
    if (f.symbol)  params.set('symbol', f.symbol);
    if (f.type)    params.set('type',   f.type);
    const from = _periodToFrom(f.period);
    if (from)      params.set('from_',  from);

    try {
      const r = await fetch(`/api/anomalies/history?${params}`);
      if (!r.ok) return;
      const data = await r.json();
      const items = Array.isArray(data) ? data : (data.items || []);
      const tbody = document.getElementById('anomaly-history-body');
      if (tbody) {
        if (!append) tbody.innerHTML = '';
        items.forEach(item => {
          tbody.insertAdjacentHTML('beforeend', _historyRowHtml(item));
        });
      }
      _state.historyOffset += items.length;
      if (items.length < HISTORY_LIMIT) {
        _state.historyExhausted = true;
      }
      const btn = document.getElementById('anomaly-load-more');
      if (btn) btn.style.display = _state.historyExhausted ? 'none' : '';
    } catch (e) {
      console.warn('[Anomalies] loadHistory error:', e);
    }
  }

  async function scanNow() {
    const btn = document.getElementById('anomaly-scan-now');
    if (btn) btn.disabled = true;
    try {
      const r = await fetch('/api/anomalies/scan', { method: 'POST' });
      const ts = new Date().toLocaleTimeString('ru-RU');
      const el = document.getElementById('anomaly-last-scan');
      if (el) el.textContent = ts;
      if (r.ok) {
        // Reload active after short delay to let backend process
        setTimeout(loadActive, 600);
      }
    } catch (e) {
      console.warn('[Anomalies] scanNow error:', e);
    } finally {
      if (btn) btn.disabled = false;
    }
  }

  // ── Tab opened ─────────────────────────────────────────────────
  function onTabOpened() {
    loadActive();
    loadHistory(false);
  }

  // ── WS event handler ───────────────────────────────────────────
  function onEventStream(ev) {
    const { type, payload } = ev;
    if (!payload) return;

    if (type === 'anomaly.opened' || type === 'anomaly.updated') {
      const sym = payload.symbol;
      if (!sym) return;
      const existing = _state.active.get(sym) || {};
      _state.active.set(sym, { ...existing, ...payload });
      _renderCards();
      _updateBadge();
    }

    if (type === 'anomaly.closed') {
      const sym = payload.symbol;
      if (sym) {
        _state.active.delete(sym);
        _renderCards();
        _updateBadge();
      }
      // Reload history page 1 to reflect newly closed anomaly
      loadHistory(false);
    }
  }

  // ── Filter change handler ──────────────────────────────────────
  function _onFilterChange() {
    _state.filters.symbol = document.getElementById('anomaly-filter-symbol')?.value || '';
    _state.filters.type   = document.getElementById('anomaly-filter-type')?.value   || '';
    _state.filters.period = document.getElementById('anomaly-filter-period')?.value || '';
    loadHistory(false);
  }

  // ── DOMContentLoaded bindings ──────────────────────────────────
  document.addEventListener('DOMContentLoaded', () => {
    document.getElementById('anomaly-scan-now')
      ?.addEventListener('click', scanNow);

    document.getElementById('anomaly-load-more')
      ?.addEventListener('click', () => loadHistory(true));

    document.getElementById('anomaly-filter-symbol')
      ?.addEventListener('change', _onFilterChange);
    document.getElementById('anomaly-filter-type')
      ?.addEventListener('change', _onFilterChange);
    document.getElementById('anomaly-filter-period')
      ?.addEventListener('change', _onFilterChange);
  });

  // ── Public API ──────────────────────────────────────────────────
  return { onTabOpened, onEventStream, loadActive, loadHistory, scanNow };
})();

// ===== Mobile bottom-bar navigation =====
const MobileNav = (() => {
  'use strict';

  function _syncActive(tabName) {
    document.querySelectorAll('.mtab').forEach(b => {
      b.classList.toggle('active', b.dataset.tab === tabName);
    });
  }

  // Обёртка switchTab: после переключения подсвечиваем нижнюю кнопку.
  const _origSwitchTab = window.switchTab;
  if (typeof _origSwitchTab === 'function') {
    window.switchTab = function(name) {
      _origSwitchTab(name);
      const inBar = ['positions', 'anomalies', 'calculator', 'backtest'].includes(name);
      _syncActive(inBar ? name : '__more');
    };
  }

  function bind() {
    document.querySelectorAll('.mtab').forEach(btn => {
      btn.addEventListener('click', () => {
        const t = btn.dataset.tab;
        if (t === '__more') {
          if (typeof MobileSheet !== 'undefined') MobileSheet.open();
          return;
        }
        window.switchTab(t);
        if (t === 'anomalies'  && typeof Anomalies !== 'undefined') Anomalies.onTabOpened();
        if (t === 'calculator' && typeof calcLoadSymbols === 'function') calcLoadSymbols();
      });
    });
    const activeTab = document.querySelector('.tab.active')?.dataset.tab || 'positions';
    _syncActive(['positions','anomalies','calculator','backtest'].includes(activeTab) ? activeTab : '__more');
  }

  document.addEventListener('DOMContentLoaded', bind);

  return { syncActive: _syncActive };
})();

// ===== Mobile "more" bottom-sheet =====
const MobileSheet = (() => {
  'use strict';

  function open() {
    const el = document.getElementById('more-sheet');
    if (!el) return;
    el.classList.remove('hidden');
    el.setAttribute('aria-hidden', 'false');
    document.body.style.overflow = 'hidden';
  }
  function close() {
    const el = document.getElementById('more-sheet');
    if (!el) return;
    el.classList.add('hidden');
    el.setAttribute('aria-hidden', 'true');
    document.body.style.overflow = '';
  }

  function bind() {
    const el = document.getElementById('more-sheet');
    if (!el) return;

    el.addEventListener('click', (e) => {
      if (e.target === el) close();
    });

    el.querySelectorAll('.sheet-item').forEach(it => {
      it.addEventListener('click', () => {
        const t = it.dataset.tab;
        window.switchTab(t);
        if (t === 'users' && typeof isAdmin === 'function' && isAdmin()
            && typeof loadUsers === 'function') {
          loadUsers();
        }
        close();
      });
    });

    document.addEventListener('keydown', (e) => {
      if (e.key === 'Escape' && !el.classList.contains('hidden')) close();
    });
  }

  document.addEventListener('DOMContentLoaded', bind);

  return { open, close };
})();
