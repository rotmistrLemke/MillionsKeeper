# Развёртывание TradingHouse на Windows Server

Инструкция доводит проект до состояния «работает 24/7 по HTTPS на собственном
домене». Архитектура:

```
[интернет] ──HTTPS:443── Caddy ──HTTP:8080── TradingHouse (FastAPI + бот)
                                                  │
                                                  └── MT5 терминал (тот же сервер)
```

Caddy получает SSL-сертификат от Let's Encrypt автоматически и проксирует
весь трафик (включая WebSocket) на бота, который слушает только локальный
интерфейс. MT5 работает на той же машине — это требование Python-пакета
`MetaTrader5`, он не работает удалённо.

---

## 0. Перед стартом

**Что нужно:**

- Windows Server 2019/2022 VPS с публичным IP. Минимум 2 vCPU, 4 GB RAM, 40 GB.
  Хостеры с Forex-friendly low-latency: **RoboForex**, **FXOpen**, **Beeks Group**,
  для общей задачи — **TimeWeb**, **Hetzner** (Cloud Windows), **Vultr**.
- Доменное имя. Регистраторы: **REG.RU**, **Namecheap**, **Cloudflare** (если
  собираетесь использовать их же DNS — рекомендую, удобнее).
- Учётные данные MT5 (login, password, server).
- RDP-доступ к серверу.

**Сразу после получения сервера:**

1. Подключитесь по RDP, смените дефолтный пароль администратора.
2. Включите автоматические обновления Windows.
3. Через **Server Manager → Local Server** убедитесь, что фаервол включён.

---

## 1. DNS-запись на домен

В панели регистратора (или Cloudflare) создайте `A`-записи. Сервис работает
на **апексе** `tradinghouse.space`, поэтому нужны записи и на `@`, и на `www`:

| Тип | Имя        | Значение         | TTL  |
|-----|------------|------------------|------|
| A   | @          | `<IP сервера>`   | 300  |
| A   | www        | `<IP сервера>`   | 300  |

> Если разворачиваете на поддомене (например, `trade.tradinghouse.space`) —
> заведите `A`-запись на `trade` и поправьте имя в `Caddyfile`. Главное:
> имя в `Caddyfile` должно **точно** совпадать с тем, что открываете в браузере.

После этого `tradinghouse.space` будет резолвиться в IP.
Дождитесь распространения DNS — обычно 5–15 минут. Проверка из cmd на сервере:

```
nslookup tradinghouse.space
```

Должен вернуть IP сервера.

> **Важно:** если используете Cloudflare как DNS — в записи **отключите**
> «proxy» (серое облачко вместо оранжевого). Иначе Caddy не сможет получить
> сертификат через HTTP-01 challenge.

---

## 2. Установка зависимостей на сервере

Все команды — в **PowerShell от имени администратора**.

### 2.1 Python 3.11

Скачайте с https://www.python.org/downloads/windows/ → **Windows installer
(64-bit)**. При установке:

