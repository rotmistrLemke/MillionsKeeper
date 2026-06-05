# Billing MVP — архитектурный план

**Статус:** план, не реализован
**Целевая фаза:** после Фазы 4 (PostgreSQL + Auth)
**Последнее обновление:** 2026-05-14

---

## Контекст и предпосылки

MillionsKeeper движется по 6-фазному roadmap. На момент написания этого документа реализована Фаза 0 (анализ). Биллинг физически нельзя интегрировать раньше, чем будут готовы:

- **Фаза 1** — PostgreSQL через Docker (БД для подписок и платежей)
- **Фаза 2** — рефакторинг backend на модульную структуру (`backend/app/`)
- **Фаза 4** — Auth-система на JWT (биллинг требует идентификации пользователя)

Документ фиксирует архитектурное решение, чтобы при подходе к этим фазам не пересобирать план с нуля.

---

## Выбор платёжных провайдеров

Целевая аудитория двойная: РФ/СНГ (рубли) и иностранные клиенты (USD/EUR). Один провайдер не закрывает оба сегмента.

| | Stripe | ЮKassa |
|---|--------|--------|
| Юрисдикция | Глобально (USD, EUR) | РФ + СНГ (RUB) |
| Когда нужен | Иностранные клиенты | Российские клиенты |
| Подписки (recurring) | Нативно, отлично | Через автоплатежи |
| Apple/Google Pay | Из коробки | Есть |
| Customer Portal (готовый UI) | Да, ссылку отдаёт | Нет |
| Комиссия | 2.9% + $0.30 | 2.8–3.5% |
| Регистрация | Stripe Atlas (US LLC) | ИП РФ + расчётный счёт |

**Решение:** оба провайдера, маршрутизация на checkout:
```
RU/CIS user → ЮKassa (RUB)
EU/US/other → Stripe (USD)
```

Реализуем через единый `IBillingProvider` интерфейс — два независимых модуля.

---

## Архитектура модуля

```
┌────────────────────────────────────────────────────────────┐
│                     Frontend (React v2)                    │
│  /pricing → /checkout → Stripe/ЮKassa redirect             │
│  /account/billing — личный кабинет                          │
└──────────────┬──────────────────────────────┬──────────────┘
               │                              │
       Checkout Session                  Customer Portal
               │                              │
               ▼                              ▼
┌────────────────────────────────────────────────────────────┐
│                  FastAPI billing module                    │
│                                                            │
│  POST  /api/billing/checkout    → создать session          │
│  POST  /api/billing/webhook/stripe                         │
│  POST  /api/billing/webhook/yookassa                       │
│  GET   /api/billing/subscription  → текущий статус         │
│  POST  /api/billing/cancel        → отмена                 │
│  POST  /api/billing/portal        → ссылка на Stripe portal│
└──────────────┬──────────────────────────────┬──────────────┘
               │                              │
               ▼                              ▼
        PostgreSQL                  Redis (idempotency)
        ┌──────────────────┐        ┌─────────────────┐
        │ users            │        │ webhook_events  │
        │ subscriptions    │        │ rate_limits     │
        │ payments         │        └─────────────────┘
        │ webhook_events   │
        └──────────────────┘
                │
                ▼
        ┌──────────────────────────────────────┐
        │  Subscription Gate (decorator)       │
        │  → проверяет access на каждом запросе │
        │    к торговым агентам                 │
        └──────────────────────────────────────┘
```

---

## Структура файлов в проекте

```
backend/app/
├── billing/
│   ├── __init__.py
│   ├── config.py              # API ключи, webhook secrets из env
│   ├── models.py              # Pydantic schemas
│   ├── repository.py          # SQLAlchemy queries
│   ├── service.py             # бизнес-логика (создать/отменить/продлить)
│   ├── gate.py                # @requires_subscription декоратор
│   ├── providers/
│   │   ├── base.py            # IBillingProvider интерфейс
│   │   ├── stripe_provider.py
│   │   └── yookassa_provider.py
│   └── api/
│       ├── checkout.py        # POST /api/billing/checkout
│       ├── webhook.py         # webhooks обоих провайдеров
│       ├── subscription.py    # GET/cancel
│       └── portal.py          # Stripe customer portal link
```

---

## Схема БД

