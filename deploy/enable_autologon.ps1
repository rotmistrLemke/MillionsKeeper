# enable_autologon.ps1 — настраивает Windows на авто-логин Administrator.
#
# Зачем нужен: TradingHouse запускается как Scheduled Task "при логине".
# После reboot сервера задача стартует, только если кто-то залогинился.
# Без авто-логина после ребута бот будет ждать вашего RDP.
#
# Безопасность: пароль хранится в реестре HKLM\Winlogon\DefaultPassword
# в виде PLAINTEXT (Windows ограничение). Это приемлемо, если:
#   - VPS виден в интернете только через Caddy на 443/80
#   - RDP только по VPN или с whitelist по IP
#   - Пароль admin длинный и уникальный
#
# Чтобы отключить — Disable-AutoLogon (см. конец файла).

#requires -RunAsAdministrator

param(
    [string]$User     = "Administrator",
    [string]$Password = ""
)

if (-not $Password) {
    $sec      = Read-Host "Пароль для $User" -AsSecureString
    $Password = [System.Net.NetworkCredential]::new("", $sec).Password
}

$RegPath = "HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Winlogon"

Set-ItemProperty $RegPath -Name "AutoAdminLogon"   -Value "1"        -Type String
Set-ItemProperty $RegPath -Name "DefaultUserName"  -Value $User      -Type String
Set-ItemProperty $RegPath -Name "DefaultPassword"  -Value $Password  -Type String
Set-ItemProperty $RegPath -Name "DefaultDomainName" -Value $env:COMPUTERNAME -Type String
# Если был AutoLogonCount — обнулить, чтобы не было лимита.
Remove-ItemProperty $RegPath -Name "AutoLogonCount" -ErrorAction SilentlyContinue

Write-Host "Авто-логин для $User включён." -ForegroundColor Green
Write-Host ""
Write-Host "Чтобы отключить:"
Write-Host "  Set-ItemProperty '$RegPath' AutoAdminLogon '0'"
Write-Host "  Remove-ItemProperty '$RegPath' DefaultPassword"
