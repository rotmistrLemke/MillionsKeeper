import json
from fastapi import APIRouter, HTTPException, Depends, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from typing import Optional

from core.agent_registry import registry
from core.event_bus import bus
from core.events import Event, EventType
import auth

router = APIRouter(prefix="/api")


# ──────────────────────────── Auth dependencies ───────────────────

_bearer = HTTPBearer(auto_error=False)


def get_current_user(
    creds: Optional[HTTPAuthorizationCredentials] = Depends(_bearer),
) -> auth.UserRecord:
    if creds is None or not creds.credentials:
        raise HTTPException(status_code=401, detail="Требуется авторизация")
    user = auth.user_from_token(creds.credentials)
    if user is None:
        raise HTTPException(status_code=401, detail="Недействительный токен")
    return user


def require_admin(user: auth.UserRecord = Depends(get_current_user)) -> auth.UserRecord:
    if user.role != auth.ROLE_ADMIN:
        raise HTTPException(status_code=403, detail="Требуются права администратора")
    return user


# ──────────────────────────── Auth endpoints ──────────────────────

class LoginRequest(BaseModel):
    username: str
    password: str


@router.post("/auth/login")
async def login(req: LoginRequest):
    user = auth.registry.verify_password(req.username, req.password)
    if user is None:
        raise HTTPException(status_code=401, detail="Неверный логин или пароль")
    token = auth.create_access_token(user.username, user.role)
    return {"token": token, "user": user.to_public()}


@router.get("/auth/me")
async def me(user: auth.UserRecord = Depends(get_current_user)):
    return {"user": user.to_public()}


# ──────────────────────────── Agents ──────────────────────────────

@router.get("/agents")
async def get_agents(user: auth.UserRecord = Depends(get_current_user)):
    return {"agents": registry.get_all_statuses()}


# ──────────────────────────── Account ─────────────────────────────

@router.get("/account")
async def get_account(user: auth.UserRecord = Depends(get_current_user)):
    try:
        from market_data_cache import cache
        info = cache.get_account_info()
        if info is None:
            return {"error": "MT5 не подключён"}
        return {
            "balance": round(info.balance, 2),
            "equity": round(info.equity, 2),
            "margin": round(info.margin, 2),
            "free_margin": round(info.margin_free, 2),
            "currency": info.currency,
        }
    except Exception as e:
        return {"error": str(e)}


# ──────────────────────────── Positions ───────────────────────────

@router.get("/positions")
async def get_positions(user: auth.UserRecord = Depends(get_current_user)):
    try:
        import MetaTrader5 as mt5
        positions = mt5.positions_get()
        if positions is None:
            return {"positions": []}
        result = []
        for p in positions:
            result.append({
                "ticket": p.ticket,
                "symbol": p.symbol,
                "type": "BUY" if p.type == mt5.ORDER_TYPE_BUY else "SELL",
                "volume": p.volume,
                "open_price": p.price_open,
                "sl": p.sl,
                "pnl": round(p.profit, 2),
                "open_time": int(p.time),
            })
        return {"positions": result}
    except Exception as e:
        return {"error": str(e)}


# ──────────────────────────── History ─────────────────────────────

@router.get("/history")
async def get_history(days: int = 1,
                      user: auth.UserRecord = Depends(get_current_user)):
    try:
        from history import History
        h = History()
        if days == 1:
            data = h.get_profit_today()
        elif days == 7:
            data = h.get_profit_this_week()
        elif days == 30:
            data = h.get_profit_this_month()
        else:
            data = h.get_profit_last_days(days)
        return {"history": data if isinstance(data, dict) else {"profit": data}}
    except Exception as e:
        return {"error": str(e)}


# ──────────────────────────── Candles (OHLCV) ────────────────────

