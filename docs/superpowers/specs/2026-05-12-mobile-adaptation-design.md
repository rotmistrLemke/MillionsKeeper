# Спецификация: мобильная адаптация фронта (итерация 1)

**Дата:** 2026-05-12
**Ветка:** feature/scalping-strategies (или новая `feature/mobile-adaptation`)
**Статус:** утверждён к реализации

## Цель

Сделать дашборд MillionsKeeper удобным с телефона (узкий экран <768px). Эта спека покрывает **фундамент + 3 ключевые вкладки**: «Торговля» (Positions), «Индикаторы», «Аномалии». Остальные вкладки (Бэктест, Стратегии, Калькулятор, Лог событий, Пользователи) получают только базовое «не вылезает за экран» через фундамент; их детальная адаптация — отдельные итерации.

## Решения (зафиксированы в брейнсторме)

- Брейкпоинт: один — `<768px = mobile`, `≥768px = desktop`.
- Навигация на мобильном: **нижний tab-bar** из 5 кнопок: Торговля · Аномалии · Калькулятор · Бэктест · Ещё.
- «Ещё» — выезжающий снизу bottom-sheet с пунктами: Индикаторы · Стратегии · Лог событий · Пользователи (admin-only).
- Десктоп (≥768px) не трогаем — нулевая регрессия.
- CSS — отдельный файл `web/static/mobile.css`, всё в одном `@media (max-width: 767.98px) { … }`.
- Positions: таблица → карточки на мобильном.
- Индикаторы: график 60vh сверху + сетка индикаторов 1-колонкой снизу.
- Аномалии: 1-колоночная сетка карточек, фильтры в несколько строк.

## Архитектура

### Новый файл
- `web/static/mobile.css` — единственный новый файл со всеми мобильными правилами.

### Изменения в существующих файлах
- `web/static/index.html` —
  - подключить `mobile.css` после `style-bybit.css`;
  - добавить inline-SVG-спрайт с 5 иконками в начале `<body>`;
  - добавить `<nav class="mobile-tabbar">` в конец `<body>`;
  - добавить контейнер bottom-sheet `<div id="more-sheet">` (скрыт по умолчанию).
- `web/static/app.js` —
  - привязать клики на `.mtab` к существующему `switchTab()`;
  - реализовать bottom-sheet (open/close, esc, click-outside);
  - синхронизировать активный `.mtab` после `switchTab()`;
  - бейдж аномалий: модуль `Anomalies` обновляет оба элемента (`#anomalies-badge` и `#mtab-anomalies-badge`);
  - функция рендера позиций строит обе разметки (таблица + блок карточек) одновременно; CSS показывает нужную через `@media`.

### Нет изменений в backend
- Никаких API, схем БД, агентов, тестов на Python.

## Фундамент (`mobile.css` базовые правила)

Всё ниже находится внутри одного блока:
```css
@media (max-width: 767.98px) {
  /* ... */
}
```

```css
html { font-size: 15px; }
body { padding-bottom: 64px; }                 /* место под нижний tab-bar */
button, a, .tab, select, input[type="button"], input[type="submit"] {
  min-height: 44px; min-width: 44px;
}
input, select, textarea { font-size: 16px; }   /* iOS не зумит при focus */
.container, .pane, .content { padding: 12px; }
table { display: block; overflow-x: auto; max-width: 100%; }

/* Шапка ужимается */
.header, header { height: 48px; padding: 0 12px; }
.header .decoration, .header .subtitle { display: none; }

/* Верхняя горизонтальная лента табов — скрыта */
.tabs { display: none; }

/* Safe area под iPhone */
.mobile-tabbar { padding-bottom: env(safe-area-inset-bottom); }
```

Точные селекторы шапки уточняются по факту в `index.html` на этапе реализации.

## Нижний tab-bar

### HTML (в конец `<body>` `index.html`, ВНЕ `@media` — рендерится всегда, скрыт CSS-ом на десктопе)
```html
<nav class="mobile-tabbar" aria-label="Основная навигация">
  <button class="mtab" data-tab="positions">
    <svg class="mtab-icon"><use href="#i-trade"/></svg>
    <span>Торговля</span>
  </button>
  <button class="mtab" data-tab="anomalies">
    <svg class="mtab-icon"><use href="#i-bell"/></svg>
    <span>Аномалии</span>
    <span id="mtab-anomalies-badge" class="mtab-badge hidden">0</span>
  </button>
  <button class="mtab" data-tab="calculator">
    <svg class="mtab-icon"><use href="#i-calc"/></svg>
    <span>Калькулятор</span>
  </button>
  <button class="mtab" data-tab="backtest">
    <svg class="mtab-icon"><use href="#i-flask"/></svg>
    <span>Бэктест</span>
  </button>
  <button class="mtab" data-tab="__more">
    <svg class="mtab-icon"><use href="#i-more"/></svg>
    <span>Ещё</span>
  </button>
</nav>
```

