<#
.SYNOPSIS
    Idempotent local setup: creates the backend venv, installs dependencies,
    applies database migrations. Safe to re-run.
#>
$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
$backend = Join-Path $repoRoot "backend"

Write-Host "== PP-SDLC-Orchestrator setup ==" -ForegroundColor Cyan

python --version | Out-Null
if ($LASTEXITCODE -ne 0) {
    Write-Error "Python not found on PATH. Install Python 3.11+ before continuing."
    exit 1
}

$venvPython = Join-Path $backend ".venv\Scripts\python.exe"
if (-not (Test-Path $venvPython)) {
    Write-Host "Creating backend virtual environment..."
    python -m venv (Join-Path $backend ".venv")
}

Write-Host "Installing backend dependencies..."
& $venvPython -m pip install --upgrade pip -q
& $venvPython -m pip install -r (Join-Path $backend "requirements.txt") -q

Write-Host "Applying database migrations..."
Push-Location $backend
try {
    & $venvPython -m alembic upgrade head
} finally {
    Pop-Location
}

Write-Host "Setup complete." -ForegroundColor Green
Write-Host "Next: .\scripts\start.ps1 to run the backend, or .\scripts\test.ps1 to run tests."
