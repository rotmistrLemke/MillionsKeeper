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
# Путь к terminal64.exe — обязателен в режиме сервиса, иначе IPC к MT5 не
# поднимается (LocalSystem ≠ RDP-сессия). Найдите свой через `where /R "C:\Program Files" terminal64.exe`.
$Mt5Path       = "C:\Program Files\MetaTrader 5\terminal64.exe"
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
if (-not (Test-Path $Mt5Path))     { throw "MT5 terminal не найден: $Mt5Path (см. `$Mt5Path в шапке скрипта)" }
if (-not (Test-Path $CaddyExe))    { throw "caddy.exe не найден: $CaddyExe" }
if (-not (Test-Path $Caddyfile))   { throw "Caddyfile не найден: $Caddyfile" }

# NSSM пишет stderr в UTF-16 и любая такая строка с $ErrorActionPreference=Stop
# превращается в NativeCommandError и роняет скрипт. Invoke-Nssm временно
# выключает Stop вокруг nssm-вызова и заглушает все стримы.
function Invoke-Nssm {
    $old = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    try {
        & nssm @args *>$null
    } finally {
        $ErrorActionPreference = $old
    }
}

function Remove-IfInstalled([string]$Name) {
    $svc = Get-Service $Name -ErrorAction SilentlyContinue
    if (-not $svc) { return }
    Write-Host "  Удаляю существующий сервис $Name..." -ForegroundColor Yellow
    if ($svc.Status -eq 'Running') {
        Invoke-Nssm stop $Name
    }
    Invoke-Nssm remove $Name confirm
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
# MT5_PATH позволяет initialize() запускать терминал в той же сессии,
# что и сервис — без него получим No IPC connection.
& nssm set TradingHouse AppEnvironmentExtra `
    "HOST=127.0.0.1" `
    "PORT=$AppPort" `
    "TRUSTED_HOSTS=$Domain,localhost,127.0.0.1" `
    "ADMIN_PASSWORD=$AdminPassword" `
    "MT5_PATH=$Mt5Path"

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
