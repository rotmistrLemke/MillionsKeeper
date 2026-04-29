# install_caddy.ps1 — Caddy как Windows-сервис через NSSM + порты 80/443.
# Caddy без проблем работает под LocalSystem (никаких профилей не требует).
# TradingHouse поднимается отдельно через install_task.ps1.

#requires -RunAsAdministrator

# ── Параметры ────────────────────────────────────────────────────────
$CaddyExe  = "C:\Caddy\caddy.exe"
$Caddyfile = "C:\Caddy\Caddyfile"
# ──────────────────────────────────────────────────────────────────────

$ErrorActionPreference = "Stop"

if (-not (Get-Command nssm -ErrorAction SilentlyContinue)) {
    throw "Не найден 'nssm' в PATH. См. DEPLOY.md шаг 2.6."
}
if (-not (Test-Path $CaddyExe))  { throw "caddy.exe не найден: $CaddyExe" }
if (-not (Test-Path $Caddyfile)) { throw "Caddyfile не найден: $Caddyfile" }

# Helper: NSSM пишет stderr в UTF-16. Без этой обёртки $ErrorActionPreference=Stop
# превращает любой такой вывод в NativeCommandError.
function Invoke-Nssm {
    $old = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    try { & nssm @args *>$null } finally { $ErrorActionPreference = $old }
}

# ── Удалить старый сервис Caddy, если был ───────────────────────────
$old = Get-Service "Caddy" -ErrorAction SilentlyContinue
if ($old) {
    Write-Host "Удаляю существующий сервис Caddy..." -ForegroundColor Yellow
    if ($old.Status -eq 'Running') { Invoke-Nssm stop Caddy }
    Invoke-Nssm remove Caddy confirm
}

# ── Регистрация ──────────────────────────────────────────────────────
Write-Host "Регистрирую сервис Caddy..." -ForegroundColor Cyan
& nssm install Caddy $CaddyExe "run" "--config" $Caddyfile
& nssm set Caddy AppDirectory  (Split-Path $CaddyExe)
& nssm set Caddy DisplayName   "Caddy Web Server"
& nssm set Caddy Description   "Reverse proxy + auto-HTTPS"
& nssm set Caddy Start         SERVICE_AUTO_START

$LogDir = "C:\Caddy\logs"
New-Item -ItemType Directory -Force -Path $LogDir | Out-Null
& nssm set Caddy AppStdout      "$LogDir\caddy.out.log"
& nssm set Caddy AppStderr      "$LogDir\caddy.err.log"
& nssm set Caddy AppRotateFiles 1
& nssm set Caddy AppRotateBytes 10485760
& nssm set Caddy AppRotateOnline 1
& nssm set Caddy AppExit         Default Restart
& nssm set Caddy AppRestartDelay 5000

Write-Host "  Запускаю Caddy..." -ForegroundColor Yellow
& nssm start Caddy

# ── Файрвол ──────────────────────────────────────────────────────────
Write-Host "Открываю порты 80/443..." -ForegroundColor Cyan
foreach ($port in @(80, 443)) {
    $name = if ($port -eq 80) { "Caddy HTTP" } else { "Caddy HTTPS" }
    if (-not (Get-NetFirewallRule -DisplayName $name -ErrorAction SilentlyContinue)) {
        New-NetFirewallRule -DisplayName $name -Direction Inbound -Protocol TCP `
                            -LocalPort $port -Action Allow | Out-Null
    }
}

Write-Host ""
Write-Host "Caddy status: " -NoNewline; & nssm status Caddy
Write-Host "Лог:          $LogDir\caddy.out.log"
