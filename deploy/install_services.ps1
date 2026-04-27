# install_services.ps1 — регистрирует TradingHouse и Caddy как Windows-сервисы
# через NSSM. Запускать в PowerShell от имени администратора.
#
# Перед запуском:
#   1. Установить Python 3.11+ и зависимости (pip install -r requirements.txt)
#   2. Установить MetaTrader5 терминал (тот же broker, под которым работает бот)
#   3. Скачать NSSM: https://nssm.cc/download → положить nssm.exe в PATH
#   4. Скачать Caddy: https://caddyserver.com/download (для Windows AMD64)
#      → положить caddy.exe в C:\Caddy\caddy.exe
#   5. Подготовить C:\Caddy\Caddyfile (см. deploy\Caddyfile из репо)
#   6. Заполнить переменные ниже под ваш сервер.

#requires -RunAsAdministrator

# ── Параметры (отредактировать!) ─────────────────────────────────────
$AppRoot       = "C:\TradingHouse"          # куда клонирован репозиторий
$PythonExe     = "C:\Python311\python.exe"  # путь к python.exe
$AppPort       = "8080"                     # порт бота (внутренний, локальный)
$Domain        = "trade.example.com"        # ваш домен (для TRUSTED_HOSTS)
$AdminPassword = "ИЗМЕНИ_МЕНЯ"              # пароль admin при первом запуске
$CaddyExe      = "C:\Caddy\caddy.exe"
$Caddyfile     = "C:\Caddy\Caddyfile"
# ──────────────────────────────────────────────────────────────────────

$ErrorActionPreference = "Stop"

function Test-Admin {
    $id = [Security.Principal.WindowsIdentity]::GetCurrent()
    $p  = New-Object Security.Principal.WindowsPrincipal($id)
    if (-not $p.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
        throw "Запустите PowerShell от имени администратора."
    }
}

function Test-Command($name) {
    if (-not (Get-Command $name -ErrorAction SilentlyContinue)) {
        throw "Не найден '$name' в PATH. Прочитайте инструкцию в начале файла."
    }
}

Test-Admin
Test-Command "nssm"

if (-not (Test-Path $PythonExe))   { throw "Python не найден: $PythonExe" }
if (-not (Test-Path "$AppRoot\main.py")) { throw "main.py не найден в $AppRoot" }
if (-not (Test-Path $CaddyExe))    { throw "caddy.exe не найден: $CaddyExe" }
if (-not (Test-Path $Caddyfile))   { throw "Caddyfile не найден: $Caddyfile" }

# NSSM пишет stderr-сообщения в UTF-16 — глушим оба стрима через Out-Null,
# а наличие сервиса проверяем заранее через Get-Service, чтобы не было
# "Can't open service!" при первом запуске.
function Remove-IfInstalled([string]$Name) {
    if (Get-Service $Name -ErrorAction SilentlyContinue) {
        Write-Host "  Удаляю существующий сервис $Name..." -ForegroundColor Yellow
        & nssm stop $Name 2>&1 | Out-Null
        & nssm remove $Name confirm 2>&1 | Out-Null
    }
}

# ── 1. TradingHouse сервис ───────────────────────────────────────────
Write-Host "Регистрирую сервис TradingHouse..." -ForegroundColor Cyan
Remove-IfInstalled "TradingHouse"

& nssm install TradingHouse $PythonExe "$AppRoot\main.py"
& nssm set TradingHouse AppDirectory $AppRoot
& nssm set TradingHouse DisplayName "TradingHouse Trading Bot"
& nssm set TradingHouse Description "Алготрейдинг + Web Dashboard (FastAPI + MT5)"
& nssm set TradingHouse Start SERVICE_AUTO_START

# Env: бот слушает только локальный интерфейс, Caddy проксирует извне.
& nssm set TradingHouse AppEnvironmentExtra `
    "HOST=127.0.0.1" `
    "PORT=$AppPort" `
    "TRUSTED_HOSTS=$Domain,localhost,127.0.0.1" `
    "ADMIN_PASSWORD=$AdminPassword"

# Логи stdout/stderr в файл с ротацией.
$LogDir = "$AppRoot\logs"
New-Item -ItemType Directory -Force -Path $LogDir | Out-Null
& nssm set TradingHouse AppStdout "$LogDir\service.out.log"
& nssm set TradingHouse AppStderr "$LogDir\service.err.log"
& nssm set TradingHouse AppRotateFiles 1
& nssm set TradingHouse AppRotateBytes 10485760     # 10 MB
& nssm set TradingHouse AppRotateOnline 1

# Перезапуск при падении.
& nssm set TradingHouse AppExit Default Restart
& nssm set TradingHouse AppRestartDelay 5000

Write-Host "  Запускаю TradingHouse..." -ForegroundColor Yellow
& nssm start TradingHouse

# ── 2. Caddy сервис ──────────────────────────────────────────────────
Write-Host "Регистрирую сервис Caddy..." -ForegroundColor Cyan
Remove-IfInstalled "Caddy"

& nssm install Caddy $CaddyExe "run" "--config" $Caddyfile
& nssm set Caddy AppDirectory (Split-Path $CaddyExe)
& nssm set Caddy DisplayName "Caddy Web Server"
& nssm set Caddy Description "Reverse proxy + auto-HTTPS"
& nssm set Caddy Start SERVICE_AUTO_START

$CaddyLogDir = "C:\Caddy\logs"
New-Item -ItemType Directory -Force -Path $CaddyLogDir | Out-Null
& nssm set Caddy AppStdout "$CaddyLogDir\caddy.out.log"
& nssm set Caddy AppStderr "$CaddyLogDir\caddy.err.log"
& nssm set Caddy AppRotateFiles 1
& nssm set Caddy AppRotateBytes 10485760
& nssm set Caddy AppRotateOnline 1
& nssm set Caddy AppExit Default Restart
& nssm set Caddy AppRestartDelay 5000

Write-Host "  Запускаю Caddy..." -ForegroundColor Yellow
& nssm start Caddy

# ── Файрвол ──────────────────────────────────────────────────────────
Write-Host "Открываю порты 80/443 в файрволе..." -ForegroundColor Cyan
New-NetFirewallRule -DisplayName "Caddy HTTP"  -Direction Inbound -Protocol TCP -LocalPort 80  -Action Allow -ErrorAction SilentlyContinue
New-NetFirewallRule -DisplayName "Caddy HTTPS" -Direction Inbound -Protocol TCP -LocalPort 443 -Action Allow -ErrorAction SilentlyContinue

# Порт бота (8080) НЕ открываем — Caddy ходит через 127.0.0.1.

Write-Host "" -ForegroundColor Green
Write-Host "Готово." -ForegroundColor Green
Write-Host "  TradingHouse status: " -NoNewline; & nssm status TradingHouse
Write-Host "  Caddy status:        " -NoNewline; & nssm status Caddy
Write-Host ""
Write-Host "Проверка:" -ForegroundColor Cyan
Write-Host "  curl http://127.0.0.1:$AppPort/health    # бот напрямую"
Write-Host "  curl https://$Domain/health             # через Caddy + HTTPS"
Write-Host ""
Write-Host "Логи:" -ForegroundColor Cyan
Write-Host "  $LogDir\service.out.log"
Write-Host "  $CaddyLogDir\caddy.out.log"
