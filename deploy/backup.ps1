# backup.ps1 — копирует критичный стейт TradingHouse в zip-архив с датой.
# Запускать руками или через Task Scheduler (раз в сутки достаточно).
#
# Включается:
#   users.json      — учётные записи и хеши паролей
#   streams.json    — конфигурация потоков
#   active_state.json
#   .jwt_secret     — секрет подписи токенов (без него все юзеры разлогинятся)
#   .env            — креды MT5
#   logs\           — лог-файлы за последние 7 дней (опционально)

$AppRoot   = "C:\TradingHouse"
$BackupDir = "C:\TradingHouse-backups"

$ErrorActionPreference = "Stop"
New-Item -ItemType Directory -Force -Path $BackupDir | Out-Null

$ts   = Get-Date -Format "yyyyMMdd-HHmmss"
$dest = Join-Path $BackupDir "tradinghouse-$ts.zip"

$files = @()
foreach ($name in @("users.json", "streams.json", "active_state.json", ".jwt_secret", ".env")) {
    $p = Join-Path $AppRoot $name
    if (Test-Path $p) { $files += $p }
}

if (-not $files) {
    Write-Warning "Нет файлов для бэкапа в $AppRoot"
    exit 0
}

Compress-Archive -Path $files -DestinationPath $dest -CompressionLevel Optimal
Write-Host "Бэкап: $dest" -ForegroundColor Green

# Удаляем бэкапы старше 30 дней.
Get-ChildItem $BackupDir -Filter "tradinghouse-*.zip" |
    Where-Object { $_.LastWriteTime -lt (Get-Date).AddDays(-30) } |
    Remove-Item -Force
