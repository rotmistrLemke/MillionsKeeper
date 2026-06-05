# Mobile Adaptation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Сделать дашборд MillionsKeeper удобным на телефоне (<768px): нижний tab-bar из 5 кнопок, bottom-sheet «Ещё», вертикальные карточки позиций, индикаторы 1-колонкой с графиком 60vh, мелкая полировка вкладки «Аномалии».

**Architecture:** Один новый CSS-файл `web/static/mobile.css` со всеми правилами внутри одного `@media (max-width: 767.98px) { ... }`, подключается ПОСЛЕ существующих CSS. JS-добавления (привязка `.mtab` к `switchTab`, bottom-sheet open/close, зеркалирование бейджа аномалий) приклеиваются к концу существующего `app.js`. Десктоп (≥768px) визуально не меняется.

**Tech Stack:** Plain HTML + vanilla JS + CSS (без новых зависимостей). lightweight-charts уже подключён и сам подхватывает resize через ResizeObserver.

**Spec:** [docs/superpowers/specs/2026-05-12-mobile-adaptation-design.md](../specs/2026-05-12-mobile-adaptation-design.md)

---

## File Structure

**Создаём:**
- `web/static/mobile.css` — все мобильные правила (фундамент + tab-bar + sheet + positions + indicators + anomalies).

**Модифицируем:**
- `web/static/index.html` — `<link rel="stylesheet" href="/static/mobile.css">`, inline-SVG-спрайт иконок, `<nav class="mobile-tabbar">`, `<div id="more-sheet">`.
- `web/static/app.js` — модуль `MobileNav` (IIFE в конец файла) с привязкой `.mtab`, синхронизация активного таба, bottom-sheet open/close. Точечный патч `Anomalies._updateBadge` (зеркало в `#mtab-anomalies-badge`).

**Не трогаем:** Python-код, существующие CSS-файлы, существующие функции JS (кроме одной маленькой правки в `Anomalies` модуле).

---

## Task 1: Фундамент — `mobile.css` skeleton + подключение

**Files:**
- Create: `web/static/mobile.css`
- Modify: `web/static/index.html` (добавить `<link>`)

- [ ] **Step 1: Создать `web/static/mobile.css`**

Create file with content:
```css
/* mobile.css — мобильная адаптация дашборда MillionsKeeper.
   Все правила внутри @media (max-width: 767.98px) — десктоп не трогается. */

/* === Фундамент === */
@media (max-width: 767.98px) {
  html { font-size: 15px; }
  body { padding-bottom: 64px; }   /* место под нижний tab-bar */

  /* Touch-цели ≥44px по Apple HIG / Material */
  button, .btn-primary, .btn-secondary, .btn-close,
  a.btn, select, input[type="button"], input[type="submit"] {
    min-height: 44px;
  }

  /* iOS не зумит инпуты при focus, если font-size ≥ 16px */
  input, select, textarea { font-size: 16px; }

  /* Контейнеры */
  .container, .content { padding: 12px; }

  /* Любая таблица в фолбэке — горизонтальный скролл, не вылезает */
  table { display: block; overflow-x: auto; max-width: 100%; }

  /* Верхняя горизонтальная лента табов — скрыта (заменяется нижним tab-bar) */
  .tabs { display: none !important; }

  /* Header ужимается */
  .header, header { padding: 8px 12px; }
}

/* === Нижний tab-bar (виден ТОЛЬКО на мобильном) === */
.mobile-tabbar { display: none; }
@media (max-width: 767.98px) {
  .mobile-tabbar { display: flex; }
}
```

- [ ] **Step 2: Подключить `mobile.css` в `index.html`**

В `web/static/index.html` найти строку с подключением `style-bybit.css` и добавить ПОСЛЕ неё (чтобы правила mobile.css имели приоритет в каскаде):

Read `web/static/index.html` строки 1–20, найти `<link rel="stylesheet" href="/static/style-bybit.css">` (или эквивалентный путь). Добавить следующей строкой:
```html
<link rel="stylesheet" href="/static/mobile.css">
```

- [ ] **Step 3: Визуальная проверка**