- ☑ «Add python.exe to PATH»
- ☑ «Install for all users» (через Customize → Advanced)
- Установите в `C:\Python311\`

Проверка:
```powershell
python --version    # 3.11.x
pip --version
```

### 2.2 MT5 терминал

Скачайте с сайта вашего брокера. Установите и запустите:

1. Войдите в свой счёт (логин + пароль + сервер).
2. **Tools → Options → Expert Advisors:**
   - ☑ «Allow algorithmic trading»
   - ☑ «Allow DLL imports»
3. **Tools → Options → Server:**
   - ☑ «Enable Auto Trading»
4. **File → Login to Trade Account → Save account information** (сохраняем
   пароль — иначе после reboot терминал не залогинится автоматически).

Чтобы MT5 запускался при старте Windows: создайте ярлык на `terminal64.exe`
и положите его в `shell:startup` (наберите эту строку в адресной строке
проводника — откроется папка автозапуска).

### 2.3 Git и клонирование репозитория

Скачайте Git for Windows: https://git-scm.com/download/win

```powershell
# Клонируем в C:\TradingHouse
cd C:\
git clone https://github.com/rotmistrLemke/MillionsKeeper.git TradingHouse
cd C:\TradingHouse
```

### 2.4 TA-Lib (нативный пакет — нужен отдельный wheel)

`TA-Lib` не ставится через `pip install` напрямую. Скачайте подходящий wheel
для Python 3.11 / Windows AMD64:
https://github.com/cgohlke/talib-build/releases

```powershell
# Пример: TA_Lib-0.4.32-cp311-cp311-win_amd64.whl
pip install C:\Users\Administrator\Downloads\TA_Lib-0.4.32-cp311-cp311-win_amd64.whl
```

### 2.5 Остальные зависимости проекта

```powershell
cd C:\TradingHouse
pip install -r requirements.txt
```

### 2.6 NSSM (Non-Sucking Service Manager)

```powershell
# Скачать nssm.cc/release/nssm-2.24.zip → распаковать
# Скопировать win64\nssm.exe в C:\Windows\System32\
Invoke-WebRequest https://nssm.cc/release/nssm-2.24.zip -OutFile $env:TEMP\nssm.zip
Expand-Archive $env:TEMP\nssm.zip -DestinationPath $env:TEMP\nssm
Copy-Item $env:TEMP\nssm\nssm-2.24\win64\nssm.exe C:\Windows\System32\
nssm version    # 2.24
```

### 2.7 Caddy

```powershell
# Скачиваем Caddy для Windows AMD64
New-Item -ItemType Directory -Force -Path C:\Caddy | Out-Null
Invoke-WebRequest https://github.com/caddyserver/caddy/releases/latest/download/caddy_windows_amd64.zip -OutFile $env:TEMP\caddy.zip
Expand-Archive $env:TEMP\caddy.zip -DestinationPath C:\Caddy
# Внутри будет caddy.exe
C:\Caddy\caddy.exe version
```

---

## 3. Настройка `.env` и `Caddyfile`

### 3.1 Учётные данные MT5

Создайте `C:\TradingHouse\.env` (этот файл в `.gitignore`, в репозиторий
не попадёт):

```
MT5_LOGIN=12345678
MT5_PASSWORD=ВашПарольMT5
MT5_SERVER=YourBroker-Demo
```

`MT5_LOGIN` — число счёта без кавычек. Имена ключей фиксированы и
читаются в `account.py`.

### 3.2 Caddyfile

Скопируйте шаблон:

```powershell
Copy-Item C:\TradingHouse\deploy\Caddyfile C:\Caddy\Caddyfile
notepad C:\Caddy\Caddyfile
```

Замените:

- `YOUR_EMAIL` → ваш e-mail (Let's Encrypt пришлёт уведомления при истечении
  сертификата — обычно их нет, обновляется автоматически)

Домен в шаблоне уже задан как `tradinghouse.space, www.tradinghouse.space`.
Если у вас другой домен — поправьте обе строки. Имя должно **точно** совпадать
с тем, что открываете в браузере, иначе Caddy отдаст самоподписанный сертификат.

---

## 4. Caddy (reverse-proxy + HTTPS)

Caddy ставим как Windows-сервис через NSSM. Под LocalSystem он работает
без проблем — ему профиля пользователя не требуется.

```powershell
cd C:\TradingHouse\deploy
PowerShell -ExecutionPolicy Bypass -File .\install_caddy.ps1
```

Скрипт:

1. Регистрирует `Caddy` как Windows-сервис
2. Открывает 80/443 в файрволе
3. Запускает Caddy

Проверка:

```powershell
nssm status Caddy        # должно быть SERVICE_RUNNING
curl http://127.0.0.1    # ответит редиректом на HTTPS
```

Если Caddy не получает SSL — в `C:\Caddy\logs\caddy.err.log` будет ошибка
(чаще всего: DNS ещё не распространился, либо Cloudflare с включенным proxy).

---

## 5. TradingHouse как Scheduled Task

**Почему не Windows-сервис:** MT5 хранит настройки и сохранённый счёт в
`%APPDATA%\Roaming\MetaQuotes`. Сервис под LocalSystem не имеет этого
профиля — терминал в session 0 запускается без логина и алготрейдинга.
Возни много, надёжность плохая.

**Решение:** Task Scheduler запускает бота при логине Administrator.
Бот работает в той же сессии, где открыт MT5 (запущенный из RDP-стартапа).
Всё работает как при `python main.py` руками, только автоматически.

### 5.1 Подготовка `run_task.ps1`

Откройте `C:\TradingHouse\deploy\run_task.ps1` и **отредактируйте**:

```powershell
$PythonExe     = "C:\Program Files\Python313\python.exe"   # ваша версия
$AppPort       = "8080"
$Domain        = "tradinghouse.space"
$AdminPassword = "ВашПарольДляAdmin"
```

`run_task.ps1` — это wrapper, который Task Scheduler вызовет: он задаёт
env-переменные и перенаправляет логи в `logs\task.out.log`.

### 5.2 MT5 в автозагрузке

`shell:startup` (вставить эту строку в адресную строку проводника)
→ положить туда ярлык на `terminal64.exe`. После авто-логина MT5
запустится первым, бот — следом (через ~3 сек после старта Task).

В MT5 сохраните пароль через **File → Login to Trade Account →
Save account information**.

### 5.3 Регистрация задачи

```powershell
cd C:\TradingHouse\deploy
PowerShell -ExecutionPolicy Bypass -File .\install_task.ps1
```

Скрипт:

1. Удаляет старый NSSM-сервис `TradingHouse` (если был с прошлой попытки)
2. Удаляет старую задачу с тем же именем (если была)
3. Создаёт `Scheduled Task → Trigger: At log on (Administrator)
   → Run as Administrator (Interactive) → Highest privileges`
4. Стартует прямо сейчас (не нужно ребутить)

После запуска через ~10 секунд:

```powershell
curl http://127.0.0.1:8080/health   # бот напрямую (с самого сервера)
curl https://tradinghouse.space/health  # через Caddy (с любой машины)
```

Откройте `https://tradinghouse.space` — форма логина. Вход: `admin` /
`$AdminPassword`.

