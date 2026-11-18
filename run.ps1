# .SYNOPSIS
# One‑command startup for the Asset Tracking and Anomaly Detection System.
# - Activates the existing Python virtual environment (backend\venv)
# - Installs missing Python/Node dependencies (only if needed)
# - Starts the Flask API (backend\app.py)
# - Starts the Vite dev server (frontend)
# - Checks that ports 5000 and 5173 are free
# - Waits for the health endpoint to become ready
# - Writes logs to backend.log & frontend.log
# - Gracefully shuts down both processes on Ctrl+C

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

# --------------------------- 1. Paths & helpers ---------------------------
$RootDir        = Split-Path -Parent $MyInvocation.MyCommand.Definition
$VenvScripts    = Join-Path $RootDir 'backend\venv\Scripts'
$PythonExe      = Join-Path $VenvScripts 'python.exe'
$PipExe         = Join-Path $VenvScripts 'pip.exe'
$FlaskApp       = Join-Path $RootDir 'backend\app.py'
$FrontendDir    = Join-Path $RootDir 'frontend'
$BackendLog     = Join-Path $RootDir 'backend.log'
$FrontendLog    = Join-Path $RootDir 'frontend.log'

function Write-Info($msg) { Write-Host "[INFO] $msg" -ForegroundColor Cyan }
function Write-Warn($msg) { Write-Host "[WARN] $msg" -ForegroundColor Yellow }
function Write-ErrorMsg($msg) { Write-Host "[ERROR] $msg" -ForegroundColor Red }

# --------------------------- 2. Verify tools ---------------------------
if (-not (Test-Path $PythonExe)) {
    Write-ErrorMsg "Python virtual‑env not found at $PythonExe. Run `python -m venv backend\venv` first."
    exit 1
}
if (-not (Get-Command npm -ErrorAction SilentlyContinue)) {
    Write-ErrorMsg "npm is not in PATH. Install Node.js (>= v20) and retry."
    exit 1
}

# --------------------------- 3. Install Python dependencies (if needed) ---------------------------
Write-Info "Ensuring Python dependencies are installed..."
$requirements = Join-Path $RootDir 'backend\requirements.txt'
if (Test-Path $requirements) {
    & $PipExe install -r $requirements | Out-Null
} else {
    Write-Warn "requirements.txt not found – skipping Python package install."
}

# --------------------------- 4. Install Node dependencies (if needed) ---------------------------
Write-Info "Checking Node dependencies..."
if (-not (Test-Path (Join-Path $FrontendDir 'node_modules'))) {
    Write-Info "Running `npm install` in frontend..."
    Push-Location $FrontendDir
    npm install | Out-Null
    Pop-Location
} else {
    Write-Info "Node modules already present."
}

# --------------------------- 5. Port availability checks ---------------------------
function Test-PortFree([int]$port) {
    $inUse = (Get-NetTCPConnection -LocalPort $port -ErrorAction SilentlyContinue).Count -gt 0
    return -not $inUse
}
if (-not (Test-PortFree 5000)) {
    Write-ErrorMsg "Port 5000 is already in use. Stop the other process or change FLASK_PORT."
    exit 1
}
if (-not (Test-PortFree 5173)) {
    Write-ErrorMsg "Port 5173 is already in use. Stop the other process or change Vite port."
    exit 1
}

# --------------------------- 6. Start Flask backend ---------------------------
Write-Info "Starting Flask backend (log → $BackendLog)..."
$backendJob = Start-Job -ScriptBlock {
    param($py,$app,$log)
    & $py $app *>&1 | Tee-Object -FilePath $log
} -ArgumentList $PythonExe, $FlaskApp, $BackendLog

# --------------------------- 7. Start Vite frontend ---------------------------
Write-Info "Starting Vite dev server (log → $FrontendLog)..."
$frontendJob = Start-Job -ScriptBlock {
    param($frontendDir,$log)
    Push-Location $frontendDir
    npm --prefix . run dev *>&1 | Tee-Object -FilePath $log
    Pop-Location
} -ArgumentList $FrontendDir, $FrontendLog

# --------------------------- 8. Wait for Flask health endpoint ---------------------------
$healthUrl = "http://127.0.0.1:5000/api/health"
Write-Info "Waiting for Flask health endpoint ($healthUrl) ..."
$maxAttempts = 30
$attempt = 0
while ($attempt -lt $maxAttempts) {
    try {
        $resp = Invoke-RestMethod -Uri $healthUrl -Method Get -TimeoutSec 2 -ErrorAction Stop
        if ($resp.status -eq 'healthy') { break }
    } catch {}
    Start-Sleep -Seconds 1
    $attempt++
}
if ($attempt -ge $maxAttempts) {
    Write-ErrorMsg "Flask did not become healthy after $maxAttempts seconds."
    Stop-Job $backendJob -Force
    Stop-Job $frontendJob -Force
    exit 1
}
Write-Info "✅ Flask API is healthy."

# --------------------------- 9. Display URLs ---------------------------
Write-Host "`n=== 🚀 Application URLs ===" -ForegroundColor Green
Write-Host "Backend API : http://127.0.0.1:5000/api/health"
Write-Host "Frontend UI : http://localhost:5173"
Write-Host "Logs        : backend.log , frontend.log`n"

# --------------------------- 10. Graceful shutdown handling ---------------------------
Write-Info "Press Ctrl+C to stop both services."
$null = Register-EngineEvent PowerShell.Exiting -Action {
    Write-Info "`nShutting down services..."
    if ($backendJob) { Stop-Job $backendJob -Force }
    if ($frontendJob) { Stop-Job $frontendJob -Force }
    Write-Info "All processes terminated."
} | Out-Null

while ($true) {
    Start-Sleep -Seconds 2
    foreach ($j in @($backendJob,$frontendJob)) {
        if ($j.State -eq 'Failed') {
            Write-ErrorMsg "A background job failed. Check $BackendLog / $FrontendLog for details."
            exit 1
        }
    }
}