```sql
-- Пользователи (после auth-фазы)
CREATE TABLE users (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email           VARCHAR(255) UNIQUE NOT NULL,
    mt5_login       VARCHAR(64),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    stripe_customer_id   VARCHAR(64) UNIQUE,
    yookassa_customer_id VARCHAR(64) UNIQUE
);

-- Тарифные планы (статичный справочник)
CREATE TABLE plans (
    code            VARCHAR(32) PRIMARY KEY,        -- 'free' | 'trader' | 'pro' | 'lifetime'
    name            VARCHAR(64) NOT NULL,
    price_usd       NUMERIC(10,2),
    price_rub       NUMERIC(10,2),
    interval        VARCHAR(16),                    -- 'month' | 'year' | 'one_time' | NULL
    max_accounts    INT NOT NULL DEFAULT 1,
    max_strategies  INT NOT NULL DEFAULT 1,
    features        JSONB NOT NULL DEFAULT '{}',
    stripe_price_id     VARCHAR(64),
    yookassa_product_id VARCHAR(64)
);

-- Подписки
CREATE TABLE subscriptions (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    plan_code       VARCHAR(32) NOT NULL REFERENCES plans(code),
    provider        VARCHAR(16) NOT NULL,           -- 'stripe' | 'yookassa' | 'manual'
    provider_sub_id VARCHAR(64),                    -- ID на стороне провайдера
    status          VARCHAR(32) NOT NULL,           -- 'trialing'|'active'|'past_due'|'canceled'|'unpaid'|'lifetime'
    current_period_start TIMESTAMPTZ,
    current_period_end   TIMESTAMPTZ,
    cancel_at_period_end BOOLEAN NOT NULL DEFAULT FALSE,
    canceled_at     TIMESTAMPTZ,
    metadata        JSONB NOT NULL DEFAULT '{}',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_sub_user_active ON subscriptions(user_id)
    WHERE status IN ('active','trialing','lifetime');

-- История платежей
CREATE TABLE payments (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID NOT NULL REFERENCES users(id),
    subscription_id UUID REFERENCES subscriptions(id),
    provider        VARCHAR(16) NOT NULL,
    provider_payment_id VARCHAR(64) UNIQUE NOT NULL,
    amount          NUMERIC(10,2) NOT NULL,
    currency        VARCHAR(8) NOT NULL,
    status          VARCHAR(32) NOT NULL,           -- 'pending'|'succeeded'|'failed'|'refunded'
    paid_at         TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    raw_event       JSONB
);

-- Webhook идемпотентность (защита от дублей)
CREATE TABLE webhook_events (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    provider        VARCHAR(16) NOT NULL,
    event_id        VARCHAR(128) NOT NULL,
    event_type      VARCHAR(64) NOT NULL,
    processed_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    payload         JSONB NOT NULL,
    UNIQUE(provider, event_id)
);
```

---

## Ключевые endpoint-ы

### Checkout — создать платёжную сессию

```python
# backend/app/billing/api/checkout.py
from fastapi import APIRouter, Depends, HTTPException
from app.billing.models import CheckoutRequest, CheckoutResponse
from app.billing.service import BillingService

router = APIRouter(prefix="/api/billing", tags=["billing"])

@router.post("/checkout", response_model=CheckoutResponse)
async def create_checkout(
    req: CheckoutRequest,
    user = Depends(get_current_user),
    svc: BillingService = Depends(),
):
    """Создаёт checkout-сессию у соответствующего провайдера."""
    if req.plan_code not in {"trader", "pro", "lifetime"}:
        raise HTTPException(400, "Invalid plan")

    provider = "yookassa" if req.currency == "RUB" else "stripe"
    session = await svc.create_checkout_session(
        user=user,
        plan_code=req.plan_code,
        provider=provider,
        success_url=req.success_url,
        cancel_url=req.cancel_url,
    )
    return CheckoutResponse(checkout_url=session.url, session_id=session.id)
```

### Webhook handler — критически важная часть