@router.get("/candles")
async def get_candles(symbol: str, timeframe: str = "H1", bars: int = 500,
                      date_from: str | None = None, date_to: str | None = None,
                      user: auth.UserRecord = Depends(get_current_user)):
    try:
        import MetaTrader5 as mt5
        from datetime import datetime, timedelta
        tf_map = {
            "M1":  mt5.TIMEFRAME_M1,
            "M5":  mt5.TIMEFRAME_M5,
            "M15": mt5.TIMEFRAME_M15,
            "M30": mt5.TIMEFRAME_M30,
            "H1":  mt5.TIMEFRAME_H1,
            "H4":  mt5.TIMEFRAME_H4,
            "D1":  mt5.TIMEFRAME_D1,
        }
        tf = tf_map.get(timeframe.upper())
        if tf is None:
            raise HTTPException(status_code=400, detail=f"Unknown timeframe: {timeframe}")
        # Если задан явный диапазон — берём весь интервал; иначе последние N баров.
        if date_from and date_to:
            try:
                d_from = datetime.strptime(date_from, "%Y-%m-%d")
                # +1 день, чтобы включить date_to целиком
                d_to   = datetime.strptime(date_to,   "%Y-%m-%d") + timedelta(days=1)
            except ValueError as e:
                raise HTTPException(status_code=400, detail=f"Bad date: {e}")
            rates = mt5.copy_rates_range(symbol, tf, d_from, d_to)
        else:
            bars = max(50, min(int(bars), 5000))
            rates = mt5.copy_rates_from_pos(symbol, tf, 0, bars)
        if rates is None:
            return {"error": f"No data for {symbol}: {mt5.last_error()}"}
        info = mt5.symbol_info(symbol)
        digits = int(info.digits) if info else 5
        candles = [
            {
                "time":   int(r["time"]),
                "open":   float(r["open"]),
                "high":   float(r["high"]),
                "low":    float(r["low"]),
                "close":  float(r["close"]),
                "volume": float(r["tick_volume"]),
            }
            for r in rates
        ]
        return {
            "symbol":    symbol,
            "timeframe": timeframe.upper(),
            "digits":    digits,
            "candles":   candles,
        }
    except Exception as e:
        return {"error": str(e)}


@router.get("/symbols")
async def get_symbols(user: auth.UserRecord = Depends(get_current_user)):
    from settings import Dictionary
    return {"symbols": list(Dictionary.symbolTradingStatus.keys())}


# ──────────────────────────── Strategies catalog ─────────────────
# Меташаг: классифицируем стратегию по эвристическому семейству, чтобы
# фронт мог нарисовать соответствующий синтетический пример.
_STRATEGY_FAMILY_HINTS = {
    "mean_revert":   ["overstretch", "mean_revert", "fibonacci", "rejection"],
    "trend_follow":  ["pullback", "ema_cross", "triple", "phase", "combined"],
    "breakout":      ["donchian", "breakout", "sr_bounce"],
    "scalp":         ["scalp", "sar_adx", "stochastic"],
    "momentum":      ["macd", "cci", "rsi"],
    "hedge":         ["hedge", "inverse"],
}


def _family_for(key: str) -> str:
    k = key.lower()
    for fam, needles in _STRATEGY_FAMILY_HINTS.items():
        for n in needles:
            if n in k:
                return fam
    return "custom"


@router.get("/strategies")
async def list_strategies(user: auth.UserRecord = Depends(get_current_user)):
    """Возвращает каталог стратегий с описаниями (docstring) и параметрами."""
    import inspect
    from strategies import STRATEGIES

    items = []
    for key, cls in STRATEGIES.items():
        try:
            inst = cls()
        except Exception:
            inst = None
        mod_doc = (inspect.getmodule(cls).__doc__ or "").strip()
        cls_doc = (cls.__doc__ or "").strip()
        if cls_doc.startswith("Helper class"):
            cls_doc = ""
        # Параметры конструктора (для "Indicators inputs")
        params = []
        try:
            sig = inspect.signature(cls.__init__)
            for name, p in sig.parameters.items():
                if name == "self":
                    continue
                params.append({
                    "name":    name,
                    "default": p.default if p.default is not inspect._empty else None,
                    "kind":    str(p.kind),
                })
        except (TypeError, ValueError):
            pass

        items.append({
            "key":         key,
            "name":        getattr(cls, "name", key),
            "description": getattr(cls, "description", "") or "",
            "timeframe":   getattr(inst, "default_timeframe", None) or getattr(cls, "default_timeframe", "H1"),
            "indicators":  list(inst.indicator_columns()) if inst else [],
            "doc":         mod_doc or cls_doc or "(описание отсутствует)",
            "family":      _family_for(key),
        })

    items.sort(key=lambda x: (x["family"], x["key"]))
    return {"strategies": items}