1. Запустить бота (`python main.py`) или открыть `web/static/index.html` локально через любой http-сервер.
2. Открыть Chrome DevTools → Toggle Device Toolbar (Ctrl+Shift+M) → выбрать iPhone 12 Pro (390×844).
3. Убедиться, что:
   - Верхняя лента `.tabs` исчезла.
   - Контент не вылезает за viewport (нет горизонтального скролла на странице целиком).
   - Шрифт чуть крупнее.
4. Переключиться обратно на «Responsive 1280×800» → лента табов и шрифт вернулись к десктопным.

- [ ] **Step 4: Commit**

```bash
git add web/static/mobile.css web/static/index.html
git commit -m "feat(mobile): фундамент — mobile.css + base rules (typography, touch, table fallback)"
```

---

## Task 2: SVG-спрайт иконок и HTML нижнего tab-bar

**Files:**
- Modify: `web/static/index.html`

- [ ] **Step 1: Добавить inline-SVG-спрайт**

В `web/static/index.html` сразу после открывающего `<body>` (первой строкой внутри body) добавить:
```html
  <!-- Иконки для mobile tab-bar -->
  <svg width="0" height="0" style="position:absolute" aria-hidden="true">
    <defs>
      <symbol id="i-trade" viewBox="0 0 24 24"><path d="M3 17l6-6 4 4 8-8" stroke="currentColor" fill="none" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></symbol>
      <symbol id="i-bell" viewBox="0 0 24 24"><path d="M6 8a6 6 0 0112 0v5l2 3H4l2-3V8zM10 19a2 2 0 004 0" stroke="currentColor" fill="none" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></symbol>
      <symbol id="i-calc" viewBox="0 0 24 24"><rect x="4" y="3" width="16" height="18" rx="2" stroke="currentColor" fill="none" stroke-width="2"/><path d="M8 7h8M7 12h2M11 12h2M15 12h2M7 16h2M11 16h2M15 16h2" stroke="currentColor" stroke-width="2" stroke-linecap="round"/></symbol>
      <symbol id="i-flask" viewBox="0 0 24 24"><path d="M9 3h6v5l5 11a2 2 0 01-2 3H6a2 2 0 01-2-3l5-11V3z" stroke="currentColor" fill="none" stroke-width="2" stroke-linejoin="round"/></symbol>
      <symbol id="i-more" viewBox="0 0 24 24"><circle cx="6" cy="12" r="1.5" fill="currentColor"/><circle cx="12" cy="12" r="1.5" fill="currentColor"/><circle cx="18" cy="12" r="1.5" fill="currentColor"/></symbol>
    </defs>
  </svg>
```

- [ ] **Step 2: Добавить tab-bar в конец `<body>`**

Найти закрывающий `</body>`. ПЕРЕД ним вставить:
```html
  <!-- Mobile bottom tab-bar -->
  <nav class="mobile-tabbar" aria-label="Основная навигация">
    <button class="mtab" data-tab="positions" type="button">
      <svg class="mtab-icon"><use href="#i-trade"/></svg>
      <span class="mtab-label">Торговля</span>
    </button>
    <button class="mtab" data-tab="anomalies" type="button">
      <svg class="mtab-icon"><use href="#i-bell"/></svg>
      <span class="mtab-label">Аномалии</span>
      <span id="mtab-anomalies-badge" class="mtab-badge hidden">0</span>
    </button>
    <button class="mtab" data-tab="calculator" type="button">
      <svg class="mtab-icon"><use href="#i-calc"/></svg>
      <span class="mtab-label">Калькулятор</span>
    </button>
    <button class="mtab" data-tab="backtest" type="button">
      <svg class="mtab-icon"><use href="#i-flask"/></svg>
      <span class="mtab-label">Бэктест</span>
    </button>
    <button class="mtab" data-tab="__more" type="button">
      <svg class="mtab-icon"><use href="#i-more"/></svg>
      <span class="mtab-label">Ещё</span>
    </button>
  </nav>
```

- [ ] **Step 3: Визуальная проверка**

Перезагрузить страницу. В DevTools Responsive ≥768 — tab-bar не виден. В iPhone 12 Pro — внизу видна нелейаутенная (пока без CSS) полоса с 5 кнопками. Иконки чёрные/без стилей — это нормально, оформление в следующем task.