### 5.4 Авто-логин Administrator

Чтобы после ребута сервера бот стартовал без RDP:

```powershell
PowerShell -ExecutionPolicy Bypass -File C:\TradingHouse\deploy\enable_autologon.ps1
```

Запросит пароль Administrator. После настройки — после Restart-Computer
Windows автологинит, MT5 запускается из shell:startup, бот — из Task
Scheduler.

> ⚠️ **Безопасность:** пароль Administrator хранится в реестре в plain text
> (Windows ограничение). Это приемлемо только если RDP закрыт от интернета
> (VPN или whitelist по IP) и пароль длинный/уникальный.

---

## 6. Безопасность

### 6.1 Минимально

- ☑ HTTPS-only (Caddy сам редиректит HTTP → HTTPS)
- ☑ Бот слушает `127.0.0.1`, наружу не торчит
- ☑ Пароли хешированы (pbkdf2_sha256), JWT с недельным TTL
- ☑ В `.gitignore`: `.env`, `users.json`, `.jwt_secret`, `streams.json`

### 6.2 Рекомендую

- **RDP только по VPN** или с whitelist по IP. По умолчанию открытый RDP — это
  ежедневные брутфорс-атаки на ваш сервер. Меньше зло — сменить порт RDP с
  3389 и поставить **Microsoft Remote Desktop Gateway** или **WireGuard**.