# ──────────────────────────── Calculator ─────────────────────────
# Объём считается через ДОЛЮ ДЕПОЗИТА × ПЛЕЧО.
# Плечо для каждого инструмента читается из shoulders/marginal-USD.xlsx.
# Стоимость пункта рассчитывается по правилам:
#   - quote == USD  →  pip_value = 1 USD на 1 лот
#   - base  == USD  →  pip_value = 1 / current_price USD на 1 лот
#   - оба не USD    →  pip_value = baseUSD_price / current_pair_price USD на 1 лот

_BROKER_SUFFIX = "rfd"
_SHOULDERS_PATH = "shoulders/marginal-USD.xlsx"
_shoulders_cache = None  # dict: normalized_symbol -> int (leverage)


def _normalize_symbol(s: str) -> str:
    """EUR/USD → EURUSD, EURUSDrfd → EURUSD, eur/usd → EURUSD."""
    if not s:
        return ""
    s = s.upper().replace("/", "").replace(" ", "")
    if s.endswith(_BROKER_SUFFIX.upper()):
        s = s[: -len(_BROKER_SUFFIX)]
    return s


def _load_shoulders():
    """Читает xlsx один раз и возвращает {EURUSD: 32, XAUUSD: 20, ...}."""
    global _shoulders_cache
    if _shoulders_cache is not None:
        return _shoulders_cache
    import openpyxl
    table = {}
    wb = openpyxl.load_workbook(_SHOULDERS_PATH, data_only=True)
    ws = wb.active
    for row in ws.iter_rows(values_only=True):
        if not row or len(row) < 2:
            continue
        sym, lev = row[0], row[1]
        if not sym or not lev:
            continue
        sym_n = _normalize_symbol(str(sym))
        lev_s = str(lev).strip()
        # формат "1:32" или просто "32"
        if ":" in lev_s:
            try:
                value = int(lev_s.split(":")[1])
            except (ValueError, IndexError):
                continue
        else:
            try:
                value = int(float(lev_s))
            except ValueError:
                continue
        if sym_n and value > 0:
            table[sym_n] = value
    _shoulders_cache = table
    return table


def _pip_value_per_lot_usd(mt5, symbol: str, info, ask: float) -> tuple[float, str]:
    """
    Стоимость 1 пункта (минимальный point из MT5) на 1 лот в долларах США
    по правилам пользователя. Возвращает (pip_value_usd, описание_способа).
    """
    base   = (info.currency_base or "").upper()
    profit = (info.currency_profit or "").upper()
    contract = float(info.trade_contract_size)
    point    = float(info.point)

    # Стоимость пункта в валюте котировки на 1 лот (универсально)
    pip_in_quote = contract * point

    if profit == "USD":
        # quote = USD → стоимость в USD напрямую
        return pip_in_quote, "quote=USD"

    if base == "USD":
        # base = USD: пересчёт пункта из quote в USD
        # 1 quote_unit = 1/ask USD  →  pip_in_USD = pip_in_quote / ask
        if ask <= 0:
            raise HTTPException(status_code=503, detail="Нет цены для конверсии")
        return pip_in_quote / ask, f"base=USD, делим на цену пары {ask}"

    # Кросс — ни base, ни quote не USD. Нужна цена baseUSD.
    cross_sym = base + "USD" + _BROKER_SUFFIX
    cross_tick = mt5.symbol_info_tick(cross_sym)
    if cross_tick is None or cross_tick.ask <= 0:
        # Попробуем без суффикса
        alt = base + "USD"
        cross_tick = mt5.symbol_info_tick(alt)
        if cross_tick is None or cross_tick.ask <= 0:
            raise HTTPException(
                status_code=400,
                detail=f"Не нашли курс {base}/USD для конверсии пункта по {symbol}"
            )
        cross_sym = alt
    base_usd = float(cross_tick.ask)
    if ask <= 0:
        raise HTTPException(status_code=503, detail="Нет цены для конверсии")
    # 1 quote = base_usd / ask USD  →  pip_in_USD = pip_in_quote × base_usd / ask
    return pip_in_quote * base_usd / ask, f"кросс через {cross_sym}={base_usd}, ÷ {ask}"