### Иконки — один inline-SVG-спрайт в начале `<body>`
```html
<svg width="0" height="0" style="position:absolute" aria-hidden="true">
  <defs>
    <symbol id="i-trade"  viewBox="0 0 24 24"><path d="M3 17l6-6 4 4 8-8"  stroke="currentColor" fill="none" stroke-width="2"/></symbol>
    <symbol id="i-bell"   viewBox="0 0 24 24"><path d="M6 8a6 6 0 1112 0v5l2 3H4l2-3V8zM10 19a2 2 0 004 0" stroke="currentColor" fill="none" stroke-width="2"/></symbol>
    <symbol id="i-calc"   viewBox="0 0 24 24"><rect x="4" y="3" width="16" height="18" rx="2" stroke="currentColor" fill="none" stroke-width="2"/><path d="M8 7h8M7 12h2M11 12h2M15 12h2M7 16h2M11 16h2M15 16h2" stroke="currentColor" stroke-width="2"/></symbol>
    <symbol id="i-flask"  viewBox="0 0 24 24"><path d="M9 3h6v5l5 11a2 2 0 01-2 3H6a2 2 0 01-2-3l5-11V3z" stroke="currentColor" fill="none" stroke-width="2"/></symbol>
    <symbol id="i-more"   viewBox="0 0 24 24"><circle cx="6"  cy="12" r="1.5" fill="currentColor"/><circle cx="12" cy="12" r="1.5" fill="currentColor"/><circle cx="18" cy="12" r="1.5" fill="currentColor"/></symbol>
  </defs>
</svg>
```

### CSS (внутри `@media`)
```css
.mobile-tabbar {
  position: fixed; left: 0; right: 0; bottom: 0;
  z-index: 100; height: 56px;
  background: var(--surface1); border-top: 1px solid var(--border);
  display: flex;
}
.mtab {
  flex: 1; display: flex; flex-direction: column;
  align-items: center; justify-content: center;
  gap: 2px; background: none; border: none; color: var(--text-muted);
  font-size: 10px; padding: 6px 0;
  min-height: 44px; position: relative; cursor: pointer;
}
.mtab.active { color: var(--primary); }
.mtab-icon { width: 22px; height: 22px; }
.mtab-badge {
  position: absolute; top: 4px; right: 25%;
  min-width: 16px; height: 16px; padding: 0 4px;
  font-size: 10px; line-height: 16px; border-radius: 8px;
  background: var(--danger, #ea3943); color: #fff; text-align: center;
}
.mtab-badge.hidden { display: none; }
```

### CSS вне `@media` (скрывает панель на десктопе)
```css
.mobile-tabbar { display: none; }
@media (max-width: 767.98px) { .mobile-tabbar { display: flex; } }
```

### JS (`app.js`)
В блок инициализации (`DOMContentLoaded`, где уже привязываются `.tab` клики):
```javascript
// Mobile bottom tab-bar
document.querySelectorAll('.mtab').forEach(btn => {
  btn.addEventListener('click', () => {
    const t = btn.dataset.tab;
    if (t === '__more') { _openMoreSheet(); return; }
    switchTab(t);
    if (t === 'anomalies')  Anomalies.onTabOpened();
    if (t === 'calculator') calcLoadSymbols();
    if (t === 'users' && isAdmin()) loadUsers();
  });
});

// Подсветка активной кнопки — обёртка над switchTab
const _origSwitchTab = switchTab;
window.switchTab = function(name) {
  _origSwitchTab(name);
  document.querySelectorAll('.mtab').forEach(b => {
    b.classList.toggle('active', b.dataset.tab === name);
  });
};
```
Если в проекте `switchTab` объявлена как `function switchTab(...)` (не на window), используется альтернативный паттерн: после каждого `switchTab(name)` вызова в существующих хендлерах добавляем строку `_syncMobileTab(name)` через локальную функцию. Финальный выбор паттерна — на этапе реализации в зависимости от того, как `switchTab` объявлена (см. line 2765 в `app.js`).

## Bottom-sheet «Ещё»

