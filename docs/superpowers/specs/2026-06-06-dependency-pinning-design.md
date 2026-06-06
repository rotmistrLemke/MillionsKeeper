# Пиннинг зависимостей — Design

**Дата:** 2026-06-06
**Статус:** утверждён (brainstorming)
**Трек:** надёжность CI (backlog #4).

## Цель

Устранить недетерминированность CI: сейчас `requirements.txt`/`requirements-dev.txt` анпиннуты, и GitHub Actions ставит latest каждой зависимости. Это уже один раз ломало прогон (pandas 3.0 убрал `freq="H"`, чинилось на `"h"`); будущие мажоры могут ломать снова. Заморозить прямые зависимости к known-good версиям.

## Решение (выбор пользователя)

**Exact `==` пиннинг прямых зависимостей** к текущим установленным known-good версиям (локальный прогон 550 passed, 3 xfailed, Python 3.11.9). Транзитивные (starlette/pydantic и пр.) НЕ пинуем — выбранный охват «только прямые»; `fastapi==0.135.3` их косвенно ограничивает.

Отвергнуты: caps (верхние границы — допускают minor-дрейф, CI не полностью детерминирован); lockfile/pip-tools (новый инструмент/воркфлоу, избыточен для лёгкого solo-проекта без poetry/docker; кросс-платформенная компиляция MetaTrader5/TA-Lib усложнила бы).

## Изменения

### `requirements.txt`
```
MetaTrader5==5.0.5388; sys_platform == "win32"
python-telegram-bot==22.5
pandas==2.3.3
numpy==2.3.4
TA-Lib==0.6.8
python-dotenv==1.1.1
fastapi==0.135.3
uvicorn[standard]==0.42.0
websockets==16.0
python-jose[cryptography]==3.5.0
passlib==1.7.4
```

### `requirements-dev.txt`
```
# Зависимости только для тестов/разработки (в проде не нужны).
# Рантайм-зависимости — в requirements.txt.
pytest==9.0.3
pytest-asyncio==1.3.0
```

## Инварианты

- **Маркер `MetaTrader5` сохраняется** (`; sys_platform == "win32"`): Linux CI пакет пропускает, тесты берут стаб из `tests/conftest.py`. Версия пинуется для воспроизводимости Windows-прода.
- **Экстры сохраняются** (`uvicorn[standard]`, `python-jose[cryptography]`).
- **Комментарии-шапки `requirements-dev.txt` сохраняются.**
- **Прод-код не трогаем** — изменение только в requirements.
- CI-workflow (`.github/workflows/ci.yml`) НЕ меняется: он уже ставит оба файла; пиннинг вступит в силу автоматически.

## Платформенный нюанс

Версии сняты с Windows-окружения; CI — Linux. Для всех пинованных пакетов существуют Linux-wheel тех же версий (mainstream-пакеты; TA-Lib 0.6.8 — manylinux-wheel). Финальная валидация — push → Actions на Linux. Если wheel не найдётся / поведение разойдётся — точечно поправить версию (только requirements).

## Критерии готовности

- Оба requirements-файла пинованы `==` к указанным версиям; маркер/экстры/комментарии сохранены.
- Локальный `pytest -q` → 550 passed, 3 xfailed (без регрессий; версии = установленным).
- `pip install -r requirements.txt -r requirements-dev.txt --dry-run` резолвится без конфликтов.
- Push → GitHub Actions зелёный на Linux (детерминированный набор).

## Будущее (вне охвата)

- Полная транзитивная заморозка (pip-tools/lockfile) — при желании отдельным шагом.
- Автообновление (Dependabot/Renovate) для контролируемого бумпа пинов.
