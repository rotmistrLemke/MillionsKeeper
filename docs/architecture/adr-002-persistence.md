# ADR-002 — Persistence: Postgres как control plane

**Дата:** 2026-06-06
**Статус:** принято (на бумаге; реализация — после валидации, см. unit-economics)
**Контекст-трек:** монетизация SaaS, под-проект #2. Зависит от ADR-001 (изоляция data plane).

## Контекст

SaaS-биллингу нужна надёжная БД для клиентов/подписок/платежей. `billing.md` уже содержит SQL-схему (users/plans/subscriptions/payments/webhook_events), спроектированную под (отменённую) v2. Нужно решить, **что именно хранит Postgres** в реальной архитектуре ADR-001 (1 VPS : 1 клиент, воркер-бот не меняется).

Текущее состояние:

- Data plane (торговля) — файловый: каждый VPS-воркер держит локально `account` (MT5-креды), `streams.json` (потоки/стратегии), `.jwt_secret`, `performance.db` (SQLite-трек), anomaly-db. Это следствие ADR-001 (воркер = существующий бот без изменений).
- Control plane (web/биллинг/аккаунты) — пока нет; `users.json` (`auth.py`) держит операторских пользователей одного деплоя.

## Решение

**Postgres хранит ТОЛЬКО control plane.** Data plane остаётся файловым на каждом VPS.

Postgres (control plane):
- клиенты-тенанты, тарифы, подписки, платежи, webhook-идемпотентность (из `billing.md`);
- маппинг **тенант ↔ VPS-инстанс ↔ тариф** (новое, для оркестрации/провижнинга);
- НЕ хранит торговый конфиг (`streams.json`/`account`) и НЕ пушит его в воркеры на этом этапе.

Data plane (per-VPS, файлы) — без изменений: воркер читает свои локальные `account`/`streams.json`/`performance.db`. Связь с control plane — через провижнинг (provisioning-runbook генерирует файлы из данных control plane при онбординге) и gating (#5 останавливает воркер).

## Схема (реконсиляция `billing.md` + control-plane дополнения)

Берём как есть из `billing.md`: `plans`, `subscriptions`, `payments`, `webhook_events` (см. там полный SQL). Корректировки/дополнения:

```sql
-- Клиент-тенант (control plane). Заменяет/расширяет billing.md users.
CREATE TABLE tenants (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email           VARCHAR(255) UNIQUE NOT NULL,
    password_hash   VARCHAR(255),              -- портал control plane (НЕ дашборд воркера)
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    status          VARCHAR(16) NOT NULL DEFAULT 'active',  -- active|suspended|closed
    stripe_customer_id   VARCHAR(64) UNIQUE,
    yookassa_customer_id VARCHAR(64) UNIQUE
);

-- VPS-инстанс тенанта (оркестрация data plane).
CREATE TABLE vps_instances (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    provider        VARCHAR(32),               -- провайдер VPS
    host            VARCHAR(255),              -- IP/домен
    dashboard_url   VARCHAR(255),
    status          VARCHAR(16) NOT NULL DEFAULT 'provisioning', -- provisioning|running|stopped|deprovisioned
    plan_code       VARCHAR(32) REFERENCES plans(code),
    mt5_login       VARCHAR(64),               -- метаданные (НЕ пароль; пароль шифруется отдельно, см. ADR-003/#3)
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_vps_tenant ON vps_instances(tenant_id);
```

`subscriptions`/`payments` из `billing.md` ссылаются на `tenants(id)` (вместо тамошнего `users`). Прочее (`plans`, `webhook_events`) — без изменений.

## Стек

- PostgreSQL (managed, напр. у того же провайдера, или Docker на control-plane хосте — НЕ на воркер-VPS).
- SQLAlchemy + Alembic (миграции). Async (asyncpg) — совместимо с FastAPI control plane.
- Redis (идемпотентность webhook/rate-limit) — опционально, как в `billing.md`; на старте можно без него (идемпотентность через `webhook_events` UNIQUE).

## Миграция

- `users.json` (операторские, `auth.py`) — это per-деплой дашборд-пользователи, НЕ клиенты-тенанты. При появлении control plane они остаются на воркерах; в Postgres мигрируют только если оператор хочет единый портал (обычно нет). Клиенты-тенанты заводятся заново при онбординге.
- `performance.db` (SQLite) остаётся на воркере (трек по счёту тенанта). Агрегация в control plane — опциональный будущий шаг (pull из воркеров), не в #2.

## Последствия

- **+** Control plane и data plane развязаны: БД-сбой не роняет торговлю; торговый путь не зависит от Postgres.
- **+** Воркер не меняется (ADR-001 соблюдён); риск для денежного пути нулевой.
- **−** Двойной источник правды по конфигу тенанта (control plane знает тариф/VPS; воркер — фактический `streams.json`). Синхронизация — через провижнинг/gating, не автоматическая. Приемлемо для MVP; авто-синк — позже.
- **−** Нужен отдельный control-plane хост (Postgres + FastAPI control plane), не на воркер-VPS.

## Граница

Этот ADR — только модель хранения. Аккаунты/идентичность — ADR-003. Биллинг-эндпоинты — `billing.md`/#4. Gating — #5. Реализацию начинаем после прохождения kill-criteria валидации.

## Связанные документы

- `docs/architecture/adr-001-data-plane-isolation.md` — почему воркер файловый.
- `docs/architecture/adr-003-multi-tenant-accounts.md` — идентичность тенанта vs дашборд воркера.
- `docs/architecture/billing.md` — исходная SQL-схема (plans/subscriptions/payments/webhook_events).
- `docs/business/2026-06-06-unit-economics-honest.md` — «валидация прежде постройки».