- [ ] **Step 4: Commit**

```bash
git add web/static/index.html
git commit -m "feat(mobile): HTML каркас нижнего tab-bar + SVG-спрайт иконок"
```

---

## Task 3: CSS нижнего tab-bar + JS привязка

**Files:**
- Modify: `web/static/mobile.css`
- Modify: `web/static/app.js`

- [ ] **Step 1: Дописать CSS для tab-bar в `mobile.css`**

Append to `web/static/mobile.css`:
```css
/* === CSS нижнего tab-bar === */
@media (max-width: 767.98px) {
  .mobile-tabbar {
    position: fixed;
    left: 0; right: 0; bottom: 0;
    z-index: 100;
    height: 56px;
    background: var(--surface, #181a20);
    border-top: 1px solid var(--border, #2b3139);
    padding-bottom: env(safe-area-inset-bottom, 0);
  }
  .mtab {
    flex: 1;
    display: flex; flex-direction: column;
    align-items: center; justify-content: center;
    gap: 2px;
    background: none; border: none;
    color: var(--text-muted, #848e9c);
    font-size: 10px;
    padding: 6px 0;
    min-height: 44px;
    position: relative;
    cursor: pointer;
    -webkit-tap-highlight-color: transparent;
  }
  .mtab.active { color: var(--primary, #f0b90b); }
  .mtab-icon { width: 22px; height: 22px; }
  .mtab-label { line-height: 1; }
  .mtab-badge {
    position: absolute;
    top: 4px; right: 25%;
    min-width: 16px; height: 16px; padding: 0 4px;
    font-size: 10px; line-height: 16px;
    border-radius: 8px;
    background: var(--red, #ea3943); color: #fff;
    text-align: center;
    box-sizing: border-box;
  }
  .mtab-badge.hidden { display: none; }
}
```

- [ ] **Step 2: Добавить JS-модуль `MobileNav` в `app.js`**

Append to the END of `web/static/app.js`:
```javascript
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
      // Если активный таб не в нижней панели (indicators/strategies/events/users) —
      // подсвечиваем "Ещё" как ближайший контекст.
      const inBar = ['positions', 'anomalies', 'calculator', 'backtest'].includes(name);
      _syncActive(inBar ? name : '__more');
    };
  }

  function bind() {
    document.querySelectorAll('.mtab').forEach(btn => {
      btn.addEventListener('click', () => {
        const t = btn.dataset.tab;
        if (t === '__more') { MobileSheet.open(); return; }
        window.switchTab(t);
        // Триггерим существующие per-tab подгрузки, как это делает верхняя лента.
        if (t === 'anomalies'  && typeof Anomalies   !== 'undefined') Anomalies.onTabOpened();
        if (t === 'calculator' && typeof calcLoadSymbols === 'function') calcLoadSymbols();
      });
    });
    // Подсветить стартовый таб (после того как app.js уже вызвал switchTab('positions') в init).
    const activeTab = document.querySelector('.tab.active')?.dataset.tab || 'positions';
    _syncActive(['positions','anomalies','calculator','backtest'].includes(activeTab) ? activeTab : '__more');
  }

  document.addEventListener('DOMContentLoaded', bind);

  return { syncActive: _syncActive };
})();
```

Note: `MobileSheet` referenced here будет реализован в Task 4 — до тех пор клик по «Ещё» в консоли выдаст ReferenceError, но остальные 4 кнопки работают. После Task 4 всё интегрируется.

- [ ] **Step 3: Визуальная проверка**

В DevTools iPhone 12 Pro перезагрузить страницу. Убедиться:
- Tab-bar внизу выглядит как ожидается (тёмный фон, иконки серые, выбранная — жёлтая).
- При клике по «Торговля/Аномалии/Калькулятор/Бэктест» переключается контент И подсвечивается нижняя кнопка.
- Клик по «Ещё» — пока выдаёт ошибку в консоли (ReferenceError: MobileSheet) — это ожидаемо, исправим в Task 4.
- Десктопная версия (≥768) не изменилась.

- [ ] **Step 4: Commit**

```bash
git add web/static/mobile.css web/static/app.js
git commit -m "feat(mobile): CSS tab-bar + JS привязка к switchTab"
```

---

