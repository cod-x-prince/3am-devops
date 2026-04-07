# bootstrap.ps1
# IncidentEnv — Windows Bootstrap Script
# Run this once to set up the full dev environment
# Usage: .\bootstrap.ps1

param(
    [switch]$SkipRust,
    [switch]$SkipDashboard,
    [switch]$SkipOllama
)

$ErrorActionPreference = "Stop"
$ProjectRoot = $PSScriptRoot

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  IncidentEnv Bootstrap — Windows" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Step 0 — Windows Defender exclusions (CRITICAL for Rust build)
Write-Host "[0/7] Adding Windows Defender exclusions for Rust build dirs..." -ForegroundColor Yellow
Write-Host "     NOTE: If this fails, run PowerShell as Administrator and re-run bootstrap.ps1" -ForegroundColor DarkYellow
try {
    Add-MpPreference -ExclusionPath "$ProjectRoot\target"
    Add-MpPreference -ExclusionPath "$env:USERPROFILE\.cargo"
    Add-MpPreference -ExclusionPath "$env:USERPROFILE\.rustup"
    Write-Host "     Defender exclusions added." -ForegroundColor Green
} catch {
    Write-Host "     WARNING: Could not add Defender exclusions. Run as Admin if Rust build fails with os error 32." -ForegroundColor Red
}

# Step 1 — Check prerequisites
Write-Host ""
Write-Host "[1/7] Checking prerequisites..." -ForegroundColor Yellow

# Check Rust
try {
    $rustVersion = cargo --version
    Write-Host "     Rust: $rustVersion" -ForegroundColor Green
} catch {
    Write-Host "     ERROR: Rust not found. Install from https://rustup.rs/" -ForegroundColor Red
    exit 1
}

# Check Python
try {
    $pythonVersion = python --version
    Write-Host "     Python: $pythonVersion" -ForegroundColor Green
} catch {
    Write-Host "     ERROR: Python not found. Install Python 3.11+ from https://python.org" -ForegroundColor Red
    exit 1
}

# Check Node
try {
    $nodeVersion = node --version
    Write-Host "     Node: $nodeVersion" -ForegroundColor Green
} catch {
    Write-Host "     WARNING: Node not found. Dashboard won't work. Install from https://nodejs.org" -ForegroundColor Red
}

# Step 2 — Create virtualenv
Write-Host ""
Write-Host "[2/7] Creating Python virtual environment..." -ForegroundColor Yellow

if (Test-Path "$ProjectRoot\.venv") {
    Write-Host "     .venv already exists, skipping creation." -ForegroundColor DarkGray
} else {
    python -m venv "$ProjectRoot\.venv"
    Write-Host "     .venv created." -ForegroundColor Green
}

$Python = "$ProjectRoot\.venv\Scripts\python.exe"
$Pip = "$ProjectRoot\.venv\Scripts\pip.exe"
$Maturin = "$ProjectRoot\.venv\Scripts\maturin.exe"
$Pytest = "$ProjectRoot\.venv\Scripts\pytest.exe"

# Step 3 — Install maturin + Python deps
Write-Host ""
Write-Host "[3/7] Installing Python dependencies..." -ForegroundColor Yellow

& $Pip install maturin --quiet
Write-Host "     maturin installed." -ForegroundColor Green

& $Pip install -e ".[dev]" --quiet
Write-Host "     Python dependencies installed." -ForegroundColor Green

