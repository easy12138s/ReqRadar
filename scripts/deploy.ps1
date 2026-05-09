<#
.SYNOPSIS
    ReqRadar one-click deployment script (Windows / cross-platform PowerShell)

.DESCRIPTION
    This script automates:
      1. Environment checks (Python, Node.js, Poetry)
      2. Frontend build (npm ci + npm run build)
      3. Backend dependency installation (poetry install)
      4. Configuration initialization (.env + .reqradar.yaml)
      5. Database migration (alembic upgrade head)
      6. Create admin superuser (optional)
      7. Start the web server

.PARAMETER SkipFrontend
    Skip frontend build step (use if already built)

.PARAMETER SkipMigrate
    Skip database migration step

.PARAMETER SkipSuperuser
    Skip superuser creation prompt

.PARAMETER Port
    Override the default port (default: 8000)

.PARAMETER Host
    Override the default host (default: 0.0.0.0)

.PARAMETER Dev
    Run in development mode (with --reload)

.EXAMPLE
    .\scripts\deploy.ps1
    .\scripts\deploy.ps1 -Port 9000 -Dev
    .\scripts\deploy.ps1 -SkipFrontend
#>

param(
    [switch]$SkipFrontend = $false,
    [switch]$SkipMigrate = $false,
    [switch]$SkipSuperuser = $false,
    [int]$Port = 0,
    [string]$Host_ = "",
    [switch]$Dev = $false
)

$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"

$ProjectRoot = Resolve-Path (Join-Path $PSScriptRoot "..")

function Write-Step($msg) {
    Write-Host "`n==> $msg" -ForegroundColor Cyan
}

function Write-Ok($msg) {
    Write-Host "    OK: $msg" -ForegroundColor Green
}

function Write-Warn($msg) {
    Write-Host "    WARNING: $msg" -ForegroundColor Yellow
}

function Write-Err($msg) {
    Write-Host "    ERROR: $msg" -ForegroundColor Red
}

# ── Step 1: Environment checks ───────────────────────────────────────────

Write-Step "Checking environment..."

$pyCmd = $null
foreach ($cmd in @("python", "python3", "py")) {
    try {
        $ver = & $cmd --version 2>&1
        if ($ver -match "3\.(\d+)") {
            $minor = [int]$matches[1]
            if ($minor -ge 12) {
                $pyCmd = $cmd
                Write-Ok "Python: $ver"
                break
            }
        }
    } catch { }
}
if (-not $pyCmd) {
    Write-Err "Python 3.12+ is required. Install from https://python.org"
    exit 1
}

$nodeOk = $false
try {
    $nodeVer = & node --version 2>&1
    if ($nodeVer -match "v(\d+)\.") {
        if ([int]$matches[1] -ge 18) {
            $nodeOk = $true
            Write-Ok "Node.js: $nodeVer"
        }
    }
} catch { }
if (-not $nodeOk -and -not $SkipFrontend) {
    Write-Warn "Node.js 18+ not found. Frontend build will be skipped."
    Write-Warn "Install Node.js from https://nodejs.org or use -SkipFrontend"
    $SkipFrontend = $true
}

try {
    $poetryVer = & poetry --version 2>&1
    Write-Ok "Poetry: $poetryVer"
} catch {
    Write-Err "Poetry is not installed. Install from https://python-poetry.org"
    Write-Host "    Run: pip install poetry  or  (Invoke-WebRequest -Uri https://install.python-poetry.org -UseBasicParsing).Content | python"
    exit 1
}

# ── Step 2: Frontend build ───────────────────────────────────────────────

if (-not $SkipFrontend) {
    Write-Step "Building frontend..."
    Push-Location (Join-Path $ProjectRoot "frontend")
    try {
        & npm ci --prefer-offline 2>&1 | Write-Host
        & npm run build 2>&1 | Write-Host

        $indexFile = Join-Path $ProjectRoot "src\reqradar\web\static\index.html"
        if (Test-Path $indexFile) {
            Write-Ok "Frontend build succeeded"
        } else {
            Write-Err "Frontend build failed - index.html not found"
            exit 1
        }
    } finally {
        Pop-Location
    }
} else {
    Write-Step "Skipping frontend build"
}

