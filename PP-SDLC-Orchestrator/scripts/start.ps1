<#
.SYNOPSIS
    Starts the backend API (FastAPI/uvicorn) for local development.
    Run scripts\setup.ps1 first if the venv or DB don't exist yet.
#>
$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
$backend = Join-Path $repoRoot "backend"
$venvPython = Join-Path $backend ".venv\Scripts\python.exe"

if (-not (Test-Path $venvPython)) {
    Write-Error "Backend venv not found. Run .\scripts\setup.ps1 first."
    exit 1
}

Write-Host "Starting backend on http://127.0.0.1:8000 (docs at /docs) ..." -ForegroundColor Cyan
Push-Location $backend
try {
    & $venvPython -m uvicorn app.main:app --reload --port 8000
} finally {
    Pop-Location
}