## Task 4: Bottom-sheet «Ещё»

**Files:**
- Modify: `web/static/index.html`
- Modify: `web/static/mobile.css`
- Modify: `web/static/app.js`

- [ ] **Step 1: Добавить HTML sheet в `index.html`**

Перед `</body>` (после `<nav class="mobile-tabbar">`) добавить:
```html
  <!-- Bottom-sheet "Ещё" -->
  <div id="more-sheet" class="sheet-backdrop hidden" aria-hidden="true">
    <div class="sheet" role="dialog" aria-label="Дополнительные вкладки">
      <div class="sheet-handle"></div>
      <button class="sheet-item" data-tab="indicators" type="button">Индикаторы</button>
      <button class="sheet-item" data-tab="strategies" type="button">Стратегии</button>
      <button class="sheet-item" data-tab="events" type="button">Лог событий</button>
      <button class="sheet-item admin-only" data-tab="users" type="button">Пользователи</button>
    </div>
  </div>
```

- [ ] **Step 2: Добавить CSS sheet в `mobile.css`**

Append to `web/static/mobile.css`:
```css
/* === Bottom-sheet "Ещё" === */
.sheet-backdrop { display: none; }
@media (max-width: 767.98px) {
  .sheet-backdrop {
    position: fixed; inset: 0; z-index: 200;
    background: rgba(0, 0, 0, 0.5);
    display: flex; align-items: flex-end;
  }
  .sheet-backdrop.hidden { display: none; }
  .sheet {
    width: 100%;
    background: var(--surface, #181a20);
    border-radius: 14px 14px 0 0;
    padding: 8px 0 calc(16px + env(safe-area-inset-bottom, 0));
    animation: sheet-slide-up 0.2s ease;
  }
  @keyframes sheet-slide-up {
    from { transform: translateY(100%); }
    to   { transform: translateY(0); }
  }
  .sheet-handle {
    width: 40px; height: 4px;
    margin: 6px auto 10px;
    background: var(--text-muted, #848e9c);
    opacity: 0.4;
    border-radius: 2px;
  }
  .sheet-item {
    display: block; width: 100%;
    padding: 14px 20px;
    background: none; border: none;
    color: var(--text, #eaecef);
    font-size: 15px; text-align: left;
    cursor: pointer;
    min-height: 44px;
  }
  .sheet-item:active { background: var(--surface2, #2b3139); }
}
```

- [ ] **Step 3: Реализовать `MobileSheet` в `app.js`**

Append to `web/static/app.js`:
```javascript
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

    // Тап вне sheet (по фону) закрывает.
    el.addEventListener('click', (e) => {
      if (e.target === el) close();
    });

    // Клик по пункту: переключить вкладку + закрыть.
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

    // Esc закрывает.
    document.addEventListener('keydown', (e) => {
      if (e.key === 'Escape' && !el.classList.contains('hidden')) close();
    });
  }

  document.addEventListener('DOMContentLoaded', bind);

  return { open, close };
})();
```

- [ ] **Step 4: Визуальная проверка**

В iPhone 12 Pro перезагрузить. Убедиться:
- Клик «Ещё» → выезжает sheet снизу с анимацией.
- В sheet 4 пункта (для admin) или 3 (для non-admin, существующий `applyRoleVisibility()` уже скрывает `.admin-only`).
- Клик по пункту → переключает контент → sheet закрывается.
- Тап вне sheet → закрывается.
- Esc → закрывается.
- Десктоп (≥768) не показывает sheet никогда.

- [ ] **Step 5: Commit**

```bash
git add web/static/index.html web/static/mobile.css web/static/app.js
git commit -m "feat(mobile): bottom-sheet 'Ещё' для вкладок не из tab-bar"
```

---

## Task 5: Positions — карточки на мобильном

**Files:**
- Modify: `web/static/mobile.css`