```python
# backend/app/billing/api/webhook.py
import stripe
from fastapi import APIRouter, Request, Header, HTTPException
from app.billing.service import BillingService
from app.billing.config import settings

router = APIRouter(prefix="/api/billing/webhook")

@router.post("/stripe")
async def stripe_webhook(
    request: Request,
    stripe_signature: str = Header(None, alias="Stripe-Signature"),
    svc: BillingService = Depends(),
):
    payload = await request.body()

    # 1. Проверка подписи
    try:
        event = stripe.Webhook.construct_event(
            payload, stripe_signature, settings.STRIPE_WEBHOOK_SECRET
        )
    except (ValueError, stripe.error.SignatureVerificationError):
        raise HTTPException(400, "Invalid signature")

    # 2. Идемпотентность
    if await svc.event_already_processed("stripe", event["id"]):
        return {"status": "duplicate"}

    # 3. Маршрутизация по типу события
    handlers = {
        "checkout.session.completed":     svc.handle_checkout_completed,
        "customer.subscription.updated":  svc.handle_subscription_updated,
        "customer.subscription.deleted":  svc.handle_subscription_canceled,
        "invoice.payment_succeeded":      svc.handle_payment_succeeded,
        "invoice.payment_failed":         svc.handle_payment_failed,
    }
    handler = handlers.get(event["type"])
    if handler:
        await handler(event)

    await svc.mark_event_processed("stripe", event["id"], event["type"], event)
    return {"status": "ok"}


@router.post("/yookassa")
async def yookassa_webhook(request: Request, svc: BillingService = Depends()):
    payload = await request.json()

    # ЮKassa: проверка по IP whitelist
    client_ip = request.client.host
    if client_ip not in settings.YOOKASSA_TRUSTED_IPS:
        raise HTTPException(403, "Untrusted source")

    event_id = payload.get("object", {}).get("id")
    if not event_id:
        raise HTTPException(400, "Missing event ID")

    if await svc.event_already_processed("yookassa", event_id):
        return {"status": "duplicate"}

    event_type = payload.get("event")
    handlers = {
        "payment.succeeded":  svc.handle_yk_payment_succeeded,
        "payment.canceled":   svc.handle_yk_payment_canceled,
        "refund.succeeded":   svc.handle_yk_refund_succeeded,
    }
    handler = handlers.get(event_type)
    if handler:
        await handler(payload)

    await svc.mark_event_processed("yookassa", event_id, event_type, payload)
    return {"status": "ok"}
```

### Subscription Gate — гейтинг трейдинг-агентов

```python
# backend/app/billing/gate.py
from functools import wraps
from fastapi import HTTPException

def requires_subscription(min_plan: str = "trader", features: list[str] = None):
    """
    Декоратор для endpoint-ов, требующих платную подписку.

    Использование:
        @requires_subscription(min_plan="pro", features=["news_filter"])
        async def enable_news_strategy(...): ...
    """
    PLAN_RANK = {"free": 0, "trader": 1, "pro": 2, "lifetime": 3}

    def decorator(fn):
        @wraps(fn)
        async def wrapper(*args, user=None, **kwargs):
            sub = await get_active_subscription(user.id)
            if not sub:
                raise HTTPException(402, "Subscription required")

            if PLAN_RANK[sub.plan_code] < PLAN_RANK[min_plan]:
                raise HTTPException(402, f"Plan {min_plan}+ required")

            if features:
                missing = [f for f in features if f not in sub.features]
                if missing:
                    raise HTTPException(402, f"Feature(s) {missing} not in plan")

            return await fn(*args, user=user, **kwargs)
        return wrapper
    return decorator
```

Применение:
```python
@router.post("/agents/strategy/enable")
@requires_subscription(min_plan="trader")
async def enable_strategy(...): ...

@router.post("/agents/news-filter/enable")
@requires_subscription(min_plan="pro", features=["news_filter"])
async def enable_news_filter(...): ...
```

---

## Личный кабинет — минимум для MVP

| Маршрут | Что показывает | Действия |
|---------|----------------|----------|
| `/account` | Email, MT5-логин, дата регистрации | Изменить email |
| `/account/billing` | Текущий план, дата след. списания, история | Сменить план, отменить, открыть Customer Portal |
| `/account/billing/invoices` | Список платежей | Скачать чек/инвойс |
| `/account/api-keys` | Только для Pro+ | Создать/отозвать ключ |

**Принцип:** Stripe Customer Portal — это полностью готовая страница управления подпиской от Stripe (`stripe.billing_portal.Session.create`). Своя страница не нужна — открываем встроенный портал по ссылке. Экономия ~2 недели разработки и поддержки.

ЮKassa Customer Portal не предоставляет — нужна минимальная своя страница: показать план + кнопка «Отменить».

---

## Безопасность — чек-лист