### HTML (в конец `<body>`)
```html
<div id="more-sheet" class="sheet-backdrop hidden" aria-hidden="true">
  <div class="sheet" role="dialog" aria-label="Дополнительные вкладки">
    <div class="sheet-handle"></div>
    <button class="sheet-item" data-tab="indicators">Индикаторы</button>
    <button class="sheet-item" data-tab="strategies">Стратегии</button>
    <button class="sheet-item" data-tab="events">Лог событий</button>
    <button class="sheet-item admin-only" data-tab="users">Пользователи</button>
  </div>
</div>
```

### CSS (внутри `@media`)
```css
.sheet-backdrop {
  position: fixed; inset: 0; z-index: 200;
  background: rgba(0,0,0,0.5);
  display: flex; align-items: flex-end;
}
.sheet-backdrop.hidden { display: none; }
.sheet {
  width: 100%; background: var(--surface1);
  border-radius: 12px 12px 0 0; padding: 8px 0 16px;
  transform: translateY(100%); transition: transform 0.2s ease;
}
.sheet-backdrop:not(.hidden) .sheet { transform: translateY(0); }
.sheet-handle {
  width: 40px; height: 4px; margin: 8px auto 12px;
  background: var(--text-muted); opacity: 0.4; border-radius: 2px;
}
.sheet-item {
  display: block; width: 100%; padding: 14px 20px;
  background: none; border: none; color: var(--text);
  font-size: 15px; text-align: left; cursor: pointer;
  min-height: 44px;
}
.sheet-item:active { background: var(--surface2); }
```

### JS (`app.js`)
```javascript
function _openMoreSheet() {
  const sheet = document.getElementById('more-sheet');
  sheet.classList.remove('hidden');
  document.body.style.overflow = 'hidden';
}
function _closeMoreSheet() {
  const sheet = document.getElementById('more-sheet');
  sheet.classList.add('hidden');
  document.body.style.overflow = '';
}

document.getElementById('more-sheet')?.addEventListener('click', (e) => {
  if (e.target.id === 'more-sheet') _closeMoreSheet();
});
document.querySelectorAll('#more-sheet .sheet-item').forEach(it => {
  it.addEventListener('click', () => {
    const t = it.dataset.tab;
    switchTab(t);
    if (t === 'users' && isAdmin()) loadUsers();
    _closeMoreSheet();
  });
});
document.addEventListener('keydown', (e) => {
  if (e.key === 'Escape') _closeMoreSheet();
});
```

## Positions — карточки

### Рендер
Существующая функция рендера (точное имя — `renderPositions()` или эквивалент, уточняется при имплементации) строит ОБА варианта в DOM:
```html
<div class="positions-wrap">
  <table class="positions-table">…</table>
  <div class="positions-cards">
    <div class="pos-card" data-ticket="...">
      <div class="pos-card-row1">
        <span class="pos-symbol">EURUSDrfd</span>
        <span class="pos-type type-buy">BUY</span>
        <span class="pos-vol">0.10</span>
        <span class="pos-pl pl-pos">+12.45 USD</span>
      </div>
      <div class="pos-card-row2">
        <span class="pos-prices">1.08321 → 1.08445</span>
      </div>
      <div class="pos-card-row3">
        <span class="pos-sltp">SL 1.08100 · TP 1.08800</span>
      </div>
      <button class="pos-close-btn" data-ticket="...">Закрыть</button>
    </div>
  </div>
</div>
```

### CSS
```css
.positions-cards { display: none; }
@media (max-width: 767.98px) {
  .positions-table { display: none; }
  .positions-cards { display: flex; flex-direction: column; gap: 10px; }
  .pos-card {
    border: 1px solid var(--border); border-radius: 8px;
    padding: 12px; background: var(--surface2);
  }
  .pos-card-row1 {
    display: grid;
    grid-template-columns: 1fr auto auto 1fr;
    align-items: center; gap: 8px; margin-bottom: 6px;
  }
  .pos-symbol { font-weight: 600; }
  .pos-type {
    padding: 2px 8px; border-radius: 4px; font-size: 11px;
  }
  .type-buy  { background: rgba(22,199,132,0.18); color: #16c784; }
  .type-sell { background: rgba(234,57,67,0.18);  color: #ea3943; }
  .pos-pl { text-align: right; font-weight: 600; font-variant-numeric: tabular-nums; }
  .pl-pos { color: #16c784; }
  .pl-neg { color: #ea3943; }
  .pos-card-row2, .pos-card-row3 {
    font-size: 12px; color: var(--text-muted);
    font-family: var(--font-mono); margin-bottom: 4px;
  }
  .pos-close-btn {
    width: 100%; margin-top: 8px; min-height: 44px;
    background: var(--surface3, #2b3139); color: var(--text);
    border: 1px solid var(--border); border-radius: 6px;
    font-size: 14px; cursor: pointer;
  }
  .pos-close-btn:active { background: var(--danger, #ea3943); color: #fff; }
}
```

