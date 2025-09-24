param(
    [switch]$VerboseOutput
)

$ErrorActionPreference = 'Stop'

# Resolve important paths
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$sprint2Dir = Split-Path -Parent $scriptDir
$repoRoot  = Split-Path -Parent $sprint2Dir
$pythonScript = Join-Path $scriptDir 'analyze_rqs.py'
$tablesScript = Join-Path $scriptDir 'generate_report_tables.py'

if (-not (Test-Path $pythonScript)) {
    Write-Error "Python script not found: $pythonScript"
}

# Try to activate venv if present
$venvActivate = Join-Path $repoRoot '.venv\Scripts\Activate.ps1'
if (Test-Path $venvActivate) {
    if ($VerboseOutput) { Write-Host "Activating venv: $venvActivate" -ForegroundColor Cyan }
    . $venvActivate
} else {
    if ($VerboseOutput) { Write-Host "No venv found at $venvActivate. Using system Python." -ForegroundColor Yellow }
}

# Ensure we run from repo root to keep relative paths stable
Set-Location $repoRoot

# Run analysis with plots
if ($VerboseOutput) { Write-Host "Running: python `"$pythonScript`" --plots" -ForegroundColor Green }
python "$pythonScript" --plots

# Generate auto tables inside the report (if script exists)
if (Test-Path $tablesScript) {
    if ($VerboseOutput) { Write-Host "Running: python `"$tablesScript`" (inject tables)" -ForegroundColor Green }
    python "$tablesScript"
}

Write-Host "Analysis complete. Outputs refreshed under sprint2/data/processed (CSV + plots) and tables injected in sprint2/docs/RELATORIO.md." -ForegroundColor Green