@router.get("/calc/leverages")
async def get_leverages(user: auth.UserRecord = Depends(get_current_user)):
    """Список плечей из shoulders/marginal-USD.xlsx — для отладки."""
    try:
        return {"leverages": _load_shoulders()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/calc/safe_volume")
async def calc_safe_volume(symbol: str,
                           deposit: float,
                           pct: float,
                           user: auth.UserRecord = Depends(get_current_user)):
    """
    Расчёт по правилу пользователя:
      lot = deposit × pct/100 / ask × leverage / contract_size
      где contract_size — из спецификации символа (forex 100000, XAU 100, XAG 5000)
      Стоимость пункта = pip_value_USD_per_lot × lot   (в USD)

    Плечо берётся из shoulders/marginal-USD.xlsx по нормализованному символу.
    """
    try:
        import math
        import MetaTrader5 as mt5

        if deposit <= 0 or pct <= 0:
            raise HTTPException(status_code=400,
                                detail="deposit и pct должны быть > 0")

        # 1. Выбираем символ в Market Watch
        if not mt5.symbol_select(symbol, True):
            err = mt5.last_error()
            raise HTTPException(status_code=400,
                                detail=f"Не удалось выбрать {symbol}: {err}")

        info = mt5.symbol_info(symbol)
        if info is None:
            raise HTTPException(status_code=404, detail=f"Символ {symbol} не найден")

        tick = mt5.symbol_info_tick(symbol)
        if tick is None or tick.ask <= 0:
            raise HTTPException(status_code=503,
                                detail=f"Нет цены по {symbol}: {mt5.last_error()}")
        ask = float(tick.ask)

        # 2. Плечо из xlsx
        shoulders = _load_shoulders()
        sym_n = _normalize_symbol(symbol)
        leverage = shoulders.get(sym_n)
        if leverage is None:
            raise HTTPException(
                status_code=404,
                detail=f"Плечо для {symbol} (норм. {sym_n}) не найдено в {_SHOULDERS_PATH}"
            )

        # 3. Объём по формуле пользователя:
        #    lot = deposit × pct/100 / ask × leverage / contract_size
        contract = float(info.trade_contract_size)
        margin_share = deposit * pct / 100.0
        if ask <= 0:
            raise HTTPException(status_code=503, detail="Нулевая цена ask")
        if contract <= 0:
            raise HTTPException(status_code=500, detail="Нулевой contract_size")
        raw_volume = margin_share / ask * leverage / contract

        step    = float(info.volume_step) or 0.01
        vol_min = float(info.volume_min)
        vol_max = float(info.volume_max)

        volume = math.floor(raw_volume / step) * step
        volume = round(volume, 8)

        reason = None
        if volume < vol_min:
            volume = 0.0
            reason = "below_volume_min"
        elif volume > vol_max:
            volume = vol_max
            reason = "capped_to_volume_max"

        # 4. Стоимость пункта в USD
        pip_value_usd_per_lot, pip_method = _pip_value_per_lot_usd(mt5, symbol, info, ask)
        pip_value_for_trade = pip_value_usd_per_lot * volume

        # 5. Маржа MT5 (для сверки)
        margin_mt5 = None
        if volume > 0:
            m = mt5.order_calc_margin(mt5.ORDER_TYPE_BUY, symbol, volume, ask)
            if m is not None:
                margin_mt5 = float(m)

        acc = mt5.account_info()
        acc_currency = acc.currency if acc else ""

        return {
            "symbol":           symbol,
            "symbol_normalized": sym_n,
            "account_currency": acc_currency,
            "currency_base":    info.currency_base,
            "currency_profit":  info.currency_profit,

            "ask":           ask,
            "digits":        int(info.digits),
            "point":         float(info.point),
            "contract_size": contract,
            "leverage":      leverage,

            "deposit":       deposit,
            "pct":           pct,
            "margin_share":  round(margin_share, 2),

            "raw_volume":    round(raw_volume, 6),
            "volume":        volume,
            "volume_min":    vol_min,
            "volume_max":    vol_max,
            "volume_step":   step,

            "pip_value_per_lot_usd":  round(pip_value_usd_per_lot, 6),
            "pip_value_for_trade":    round(pip_value_for_trade, 4),
            "pip_method":             pip_method,

            "margin_mt5":    round(margin_mt5, 2) if margin_mt5 is not None else None,

            "reason": reason,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ──────────────────────────── Indicators ──────────────────────────

_DEFAULT_INDICATORS = [
    {"col": "ema8",        "label": "EMA8"},
    {"col": "ema21",       "label": "EMA21"},
    {"col": "macd_line",   "label": "MACD"},
    {"col": "macd_signal", "label": "Signal"},
    {"col": "macd_hist",   "label": "Hist"},
    {"col": "rsi",         "label": "RSI"},
    {"col": "atr",         "label": "ATR"},
]


def _compute_default_indicators(df):
    import talib
    close = df['close'].values.astype(float)
    high  = df['high'].values.astype(float)
    low   = df['low'].values.astype(float)
    df['ema8']  = talib.EMA(close, 8)
    df['ema21'] = talib.EMA(close, 21)
    macd, sig, hist = talib.MACD(close)
    df['macd_line']   = macd
    df['macd_signal'] = sig
    df['macd_hist']   = hist
    df['rsi'] = talib.RSI(close, 14)
    df['atr'] = talib.ATR(high, low, close, 14)
    return df


def _default_signal(row):
    """Лёгкий сигнал для default: EMA кросс + MACD знак + RSI зоны."""
    import math
    req = ['ema8', 'ema21', 'macd_line', 'macd_signal', 'rsi']
    for c in req:
        v = row.get(c)
        if v is None or (isinstance(v, float) and math.isnan(v)):
            return None
    if row['ema8'] > row['ema21'] and row['macd_line'] > row['macd_signal'] and 55 <= row['rsi'] <= 70:
        return "BUY"
    if row['ema8'] < row['ema21'] and row['macd_line'] < row['macd_signal'] and 30 <= row['rsi'] <= 45:
        return "SELL"
    return None


@router.get("/indicators")
async def get_indicators(symbol: str, timeframe: str = "H1", strategy: str = "default", bars: int = 500,
                         user: auth.UserRecord = Depends(get_current_user)):
    try:
        import math
        import MetaTrader5 as mt5
        import pandas as pd

        tf_map = {
            "M1":  mt5.TIMEFRAME_M1,  "M5":  mt5.TIMEFRAME_M5,
            "M15": mt5.TIMEFRAME_M15, "M30": mt5.TIMEFRAME_M30,
            "H1":  mt5.TIMEFRAME_H1,  "H4":  mt5.TIMEFRAME_H4,
            "D1":  mt5.TIMEFRAME_D1,
        }
        tf = tf_map.get(timeframe.upper())
        if tf is None:
            raise HTTPException(status_code=400, detail=f"Unknown timeframe: {timeframe}")

        bars = max(100, min(int(bars), 2000))
        rates = mt5.copy_rates_from_pos(symbol, tf, 0, bars)
        if rates is None or len(rates) == 0:
            return {"error": f"No data for {symbol}: {mt5.last_error()}"}

        df = pd.DataFrame(rates)
        df['time'] = pd.to_datetime(df['time'], unit='s')

        indicators = []
        signal_val = None
        is_flat = None
        strategy_lc = strategy.lower()

        if strategy_lc == "default":
            df = _compute_default_indicators(df)
            indicators = _DEFAULT_INDICATORS
            signal_val = _default_signal(df.iloc[-1])
        else:
            from strategies import STRATEGIES
            cls = STRATEGIES.get(strategy_lc)
            if cls is None:
                return {"error": f"Unknown strategy: {strategy}"}
            s = cls()
            df = s.compute_indicators(df)
            try:
                df = s.compute_flat_indicators(df)
            except Exception:
                pass
            cols = s.indicator_columns() or []
            indicators = [{"col": c, "label": c} for c in cols]
            try:
                signal_val = s.get_entry_signal(df.iloc[-1])
            except Exception:
                signal_val = None
            try:
                is_flat = bool(s.is_flat(df.iloc[-1]))
            except Exception:
                is_flat = None

        def _to_num(v):
            try:
                fv = float(v)
                if math.isnan(fv) or math.isinf(fv):
                    return None
                return fv
            except (TypeError, ValueError):
                return None

        last = df.iloc[-1]
        values = {}
        series = {}
        series_len = len(df)
        tail = df.tail(series_len)
        for ind in indicators:
            col = ind["col"]
            if col in df.columns:
                values[col] = _to_num(last[col])
                series[col] = [_to_num(v) for v in tail[col].tolist()]
            else:
                values[col] = None
                series[col] = []

        price = _to_num(last.get("close"))
        price_series = [_to_num(v) for v in tail["close"].tolist()]
        time_series = [int(t.timestamp()) for t in tail["time"].tolist()]

        return {
            "symbol":       symbol,
            "timeframe":    timeframe.upper(),
            "strategy":     strategy_lc,
            "indicators":   indicators,
            "values":       values,
            "series":       series,
            "price":        price,
            "price_series": price_series,
            "time_series":  time_series,
            "signal":       signal_val,
            "is_flat":      is_flat,
            "time":         int(df['time'].iloc[-1].timestamp()),
        }
    except HTTPException:
        raise
    except Exception as e:
        return {"error": str(e)}


# ──────────────────────────── Events ──────────────────────────────

@router.get("/events")
async def get_events(event_type: Optional[str] = None, limit: int = 50,
                     user: auth.UserRecord = Depends(get_current_user)):
    events = bus.get_recent_events(event_type=event_type, limit=limit)
    return {"events": [e.to_dict() for e in events]}


# ──────────────────────────── Trading control ─────────────────────

class TradingStatusRequest(BaseModel):
    symbol: str
    status: int  # 0=разрешена, 3=выключена


@router.post("/trading/status")
async def set_trading_status(req: TradingStatusRequest,
                             admin: auth.UserRecord = Depends(require_admin)):
    from settings import Dictionary
    if req.symbol not in Dictionary.symbolTradingStatus:
        raise HTTPException(status_code=404, detail=f"Символ {req.symbol} не найден")
    Dictionary.symbolTradingStatus[req.symbol] = req.status
    await bus.publish(Event(
        type=EventType.TRADING_STATUS_CHANGED,
        source="api",
        payload={"symbol": req.symbol, "status": req.status, "reason": "api_request"}
    ))
    return {"ok": True, "symbol": req.symbol, "status": req.status}


@router.get("/trading/status")
async def get_trading_status(user: auth.UserRecord = Depends(get_current_user)):
    from settings import Dictionary
    return {"status": Dictionary.symbolTradingStatus}


# ──────────────────────────── Active strategy ────────────────────

@router.get("/active_strategy")
async def get_active_strategy(user: auth.UserRecord = Depends(get_current_user)):
    from settings import GlobalValues, TF_REVERSE
    return {
        "strategy":  GlobalValues.active_strategy,
        "symbol":    GlobalValues.active_symbol,
        "timeframe": TF_REVERSE.get(GlobalValues.time_frame, "H1"),
        "volume":    GlobalValues.active_volume,
        "sl_atr":    GlobalValues.active_sl_atr,
        "tp_atr":    GlobalValues.active_tp_atr,
    }


# ──────────────────────────── Streams (мульти-поточная торговля) ──

class StreamCreateRequest(BaseModel):
    name: Optional[str] = None
    strategy: str = "default"
    symbol: str
    timeframe: str = "H1"
    volume: float = 0.0
    sl_atr: float = 0.0
    tp_atr: float = 0.0
    deposit: float = 0.0
    breakeven_atr: float = 0.0
    trail_atr: float = 0.0
    enabled: bool = True


class StreamUpdateRequest(BaseModel):
    name: Optional[str] = None
    strategy: Optional[str] = None
    symbol: Optional[str] = None
    timeframe: Optional[str] = None
    volume: Optional[float] = None
    sl_atr: Optional[float] = None
    tp_atr: Optional[float] = None
    deposit: Optional[float] = None
    breakeven_atr: Optional[float] = None
    trail_atr: Optional[float] = None
    enabled: Optional[bool] = None


def _validate_symbol(symbol: str):
    from settings import Dictionary
    if symbol not in Dictionary.symbolTradingStatus:
        raise HTTPException(status_code=400, detail=f"Неизвестный символ: {symbol}")


def _tf_to_int(tf_str: str) -> int:
    from settings import TF_MAP
    if tf_str not in TF_MAP:
        raise HTTPException(status_code=400, detail=f"Неизвестный timeframe: {tf_str}")
    return TF_MAP[tf_str]


@router.get("/streams")
async def list_streams(user: auth.UserRecord = Depends(get_current_user)):
    import streams as streams_mod
    return {"streams": [s.to_dict() for s in streams_mod.registry.all()],
            "max": streams_mod.MAX_STREAMS}


@router.post("/streams")
async def create_stream(req: StreamCreateRequest,
                        admin: auth.UserRecord = Depends(require_admin)):
    import streams as streams_mod
    _validate_symbol(req.symbol)
    tf = _tf_to_int(req.timeframe)
    try:
        s = streams_mod.registry.create(
            name=req.name or "",
            strategy=req.strategy,
            symbol=req.symbol,
            timeframe=tf,
            volume=req.volume,
            sl_atr=req.sl_atr,
            tp_atr=req.tp_atr,
            deposit=req.deposit,
            breakeven_atr=req.breakeven_atr,
            trail_atr=req.trail_atr,
            enabled=req.enabled,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    await _broadcast_streams_changed()
    return {"ok": True, "stream": s.to_dict()}


@router.patch("/streams/{stream_id}")
async def update_stream(stream_id: str, req: StreamUpdateRequest,
                        admin: auth.UserRecord = Depends(require_admin)):
    import streams as streams_mod
    fields = req.model_dump(exclude_unset=True, exclude_none=True)
    if "symbol" in fields:
        _validate_symbol(fields["symbol"])
    if "timeframe" in fields:
        fields["timeframe"] = _tf_to_int(fields["timeframe"])
    try:
        s = streams_mod.registry.update(stream_id, **fields)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Поток {stream_id} не найден")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    await _broadcast_streams_changed()
    return {"ok": True, "stream": s.to_dict()}


@router.delete("/streams/{stream_id}")
async def delete_stream(stream_id: str,
                        admin: auth.UserRecord = Depends(require_admin)):
    import streams as streams_mod
    if not streams_mod.registry.delete(stream_id):
        raise HTTPException(status_code=404, detail=f"Поток {stream_id} не найден")
    await _broadcast_streams_changed()
    return {"ok": True}


async def _broadcast_streams_changed():
    import streams as streams_mod
    from web.ws_manager import ws_manager
    await ws_manager.broadcast("streams_changed", {
        "streams": [s.to_dict() for s in streams_mod.registry.all()],
    })


# ──────────────────────────── Backtest ────────────────────────────

class BacktestRequest(BaseModel):
    strategy: str = "default"
    symbol: str
    bars: int = 2000
    deposit: float = 0.0
    spread: int = 0
    risk: float = 80.0
    volume: float = 0.0
    sl_atr: float = 0.0
    tp_atr: float = 0.0
    breakeven_atr: float = 0.0
    trail_atr: float = 0.0
    start: Optional[str] = None
    end: Optional[str] = None


@router.post("/backtest")
async def run_backtest(req: BacktestRequest,
                       user: auth.UserRecord = Depends(get_current_user)):
    await bus.publish(Event(
        type=EventType.BACKTEST_STARTED,
        source="api",
        payload={
            "strategy": req.strategy,
            "symbol": req.symbol,
            "bars": req.bars,
            "deposit": req.deposit,
            "spread": req.spread,
            "risk": req.risk,
            "volume": req.volume,
            "sl_atr": req.sl_atr,
            "tp_atr": req.tp_atr,
            "breakeven_atr": req.breakeven_atr,
            "trail_atr": req.trail_atr,
            "start": req.start,
            "end": req.end,
        }
    ))
    return {"ok": True, "message": f"Бэктест {req.symbol} запущен"}


# ──────────────────────────── Close position ──────────────────────

class ClosePositionRequest(BaseModel):
    ticket: int
    symbol: str


@router.post("/position/close")
async def close_position(req: ClosePositionRequest,
                         admin: auth.UserRecord = Depends(require_admin)):
    await bus.publish(Event(
        type=EventType.ORDER_CLOSE_REQUEST,
        source="api",
        payload={"ticket": req.ticket, "symbol": req.symbol, "reason": "manual_api"}
    ))
    return {"ok": True, "ticket": req.ticket}


# ──────────────────────────── Users (admin only) ──────────────────

class UserCreateRequest(BaseModel):
    username: str
    password: str
    role: str = "user"


class UserUpdateRequest(BaseModel):
    password: Optional[str] = None
    role: Optional[str] = None
    avatar: Optional[str] = None


class AvatarRequest(BaseModel):
    avatar: str


@router.patch("/me/avatar")
async def update_my_avatar(req: AvatarRequest,
                           user: auth.UserRecord = Depends(get_current_user)):
    try:
        rec = auth.registry.update(user.username, avatar=req.avatar)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"ok": True, "user": rec.to_public()}


@router.get("/users")
async def list_users(admin: auth.UserRecord = Depends(require_admin)):
    return {"users": [u.to_public() for u in auth.registry.all()]}


@router.post("/users")
async def create_user(req: UserCreateRequest,
                      admin: auth.UserRecord = Depends(require_admin)):
    try:
        rec = auth.registry.create(req.username, req.password, req.role)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"ok": True, "user": rec.to_public()}


@router.patch("/users/{username}")
async def update_user(username: str, req: UserUpdateRequest,
                      admin: auth.UserRecord = Depends(require_admin)):
    try:
        rec = auth.registry.update(username, password=req.password, role=req.role, avatar=req.avatar)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Пользователь {username} не найден")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"ok": True, "user": rec.to_public()}


@router.delete("/users/{username}")
async def delete_user(username: str,
                      admin: auth.UserRecord = Depends(require_admin)):
    if username.lower() == admin.username.lower():
        raise HTTPException(status_code=400, detail="Нельзя удалить самого себя")
    try:
        ok = auth.registry.delete(username)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if not ok:
        raise HTTPException(status_code=404, detail=f"Пользователь {username} не найден")
    return {"ok": True}