Обработчик `.pos-close-btn` использует тот же endpoint/функцию, что и текущая таблица — JS-логика не дублируется, только новый DOM-элемент привязывается к существующему handler по `data-ticket`.

## Indicators — график 60vh + 1-колоночная сетка

```css
@media (max-width: 767.98px) {
  .chart-wrapper, #chart, .chart-container {
    height: 60vh !important; min-height: 320px;
  }
  .ind-grid { grid-template-columns: 1fr !important; gap: 6px; }
  .ind-row { padding: 8px 10px; font-size: 12px; }
  .ind-symbol { width: auto; min-width: 80px; }
  .ind-badges { flex-wrap: wrap; }
}
```

Точный селектор для `lightweight-charts` контейнера — уточняется по `index.html` (может быть `.chart-wrapper`, `#chart-container` и т.п.); правило ставится на актуальный.

JS: lightweight-charts должен пересчитать ширину при ресайзе. Если в проекте уже есть `resizeObserver` или `window.addEventListener('resize', …)` для графика — менять ничего не нужно. Если нет — добавить в `chartModule` (выявляется при реализации):
```javascript
const ro = new ResizeObserver(() => {
  if (chart) chart.applyOptions({ width: container.clientWidth });
});
ro.observe(container);
```

## Anomalies — тонкая полировка

```css
@media (max-width: 767.98px) {
  .anomaly-grid { grid-template-columns: 1fr; }
  .anomaly-filters { flex-wrap: wrap; }
  .anomaly-filters .toolbar-select { flex: 1 1 100%; min-width: 0; }
  .anomaly-header { flex-wrap: wrap; font-size: 13px; gap: 12px; }
  .anomaly-table th, .anomaly-table td { padding: 4px 6px; font-size: 12px; }
}
```

JS — в модуле `Anomalies` функция `_updateBadge()` дополнительно обновляет `#mtab-anomalies-badge`:
```javascript
function _updateBadge() {
  const n = _state.active.size;
  for (const id of ['anomalies-badge', 'mtab-anomalies-badge']) {
    const el = document.getElementById(id);
    if (!el) continue;
    el.textContent = n;
    el.classList.toggle('hidden', n === 0);
  }
}
```

## Out-of-scope (явно)

- Свайп между вкладками (горизонтальный жест) — нет.
- PWA / Service Worker / push-нотификации — нет.
- Тёмная/светлая тема (выбор) — нет, остаётся текущая тёмная.
- Глубокая адаптация вкладок Бэктест/Стратегии/Калькулятор/Лог событий/Пользователи — следующие итерации; в этой спеке они получают только фундамент (не вылезают за viewport, шрифт ≥16px в формах).
- Landscape mode — работает «как-нибудь», не оптимизируется.
- Юнит-тесты — фича чисто визуальная, проверяется руками в DevTools и на реальном устройстве.

## Acceptance criteria

1. На любом устройстве шириной <768px виден нижний tab-bar с 5 кнопками; верхняя `.tabs` лента скрыта.
2. Клик по нижней кнопке переключает контент через `switchTab()`; активная кнопка визуально подсвечена.
3. Кнопка «Ещё» открывает sheet с 4 пунктами (Индикаторы/Стратегии/Лог событий/Пользователи), последний виден только админу. Клик по пункту переключает + закрывает sheet. Закрытие также по тапу-вне и по Esc.
4. Бейдж аномалий в нижней панели обновляется одновременно с верхним; при `active=0` оба скрыты.
5. На вкладке «Торговля» при <768 — карточки позиций, кнопка «Закрыть» ≥44px тапается.
6. На «Индикаторах» — график 60vh сверху, индикаторы 1-колоночной сеткой; график корректно меняет ширину при ротации/ресайзе.
7. На «Аномалиях» — карточки одной колонкой; фильтры разносятся в несколько строк; таблица истории скроллится горизонтально без выхода за экран.
8. Все `<input>/<select>` имеют шрифт ≥16px → iOS не зумит при фокусе.
9. На ≥768px фронт визуально идентичен текущему (зрительная проверка любых 3 вкладок).
10. Десктопное поведение `switchTab()` не сломано (клик по любой `.tab` работает как раньше).

## Зависимости

- Перед стартом — слить с main, ветка `feature/scalping-strategies` уже содержит фичу «Аномалии» (от которой эта спека зависит для пункта 4).
- Если вкладка «Аномалии» в работе у другого разработчика — синхронизировать.
