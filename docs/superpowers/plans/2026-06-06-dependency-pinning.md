# Пиннинг зависимостей Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Заморозить прямые зависимости к known-good версиям (exact `==`), сделав CI детерминированным и защитив от ломающих мажоров.

**Architecture:** Точечное изменение двух requirements-файлов. Версии берутся с текущего known-good окружения (локальный прогон 550 passed, 3 xfailed, Python 3.11.9). Маркеры/экстры/комментарии сохраняются. Прод-код и CI-workflow не трогаются. Финальная валидация — push → GitHub Actions на Linux.

**Tech Stack:** pip requirements, GitHub Actions (ubuntu-latest, Python 3.11).

---

## File Structure

- **Modify:** `requirements.txt` — рантайм-зависимости, пиннинг `==`.
- **Modify:** `requirements-dev.txt` — тест-зависимости, пиннинг `==`.
- **Не трогаем:** `.github/workflows/ci.yml` (уже ставит оба файла), прод-код.

---

## Task 1: Пиннинг requirements.txt и requirements-dev.txt

**Files:**
- Modify: `requirements.txt`
- Modify: `requirements-dev.txt`

- [ ] **Step 1: Заменить `requirements.txt` целиком**

Записать в `requirements.txt` РОВНО это содержимое:

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

Сохранить: маркер `; sys_platform == "win32"` у MetaTrader5, экстры `[standard]`/`[cryptography]`. Порядок строк — как в оригинале.

- [ ] **Step 2: Заменить `requirements-dev.txt` целиком**

Записать в `requirements-dev.txt` РОВНО это содержимое (комментарии-шапку сохранить):

```
# Зависимости только для тестов/разработки (в проде не нужны).
# Рантайм-зависимости — в requirements.txt.
pytest==9.0.3
pytest-asyncio==1.3.0
```

- [ ] **Step 3: Проверка резолва зависимостей (dry-run, без установки)**

Run: `python -m pip install -r requirements.txt -r requirements-dev.txt --dry-run`
Expected: команда завершается без ошибок резолва/конфликтов (на Windows MetaTrader5 включён маркером и присутствует). Допустимо «Would install ...» / «Requirement already satisfied». Если pip сообщает ResolutionImpossible или не находит версию — STOP, report (нужна точечная правка версии).

- [ ] **Step 4: Регрессия — полный прогон**

Run: `python -m pytest -q`
Expected: **550 passed, 3 xfailed** (версии = уже установленным, поведение не меняется). Любое падение незелёных → STOP, report.

- [ ] **Step 5: Commit**

```bash
git add requirements.txt requirements-dev.txt
git commit -m "build: пиннинг прямых зависимостей к known-good версиям (детерминированный CI)"
```
Завершить трейлером (пустая строка, затем): `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`

---

## Task 2: Push и валидация CI на Linux

**Files:** (нет правок — только git/CI)

- [ ] **Step 1: Push на origin**

Ветка `main`. Запушить оба синхронных указателя при необходимости:
```bash
git push origin main
```
(stage-2 синхронизируем отдельно при следующем шаге трека, если нужно; на этой задаче достаточно main для срабатывания Actions.)

- [ ] **Step 2: Дождаться GitHub Actions**

CI workflow `tests` (`.github/workflows/ci.yml`) триггерится на push в `main`. На ubuntu-latest/Python 3.11 поставит РОВНО пинованные версии (MetaTrader5 пропущен по маркеру, TA-Lib 0.6.8 из manylinux-wheel) и выполнит `pytest -q`.
Expected: зелёный прогон. Проверить статус через веб-интерфейс Actions (gh CLI в окружении не установлен — см. память).

- [ ] **Step 3: Если CI красный — диагностика (не угадывать)**

Вероятные причины и реакция (только requirements, прод не трогаем):
- Нет Linux-wheel для пинованной версии → ослабить именно эту строку до ближайшей версии с wheel (или `>=x,<x+1`), зафиксировать причину.
- Поведенческое расхождение Linux vs Windows на пинованной версии → разобрать конкретный тест по систематической отладке, привести версию к известно-зелёной.
Закоммитить точечную правку, повторить push. Если зелёный с первого раза — Task завершён.

---

## Task 3: Обновление памяти

**Files:**
- Modify: `C:\Users\paha4\.claude\projects\i--development-projects-MillionsKeeper\memory\project_millionskeeper.md` (вне git)

- [ ] **Step 1: Отметить пиннинг в памяти**

В `project_millionskeeper.md`:
- В слайс CI / «Важные нюансы»: снять/обновить пометку «депы unpinned → CI на latest» на «зависимости запинованы `==` (backlog #4, 2026-06-06): requirements.txt/-dev.txt заморожены к known-good (pandas 2.3.3 и т.д.); транзитивные не пинованы; защита от ломающих мажоров».
- В backlog: пометить пункт «пиннинг зависимостей» как ✅ СДЕЛАНО с датой и SHA коммита.
- Указать статус CI (зелёный/красный по факту Task 2).

(Память вне git — не коммитить.)

---

## Self-Review (выполнено автором плана)

- **Покрытие спеки:** оба requirements-файла с точным содержимым → Task 1 (Steps 1–2); dry-run резолв → Task 1 Step 3; локальная регрессия 550/3xfailed → Task 1 Step 4; push→Actions валидация Linux → Task 2; критерий «CI зелёный» → Task 2 Steps 2–3; обновление памяти → Task 3. ✅
- **Плейсхолдеры:** нет — точное содержимое обоих файлов приведено целиком, команды и ожидаемые результаты явные. ✅
- **Согласованность:** версии в плане совпадают со спекой (pandas==2.3.3, numpy==2.3.4, TA-Lib==0.6.8, fastapi==0.135.3, uvicorn[standard]==0.42.0, websockets==16.0, python-telegram-bot==22.5, python-dotenv==1.1.1, python-jose[cryptography]==3.5.0, passlib==1.7.4, MetaTrader5==5.0.5388; pytest==9.0.3, pytest-asyncio==1.3.0). ✅
- **Инварианты:** маркер MetaTrader5, экстры, комментарии-шапка, CI-workflow без изменений, прод не трогаем. ✅