- **Fail2ban-аналог для Windows**: `IPBan` (https://github.com/DigitalRuby/IPBan).
- **Длинный admin-пароль** в `$AdminPassword` (16+ символов).
- **Двухфакторка для регистратора домена** — если перехватят домен, перехватят
  HTTPS.

### 6.3 Что менять регулярно

- Пароли пользователей — раз в 3 месяца через UI
- `JWT_SECRET` — раз в год (выйдет в `.jwt_secret`, удалить, перезапустить
  TradingHouse — все сессии разлогинятся)

---

## 7. Бэкапы

### 7.1 Что бэкапить

- `users.json` — учётные записи
- `streams.json` — конфигурация потоков
- `.jwt_secret` — без него все токены инвалидны
- `.env` — учётка MT5
- (опционально) `logs/`

### 7.2 Скрипт

`deploy\backup.ps1` собирает всё в zip-архив с датой и хранит 30 дней.

### 7.3 Регулярный запуск

```powershell
# Создать задачу в Task Scheduler — раз в сутки в 3:00.
$action  = New-ScheduledTaskAction -Execute "PowerShell.exe" `
           -Argument "-ExecutionPolicy Bypass -File C:\TradingHouse\deploy\backup.ps1"
$trigger = New-ScheduledTaskTrigger -Daily -At 3am
Register-ScheduledTask -TaskName "TradingHouse Backup" -Action $action -Trigger $trigger -RunLevel Highest
```

Бэкапы — в `C:\TradingHouse-backups\`. Регулярно копируйте их **на другой
носитель** (OneDrive / S3 / другой VPS) — иначе если упадёт диск VPS, бэкап
сгорит вместе с оригиналом.

---

## 8. Эксплуатация

### Управление ботом (Scheduled Task)

```powershell
Get-ScheduledTaskInfo -TaskName TradingHouse   # время последнего запуска и код выхода
Start-ScheduledTask   -TaskName TradingHouse
Stop-ScheduledTask    -TaskName TradingHouse
```

Задача автоматически перезапускает себя при крахе процесса (до 999 попыток
с интервалом 1 мин — настраивается в `install_task.ps1`).

### Управление Caddy (NSSM-сервис)

```powershell
nssm status   Caddy
nssm restart  Caddy
nssm stop     Caddy
```

### Логи

- Бот:   `C:\TradingHouse\logs\task.out.log` (ротация на 50 MB → `.old`)
- Caddy: `C:\Caddy\logs\caddy.out.log`, `caddy.err.log`, `access.log`

Посмотреть последние 200 строк бота в реальном времени:

```powershell
Get-Content C:\TradingHouse\logs\task.out.log -Tail 200 -Wait
```

### Обновление кода

```powershell
Stop-ScheduledTask -TaskName TradingHouse
cd C:\TradingHouse
git pull
pip install -r requirements.txt        # если зависимости изменились
Start-ScheduledTask -TaskName TradingHouse
```

Если изменился `Caddyfile` — `nssm restart Caddy`.

### Если Let's Encrypt не выдаёт сертификат

- Проверьте, что `A`-запись DNS указывает на ваш IP (см. шаг 1).
- Если используете Cloudflare — отключите proxy (серое облачко).
- Файрвол: порт 80 должен быть открыт (Caddy через него делает HTTP-01
  challenge).
- Логи Caddy: `C:\Caddy\logs\caddy.err.log`.

### Если бот не запускается

- `Get-ScheduledTaskInfo TradingHouse` — посмотрите `LastTaskResult`. `0x0`
  значит OK; иначе — Action не нашёл `powershell.exe`/`run_task.ps1`.
- `C:\TradingHouse\logs\task.out.log` — последние строки, traceback.
- Запустите `python C:\TradingHouse\main.py` руками в RDP-сессии — увидите
  ошибки в консоли.

### Если бот не подключается к MT5

- Терминал MT5 должен быть **запущен в той же сессии** (RDP под Administrator).
  Проверьте через Task Manager — `terminal64.exe` есть.
- В терминале: **Tools → Options → Expert Advisors** — «Allow algorithmic
  trading» включено.
- В `.env` — `MT5_LOGIN`, `MT5_PASSWORD`, `MT5_SERVER` правильные.
- Если меняли пароль на счёте — обновите `.env` и перезапустите задачу.

---

## 8. Что не входит в эту инструкцию

- **Мониторинг и алерты** (UptimeRobot, Better Uptime — пингуют `/health`
  и шлют SMS/email при падении)
- **Off-site репликация бэкапов** (rclone в S3/Backblaze)
- **Multi-region failover** — для одного брокерского аккаунта это не нужно

Если что-то из этого нужно — скажите, добавлю.