# ── Step 3: Backend dependency installation ──────────────────────────────

Write-Step "Installing Python dependencies..."
Push-Location $ProjectRoot
try {
    & poetry install --no-interaction 2>&1 | Write-Host
    Write-Ok "Dependencies installed"
} finally {
    Pop-Location
}

# ── Step 4: Configuration initialization ──────────────────────────────────

Write-Step "Checking configuration..."

$envFile = Join-Path $ProjectRoot ".env"
$ymlFile = Join-Path $ProjectRoot ".reqradar.yaml"
$exampleYml = Join-Path $ProjectRoot ".reqradar.yaml.example"

if (-not (Test-Path $ymlFile) -and (Test-Path $exampleYml)) {
    Copy-Item $exampleYml $ymlFile
    Write-Ok "Created .reqradar.yaml from example"
} elseif (Test-Path $ymlFile) {
    Write-Ok ".reqradar.yaml already exists"
} else {
    Write-Warn "No .reqradar.yaml found. Defaults will be used."
}

if (-not (Test-Path $envFile)) {
    $needKey = $true
    $apiKey = ""
    $secretKey = ""

    if (Test-Path $ymlFile) {
        $ymlContent = Get-Content $ymlFile -Raw
        if ($ymlContent -match "api_key:\s*\S+" -and $ymlContent -notmatch "api_key:\s*\$\{") {
            $needKey = $false
        }
    }

    if ($needKey) {
        Write-Host ""
        Write-Host "ReqRadar requires an LLM API key to function." -ForegroundColor Yellow
        $apiKey = Read-Host "    Enter OPENAI_API_KEY (or compatible API key)"
        $secretKey = -join ((48..57) + (65..90) + (97..122) | Get-Random -Count 32 | ForEach-Object { [char]$_ })
    }

    $envContent = @(
        "# ReqRadar Environment Configuration",
        "# Generated by deploy script - edit as needed",
        ""
    )
    if ($apiKey) { $envContent += "OPENAI_API_KEY=$apiKey" }
    if ($secretKey) { $envContent += "REQRADAR_SECRET_KEY=$secretKey" }
    if ($apiKey -or $secretKey) {
        $envContent | Set-Content $envFile -Encoding UTF8
        Write-Ok "Created .env with API key and secret key"
    }
} else {
    Write-Ok ".env already exists"
}

# ── Step 5: Database migration ────────────────────────────────────────────

if (-not $SkipMigrate) {
    Write-Step "Running database migrations..."
    Push-Location $ProjectRoot
    try {
        & poetry run alembic upgrade head 2>&1 | Write-Host
        if ($LASTEXITCODE -eq 0) {
            Write-Ok "Database migrations applied"
        } else {
            Write-Warn "Migration failed. Tables will be auto-created if needed."
        }
    } finally {
        Pop-Location
    }
} else {
    Write-Step "Skipping database migrations"
}

# ── Step 6: Create superuser (optional) ──────────────────────────────────

if (-not $SkipSuperuser) {
    Write-Step "Superuser account"
    Write-Host "    A default admin account will be created automatically on first start:" -ForegroundColor Yellow
    Write-Host "    Email: admin@reqradar.io  |  Password: Admin12138%" -ForegroundColor Yellow
    Write-Host "    You can also create a custom admin with: poetry run reqradar createsuperuser"
}

# ── Step 7: Start server ─────────────────────────────────────────────────

Write-Step "Starting ReqRadar server..."

$serveArgs = @("run", "reqradar", "serve")
if ($Port -gt 0) { $serveArgs += @("--port", $Port) }
if ($Host_) { $serveArgs += @("--host", $Host_) }
if ($Dev) { $serveArgs += "--reload" }

Write-Host ""
Write-Host "ReqRadar is ready!" -ForegroundColor Green
Write-Host "    Web UI: http://localhost:$($Port -gt 0 ? $Port : 8000)/app/" -ForegroundColor White
Write-Host "    API:    http://localhost:$($Port -gt 0 ? $Port : 8000)/health" -ForegroundColor White
Write-Host ""

& poetry $serveArgs