- [ ] **Webhook signature verification** для Stripe (HMAC через `stripe.Webhook.construct_event`)
- [ ] **IP whitelist** для ЮKassa ([официальный список IP](https://yookassa.ru/developers/using-api/webhooks#ip))
- [ ] **Идемпотентность** через `webhook_events` таблицу с UNIQUE(provider, event_id)
- [ ] **HTTPS only** для webhook endpoints
- [ ] **Secrets в env** (`STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET`, `YOOKASSA_SHOP_ID`, `YOOKASSA_SECRET_KEY`), никогда в коде
- [ ] **Не доверять фронту** — `plan_code`, `amount` валидируется на бэке против справочника `plans`
- [ ] **Логировать всё** — webhook payloads в `raw_event` для аудита и отладки
- [ ] **Rate limiting** на checkout endpoint (защита от перебора)
- [ ] **Не хранить карточные данные** — только токены провайдера

---

## Тестирование

### Stripe
```bash
# Локальный webhook через Stripe CLI
stripe listen --forward-to localhost:8080/api/billing/webhook/stripe

# Триггер тестовых событий
stripe trigger checkout.session.completed
stripe trigger customer.subscription.updated
stripe trigger invoice.payment_failed
```

### ЮKassa
- Тестовый магазин в личном кабинете → отдельный `shopId`/`secretKey`
- Тестовые карты: `5555 5555 5555 4444` и др. из [документации](https://yookassa.ru/developers/payment-acceptance/testing-and-going-live)
- Для webhook локально — использовать ngrok или cloudflared tunnel

### Pytest-стратегия
- Unit-тесты на handler-ы с моковыми payload-ами
- Интеграция через Stripe test mode (реальные API-вызовы)
- Critical path E2E: checkout → webhook → DB-запись → gate-проверка

---

## План реализации в неделях

### Неделя 1: Подготовка инфраструктуры
- Завершить Фазу 1 v2 (Pydantic Settings, Docker, PostgreSQL)
- Заявка ИП + регистрация ЮKassa магазина
- Stripe аккаунт (Stripe Atlas если нужны $-платежи)
- Юр.лицо в email-копии оферты

### Неделя 2: Backend каркас
- Миграции БД (`users`, `plans`, `subscriptions`, `payments`, `webhook_events`)
- `IBillingProvider` интерфейс + Stripe-реализация
- Checkout endpoint + webhook handler (Stripe only)
- E2E тест: checkout → webhook → активная подписка в БД

### Неделя 3: ЮKassa + gating
- ЮKassa провайдер
- `requires_subscription` декоратор
- Применение gate ко всем торговым endpoint-ам
- Webhook ЮKassa + идемпотентность

### Неделя 4: Frontend ЛК + полировка
- `/account/billing` страница
- Stripe Customer Portal интеграция (одна ссылка)
- Email-уведомления (платёж успешен/неудача/отмена)
- Полный E2E через test mode обоих провайдеров

**Итого: 4 недели от старта работ до приёма первого реального платежа.**

---

## Открытые вопросы (TBD)

- **Trial-период:** давать или нет? Если да — сколько дней, требовать ли карту?
- **Pro-rata при апгрейде:** Stripe умеет сам, ЮKassa — нужна ручная логика возврата + новой подписки.
- **VAT/НДС:** для ЕС-клиентов через Stripe — нужен VAT-ID и Stripe Tax; для РФ ИП на УСН — НДС не начисляется.
- **Multi-currency для одного пользователя:** что если RU-юзер уезжает за границу и хочет платить в $? Перенос подписки между провайдерами — нетривиально, проще закрыть и открыть заново.
- **Refund automation:** Stripe API позволяет автоматизировать, ЮKassa тоже — но логика для Lifetime (14 дней) и месячных (7 дней при технической непригодности) различается.
- **Реферальная программа (30%):** учёт промокодов и партнёрских выплат — отдельный модуль, не в MVP.

Решить эти вопросы при подходе к Неделе 1.

---

## Связанные документы

- [Публичная оферта](../business/oferta.md) — юридическая обвязка
- [Unit Economics Dashboard](../business/unit-economics.html) — расчёты, на которых основаны Тарифы
- [Landing Page](../business/landing.html) — pricing-блок
- `docs/architecture/roadmap.md` — общий roadmap проекта (Фазы 0–6)
