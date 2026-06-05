# install_task.ps1 — регистрирует TradingHouse как Scheduled Task,
# запускающуюся при логине Administrator.
#
# Преимущество перед NSSM-сервисом: бот работает в той же сессии, что и
# RDP-юзер, поэтому MT5 (со всеми настройками и сохранённым логином)
# доступен через стандартный IPC. Никакой возни с MetaQuotes-профилем
# в systemprofile.
#
# Запускать в PowerShell от имени администратора.

#requires -RunAsAdministrator

# ── Параметры (отредактировать!) ─────────────────────────────────────
$AppRoot   = "C:\TradingHouse"
$RunAsUser = "Administrator"     # тот, под кем настраивали MT5 в RDP
# ──────────────────────────────────────────────────────────────────────

$ErrorActionPreference = "Stop"
$Wrapper = Join-Path $AppRoot "deploy\run_task.ps1"

if (-not (Test-Path $Wrapper)) { throw "run_task.ps1 не найден: $Wrapper" }
if (-not (Test-Path "$AppRoot\main.py")) { throw "main.py не найден в $AppRoot" }

# ── 1. Удалить старый NSSM-сервис, если был ─────────────────────────
$old = Get-Service "TradingHouse" -ErrorAction SilentlyContinue
if ($old) {
    Write-Host "Удаляю старый NSSM-сервис TradingHouse..." -ForegroundColor Yellow
    if (Get-Command nssm -ErrorAction SilentlyContinue) {
        $ErrorActionPreference = 'Continue'
        & nssm stop TradingHouse *>$null
        & nssm remove TradingHouse confirm *>$null
        $ErrorActionPreference = 'Stop'
    } else {
        sc.exe stop TradingHouse | Out-Null
        sc.exe delete TradingHouse | Out-Null
    }
}

# ── 2. Удалить старую задачу, если есть ─────────────────────────────
if (Get-ScheduledTask -TaskName "TradingHouse" -ErrorAction SilentlyContinue) {
    Write-Host "Удаляю старую задачу TradingHouse..." -ForegroundColor Yellow
    Unregister-ScheduledTask -TaskName "TradingHouse" -Confirm:$false
}

# ── 3. Создать новую задачу ──────────────────────────────────────────
Write-Host "Создаю Scheduled Task TradingHouse..." -ForegroundColor Cyan

$action = New-ScheduledTaskAction `
    -Execute "powershell.exe" `
    -Argument "-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$Wrapper`"" `
    -WorkingDirectory $AppRoot

# Trigger: при логине указанного пользователя.
$trigger = New-ScheduledTaskTrigger -AtLogOn -User $RunAsUser

# Settings: автоперезапуск при ошибке, без таймаута, не останавливать при простое.
$settings = New-ScheduledTaskSettingsSet `
    -StartWhenAvailable `
    -RestartCount 999 `
    -RestartInterval (New-TimeSpan -Minutes 1) `
    -ExecutionTimeLimit ([TimeSpan]::Zero) `
    -DontStopOnIdleEnd `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries

# Principal: запускать как пользователь (interactive), с повышенными правами.
$principal = New-ScheduledTaskPrincipal `
    -UserId $RunAsUser `
    -LogonType Interactive `
    -RunLevel Highest

Register-ScheduledTask `
    -TaskName "TradingHouse" `
    -Description "TradingHouse trading bot + Web Dashboard (FastAPI + MT5)" `
    -Action $action `
    -Trigger $trigger `
    -Settings $settings `
    -Principal $principal | Out-Null

Write-Host "  Задача создана." -ForegroundColor Green

# ── 4. Стартануть прямо сейчас (не ждать ребута) ─────────────────────
Write-Host "Запускаю задачу..." -ForegroundColor Cyan
Start-ScheduledTask -TaskName "TradingHouse"
Start-Sleep -Seconds 3

$task = Get-ScheduledTask -TaskName "TradingHouse"
$info = $task | Get-ScheduledTaskInfo
Write-Host ""
Write-Host "Состояние:    " -NoNewline; Write-Host $task.State -ForegroundColor Yellow
Write-Host "Last run at:  " -NoNewline; Write-Host $info.LastRunTime
Write-Host "Last result:  " -NoNewline; Write-Host ("0x{0:X}" -f $info.LastTaskResult)
Write-Host ""
Write-Host "Лог:           $AppRoot\logs\task.out.log" -ForegroundColor Cyan
Write-Host "Проверка:      curl http://127.0.0.1:8080/health (через ~10 сек)"
Write-Host ""
Write-Host "Управление:"
Write-Host "  Start-ScheduledTask    -TaskName TradingHouse"
Write-Host "  Stop-ScheduledTask     -TaskName TradingHouse"
Write-Host "  Get-ScheduledTaskInfo  -TaskName TradingHouse"