**Контекст:** функция `renderPositions()` ([web/static/app.js:669](../../web/static/app.js#L669)) уже рендерит каждую позицию как `<div class="pos-card">`. На десктопе CSS делает её `display: flex; align-items: center; gap: 20px` ([web/static/style.css:411-421](../../web/static/style.css#L411-L421)) — то есть карточка визуально выглядит как табличный ряд. На мобильном переопределяем CSS, чтобы получить настоящие вертикальные карточки. JS и DOM не трогаем.

- [ ] **Step 1: Дописать positions-секцию в `mobile.css`**

Append to `web/static/mobile.css`:
```css
/* === Positions: вертикальные карточки === */
@media (max-width: 767.98px) {
  .pos-card {
    display: grid;
    grid-template-columns: 1fr auto;
    grid-template-rows: auto auto auto auto;
    column-gap: 12px;
    row-gap: 4px;
    align-items: center;
    padding: 12px 14px 12px 16px;
    margin-bottom: 10px;
    width: 100%;
    box-sizing: border-box;
  }
  /* Раскладка:
     row1: symbol            | pnl
     row2: badge + volume    | (empty / spans)
     row3: meta (entry/SL)   | meta
     row4: close-btn (full width) */
  .pos-card > .pos-symbol {
    grid-row: 1; grid-column: 1;
    width: auto; font-size: 16px;
  }
  .pos-card > .pos-pnl {
    grid-row: 1; grid-column: 2;
    margin-left: 0; font-size: 17px; text-align: right;
  }
  .pos-card > div:nth-child(2) {   /* badge + volume container */
    grid-row: 2; grid-column: 1 / span 2;
    font-size: 12px;
  }
  .pos-card > .pos-meta {
    grid-row: 3; grid-column: 1 / span 2;
    font-size: 12px;
  }
  .pos-card > .pos-meta + .pos-meta {
    grid-row: 4; grid-column: 1 / span 2;
  }
  .pos-card .btn-close {
    grid-row: 5; grid-column: 1 / span 2;
    width: 100%; margin-top: 8px;
    padding: 10px;
    font-size: 14px;
    min-height: 44px;
  }
  /* Кнопка закрытия видна только админу — уже управляется existing .admin-only */
}
```

**Note:** в `renderPositions()` карточка содержит элементы в порядке: `.pos-symbol`, `<div>` (badge+volume), 2× `.pos-meta`, `.pos-pnl`, `.btn-close`. Сетка через `grid-row`/`grid-column` позиционирует каждый по нужному месту независимо от DOM-порядка. Селектор `.pos-card > div:nth-child(2)` нацелен на анонимный `<div>` со span'ами badge и volume.

- [ ] **Step 2: Визуальная проверка**

С реальными открытыми позициями (или с моковыми, если можно):
- На iPhone 12 Pro карточка позиции: symbol слева крупно, P/L справа крупно (цветной), под ним бейдж BUY/SELL + объём, далее два мета-ряда (вход, SL), кнопка «Закрыть» full-width внизу.
- Кнопка тапается всем пальцем (≥44px).
- При >1 позиции карточки идут вертикальным списком, между ними отступ ~10px.
- Десктоп: всё по-прежнему flex-row.

- [ ] **Step 3: Commit**

```bash
git add web/static/mobile.css
git commit -m "feat(mobile): вертикальные карточки позиций на узком экране"
```

---

## Task 6: Indicators — график 60vh + сетка 1 колонкой

**Files:**
- Modify: `web/static/mobile.css`

**Контекст:** график lightweight-charts живёт в `#chart-container` ([web/static/index.html:103](../../web/static/index.html#L103)), на десктопе фиксированная `height: 460px` ([web/static/style.css:547-555](../../web/static/style.css#L547-L555)). У графика уже есть `ResizeObserver` ([web/static/app.js:1911-1914](../../web/static/app.js#L1911-L1914)), который сам пересчитывает ширину/высоту при изменении CSS-размера. Поэтому JS трогать не надо.

- [ ] **Step 1: Дописать indicators-секцию в `mobile.css`**

Append to `web/static/mobile.css`:
```css
/* === Indicators: график 60vh + сетка 1-колонкой === */
@media (max-width: 767.98px) {
  .chart-container {
    height: 60vh;
    min-height: 320px;
  }

  /* Сетка индикаторов */
  .ind-grid {
    grid-template-columns: 1fr;
    gap: 6px;
  }
  .ind-row {
    padding: 8px 10px;
    font-size: 12px;
    gap: 8px;
  }
  .ind-symbol {
    width: auto;
    min-width: 80px;
    font-size: 12.5px;
  }
  .ind-badges {
    flex-wrap: wrap;
  }
}
```

- [ ] **Step 2: Визуальная проверка**

1. Переключиться на вкладку «Индикаторы» (через «Ещё» → «Индикаторы»).
2. В iPhone 12 Pro:
   - График занимает ~60% высоты экрана.
   - Свечи и метки читаемы, ширина 100%.
   - Pinch/scroll работают (lightweight-charts из коробки).
   - Ниже графика — индикаторы в одной колонке, каждый ряд занимает всю ширину.
3. Повернуть устройство (Ctrl+Shift+M → Rotate) → график пересчитывает размер.
4. Десктоп — график 460px, сетка как раньше.

- [ ] **Step 3: Commit**

```bash
git add web/static/mobile.css
git commit -m "feat(mobile): график 60vh + индикаторы 1-колонкой"
```

---

## Task 7: Anomalies — мобильная полировка + зеркало бейджа

**Files:**
- Modify: `web/static/mobile.css`
- Modify: `web/static/app.js` (точечно — функция `_updateBadge` модуля `Anomalies`)

**Контекст:** модуль `Anomalies` ([web/static/app.js:3389](../../web/static/app.js#L3389)) уже обновляет верхний бейдж `#anomalies-badge`. Нам нужно зеркалить значение в новый `#mtab-anomalies-badge`.

- [ ] **Step 1: Дописать anomalies-секцию в `mobile.css`**

Append to `web/static/mobile.css`:
```css
/* === Anomalies: мобильная полировка === */
@media (max-width: 767.98px) {
  .anomaly-grid {
    grid-template-columns: 1fr;
  }
  .anomaly-filters {
    flex-wrap: wrap;
  }
  .anomaly-filters .toolbar-select {
    flex: 1 1 100%;
    min-width: 0;
  }
  .anomaly-header {
    flex-wrap: wrap;
    font-size: 13px;
    gap: 12px;
  }
  .anomaly-table th,
  .anomaly-table td {
    padding: 4px 6px;
    font-size: 12px;
  }
}
```

- [ ] **Step 2: Найти и пропатчить `_updateBadge` в `Anomalies`**

Read `web/static/app.js` around line 3389 (start of Anomalies module). Найти функцию `_updateBadge` (или эквивалентную, обновляющую `#anomalies-badge`). Заменить тело функции на цикл по обоим ID:

Текущий вариант (примерный, точная форма может отличаться):
```javascript
function _updateBadge() {
  const n = _state.active.size;
  const el = document.getElementById('anomalies-badge');
  if (!el) return;
  el.textContent = n;
  el.classList.toggle('hidden', n === 0);
}
```

Заменить на:
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

Если в коде функция называется иначе (например, `updateBadge` без подчёркивания, или логика встроена в `repaintCards`), найти место, где пишется в `#anomalies-badge`, и продублировать запись для `#mtab-anomalies-badge` тем же способом.

- [ ] **Step 3: Визуальная проверка**

1. На вкладке «Аномалии» в iPhone 12 Pro:
   - Карточки — одной колонкой.
   - Фильтры (symbol/type/период) — каждый на отдельной строке, full-width.
   - Шапка («Активные: N · Последний скан: ... · ⟳ Сканировать») переносится по строкам.
   - Таблица истории скроллится горизонтально (фундамент даёт `display:block; overflow-x:auto` для всех `table`).
2. Если есть активные аномалии — бейдж на нижнем табе показывает то же число, что и наверху страницы; при `active=0` оба бейджа скрыты.
3. Если активных нет — открыть Network в DevTools и нажать `POST /api/anomalies/scan`; когда сервер вернёт результаты, бейджи синхронно обновляются.
4. Десктоп: всё как раньше.

- [ ] **Step 4: Commit**

```bash
git add web/static/mobile.css web/static/app.js
git commit -m "feat(mobile): полировка вкладки 'Аномалии' + зеркало бейджа в tab-bar"
```

---

## Task 8: Финальная приёмка

**Files:** —

- [ ] **Step 1: Полный walkthrough по acceptance criteria**

Сверить с [spec.md acceptance](../specs/2026-05-12-mobile-adaptation-design.md#acceptance-criteria):

1. На <768 виден нижний tab-bar, верхняя `.tabs` лента скрыта.
2. Клик по нижней кнопке переключает контент; активная кнопка подсвечена.
3. «Ещё» → sheet с 4 пунктами (admin) или 3 (non-admin); клик переключает + закрывает. Закрытие также по тапу-вне и Esc.
4. Бейдж аномалий в нижней панели обновляется одновременно с верхним; при `active=0` оба скрыты.
5. Карточки позиций вертикальные, кнопка «Закрыть» ≥44px.
6. Индикаторы: график 60vh, сетка 1-колоночная; график пересчитывает ширину при ротации.
7. Аномалии: карточки 1 колонкой, фильтры в несколько строк, таблица истории скроллится.
8. Инпуты не зумят iOS (font-size ≥ 16px).
9. На ≥768 фронт визуально идентичен — пройтись по 3-4 вкладкам и сверить с memory из прошлой сессии.
10. Десктопный `switchTab()` работает (клик по любой `.tab` на ≥768).

- [ ] **Step 2: Проверка на реальном устройстве**

Открыть бота с телефона по локальной сети (`http://<host-ip>:8080`). Залогиниться. Прокликать вкладки. Проверить, что:
- Tap targets кнопок ощущаются нормально (не мажут).
- Bottom-sheet выезжает плавно.
- Свайп страницы вверх/вниз не залипает на tab-bar.
- На iPhone safe-area работает (tab-bar не залезает под home indicator).

- [ ] **Step 3: Если найдены расхождения**

Открыть новый тикет/iteration. Не править прямо в текущей ветке без явного запроса пользователя.

- [ ] **Step 4: Финальный коммит-маркер (опционально)**

Если все criteria зелёные и нет дополнительных правок — никакого коммита не нужно. Если были мелкие правки по итогам walkthrough:
```bash
git add web/static/mobile.css
git commit -m "fix(mobile): мелкие правки по итогам ручной приёмки"
```

---

## Self-Review

**Spec coverage:**

| Spec раздел / acceptance | Покрыто в |
|---|---|
| Фундамент (typography, touch, table fallback, viewport) | Task 1 |
| Скрытие верхней `.tabs` ленты | Task 1 |
| Tab-bar HTML + SVG sprite | Task 2 |
| Tab-bar CSS + JS привязка к `switchTab` | Task 3 |
| Bottom-sheet «Ещё» (HTML/CSS/JS, esc, click-outside) | Task 4 |
| Positions cards | Task 5 |
| Indicators chart 60vh + 1-col grid + resize | Task 6 (resize уже есть, явно отмечено) |
| Anomalies polish + badge mirror | Task 7 |
| Acceptance criteria 1–10 | Task 8 |
| Out-of-scope (свайп, PWA, темы, прочие вкладки) | Не покрывается, как и заявлено в spec |

**Placeholder scan:**
- Нет «TBD»/«TODO»/«implement later».
- В Task 7 Step 2 есть «если функция называется иначе» — это исследовательский шаг с двумя точными альтернативными действиями, не плейсхолдер. Допустимо, потому что точная сигнатура функции `_updateBadge` была написана в Task 9 фичи «Аномалии» одним из субагентов и может отличаться по форме (но не по поведению) от того, что зафиксировано в моём контексте.

**Type/signature consistency:**
- `MobileNav` / `MobileSheet` — два независимых IIFE, экспортируют только `syncActive` / `open`/`close`. Перекрёстная ссылка: `MobileNav.bind()` вызывает `MobileSheet.open()` — Task 3 явно отмечает, что `MobileSheet` появится в Task 4 (упорядочена зависимость).
- `window.switchTab` overrride в Task 3 → используется в Task 4 (`MobileSheet` click handlers вызывают `window.switchTab(t)`).
- Бейдж IDs `#anomalies-badge` (существующий) + `#mtab-anomalies-badge` (новый из Task 2) — Task 7 явно обновляет оба.
- CSS-переменные (`--surface`, `--text-muted`, `--primary`, `--red`, `--text`) — все используются в `mobile.css` с fallback-значениями `var(--name, #hex)`, чтобы не зависеть от точного списка переменных в существующих файлах.