# Step 4 — Build Rust engine
if (-not $SkipRust) {
    Write-Host ""
    Write-Host "[4/7] Building Rust simulation engine..." -ForegroundColor Yellow
    Write-Host "     This may take 2-5 minutes on first build." -ForegroundColor DarkGray

    & $Maturin develop -m "$ProjectRoot\engine\Cargo.toml" --release

    if ($LASTEXITCODE -ne 0) {
        Write-Host ""
        Write-Host "     ERROR: Rust build failed." -ForegroundColor Red
        Write-Host "     Common fixes:" -ForegroundColor Yellow
        Write-Host "       1. Run this script as Administrator (for Defender exclusions)" -ForegroundColor Yellow
        Write-Host "       2. Check engine/Cargo.toml has [lib] name = 'incident_core'" -ForegroundColor Yellow
        Write-Host "       3. Kill any processes holding target/ files and retry" -ForegroundColor Yellow
        exit 1
    }

    Write-Host "     Rust engine built successfully." -ForegroundColor Green

    # Smoke test
    Write-Host "     Running smoke test..." -ForegroundColor DarkGray
    $smokeResult = & $Python -c @"
try:
    import incident_core
    g = incident_core.RustServiceGraph('bad_deploy', 1)
    obs = g.reset()
    assert len(obs) == 72, f'Expected 72, got {len(obs)}'
    obs2, reward, done = g.step(0)
    print(f'OK: obs={len(obs)}, reward={reward:.3f}')
except Exception as e:
    print(f'FAIL: {e}')
    exit(1)
"@
    Write-Host "     Smoke test: $smokeResult" -ForegroundColor Green
} else {
    Write-Host ""
    Write-Host "[4/7] Skipping Rust build (--SkipRust flag)" -ForegroundColor DarkGray
}

# Step 5 — Dashboard deps
if (-not $SkipDashboard) {
    Write-Host ""
    Write-Host "[5/7] Installing dashboard dependencies..." -ForegroundColor Yellow

    if (Test-Path "$ProjectRoot\dashboard\package.json") {
        Push-Location "$ProjectRoot\dashboard"
        npm install --silent
        Pop-Location
        Write-Host "     Dashboard dependencies installed." -ForegroundColor Green
    } else {
        Write-Host "     WARNING: dashboard/package.json not found. Skipping." -ForegroundColor Red
    }
} else {
    Write-Host ""
    Write-Host "[5/7] Skipping dashboard deps (--SkipDashboard flag)" -ForegroundColor DarkGray
}

# Step 6 — Ollama check
if (-not $SkipOllama) {
    Write-Host ""
    Write-Host "[6/7] Checking Ollama and Llama 3 model..." -ForegroundColor Yellow

    try {
        $ollamaList = ollama list 2>&1
        if ($ollamaList -match "llama3:8b-instruct-q4_K_M") {
            Write-Host "     llama3:8b-instruct-q4_K_M already available." -ForegroundColor Green
        } else {
            Write-Host "     llama3:8b-instruct-q4_K_M not found. Pulling (this will take ~5GB + 10 min)..." -ForegroundColor Yellow
            ollama pull llama3:8b-instruct-q4_K_M
            Write-Host "     Llama 3 pulled successfully." -ForegroundColor Green
        }
    } catch {
        Write-Host "     WARNING: Ollama not running or not installed." -ForegroundColor Red
        Write-Host "     Install from https://ollama.com and run 'ollama pull llama3:8b-instruct-q4_K_M'" -ForegroundColor Yellow
    }
} else {
    Write-Host ""
    Write-Host "[6/7] Skipping Ollama check (--SkipOllama flag)" -ForegroundColor DarkGray
}

# Step 7 — Run tests
Write-Host ""
Write-Host "[7/7] Running test suite..." -ForegroundColor Yellow

if (Test-Path "$ProjectRoot\tests") {
    & $Pytest "$ProjectRoot\tests\" -v --tb=short 2>&1 | Tee-Object -Variable testOutput
    if ($LASTEXITCODE -eq 0) {
        Write-Host "     All tests passed." -ForegroundColor Green
    } else {
        Write-Host "     Some tests failed. Check output above." -ForegroundColor Red
    }
} else {
    Write-Host "     tests/ directory not found. Skipping." -ForegroundColor DarkGray
}

# Done
Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Bootstrap Complete!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "To start the full demo:" -ForegroundColor White
Write-Host "  Terminal 1 (API):       .\.venv\Scripts\uvicorn.exe api.main:app --reload --port 8000" -ForegroundColor Gray
Write-Host "  Terminal 2 (Dashboard): cd dashboard && npm run dev" -ForegroundColor Gray
Write-Host "  Terminal 3 (Training):  .\.venv\Scripts\python.exe training\train.py" -ForegroundColor Gray
Write-Host "  Terminal 4 (TBoard):    .\.venv\Scripts\tensorboard.exe --logdir logs\" -ForegroundColor Gray
Write-Host ""
Write-Host "Good luck at the hackathon!" -ForegroundColor Cyan
