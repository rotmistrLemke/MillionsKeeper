# run_task.ps1 — wrapper, который Task Scheduler запускает при логине Administrator.
#
# Зачем wrapper нужен:
#   - Передать env-переменные процессу python (Task Scheduler сам не задаёт env)
#   - Перенаправить stdout/stderr в лог-файл (Task Scheduler stdout идёт в /dev/null)
#   - Обеспечить ожидание процесса (Task Scheduler ждёт завершения action)
#
# Параметры — в одном месте, чтобы их легко править без перерегистрации задачи.

$AppRoot       = "C:\TradingHouse"
$PythonExe     = "C:\Program Files\Python313\python.exe"   # уточнить если другая версия
$AppPort       = "8080"
$Domain        = "tradinghouse.space"
$AdminPassword = "P@ssword"

# ── Подготовка лога ──────────────────────────────────────────────────
$LogDir  = Join-Path $AppRoot "logs"
New-Item -ItemType Directory -Force -Path $LogDir | Out-Null
$LogFile = Join-Path $LogDir "task.out.log"

# Простая ротация: если лог > 50 MB — переименовать в .old, начать новый.
if ((Test-Path $LogFile) -and ((Get-Item $LogFile).Length -gt 52428800)) {
    $bak = "$LogFile.old"
    if (Test-Path $bak) { Remove-Item $bak -Force }
    Rename-Item -Path $LogFile -NewName "$LogFile.old"
}

# ── Кодировка stdout дочернего процесса ──────────────────────────────
# Python пишет UTF-8 (см. PYTHONUTF8/PYTHONIOENCODING ниже), но PowerShell
# по умолчанию декодирует stdout через cp866 → кракозябры в логе.
# Принудительно ставим UTF-8 на оба конца pipeline'а.
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding           = [System.Text.Encoding]::UTF8

# ── Env-переменные для python ────────────────────────────────────────
# UTF-8 mode: иначе print() с кириллицей валит cp1252 codec error и
# реальная причина падения MT5 / других модулей теряется.
$env:PYTHONUTF8       = "1"
$env:PYTHONIOENCODING = "utf-8"

$env:HOST           = "127.0.0.1"
$env:PORT           = $AppPort
$env:TRUSTED_HOSTS  = "$Domain,localhost,127.0.0.1"
$env:ADMIN_PASSWORD = $AdminPassword
# MT5 — креды берёт из C:\TradingHouse\.env (load_dotenv). Path не передаём:
# в нашей сессии MT5 уже запущен и залогинен через RDP-стартап, mt5.initialize()
# просто attach-ится к нему.

# ── Зачистка прошлого инстанса ──────────────────────────────────────
# Если предыдущий python.exe завис (uvicorn не отпустил сокет, или MT5 DLL
# крашнулся с access violation) — порт 8080 останется занят, новый запуск
# словит WinError 10048 и упадёт. Перед стартом гасим всё, что слушает 8080.
try {
    $owners = Get-NetTCPConnection -LocalPort $AppPort -State Listen -ErrorAction Stop |
              Select-Object -ExpandProperty OwningProcess -Unique
    foreach ($procId in $owners) {
        "Killing stale process PID=$procId holding port $AppPort" |
            Out-File -FilePath $LogFile -Append -Encoding utf8
        Stop-Process -Id $procId -Force -ErrorAction SilentlyContinue
    }
    if ($owners) { Start-Sleep -Seconds 2 }  # дать ОС освободить сокет
} catch {
    # порт свободен — Get-NetTCPConnection кидает ошибку, это норма
}

# ── Запуск ───────────────────────────────────────────────────────────
"=== task started $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') ===" |
    Out-File -FilePath $LogFile -Append -Encoding utf8

Set-Location $AppRoot
& $PythonExe "$AppRoot\main.py" *>&1 |
    Out-File -FilePath $LogFile -Append -Encoding utf8

"=== task exited $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') exit=$LASTEXITCODE ===" |
    Out-File -FilePath $LogFile -Append -Encoding utf8
exit $LASTEXITCODE
