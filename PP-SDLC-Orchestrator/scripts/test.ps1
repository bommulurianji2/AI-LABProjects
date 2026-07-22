<#
.SYNOPSIS
    Runs the backend test suite (unit + integration).
#>
$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
$backend = Join-Path $repoRoot "backend"
$venvPython = Join-Path $backend ".venv\Scripts\python.exe"

if (-not (Test-Path $venvPython)) {
    Write-Error "Backend venv not found. Run .\scripts\setup.ps1 first."
    exit 1
}

Push-Location $backend
try {
    & $venvPython -m pytest -q
    exit $LASTEXITCODE
} finally {
    Pop-Location
}
