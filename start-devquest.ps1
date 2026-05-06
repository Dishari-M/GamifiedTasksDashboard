$ErrorActionPreference = "Stop"

$root = $PSScriptRoot
$backendDir = Join-Path $root "backend"
$frontendDir = Join-Path $root "frontend"
$venvPython = Join-Path $backendDir ".venv\Scripts\python.exe"
$backendOut = Join-Path $backendDir "uvicorn.out.log"
$backendErr = Join-Path $backendDir "uvicorn.err.log"
$frontendOut = Join-Path $frontendDir "static-server.out.log"
$frontendErr = Join-Path $frontendDir "static-server.err.log"
$oracleWalletDir = Join-Path $env:USERPROFILE ".oracle\wallet_tasksdb"
$oracleClientDir = "C:\oracle\instantclient_23_0"
$dbUser = "DEVQUEST_APP"
$dbPassword = "Teamaurora2026"
$dbWalletPassword = "TeamAurora2026"
$dbAlias = "tasksdb_tp"

function Stop-PortProcess {
    param([int]$Port)

    $connections = Get-NetTCPConnection -State Listen -LocalPort $Port -ErrorAction SilentlyContinue
    foreach ($connection in $connections) {
        try {
            Stop-Process -Id $connection.OwningProcess -Force -ErrorAction Stop
        } catch {
        }
    }
}

function Wait-ForHttp {
    param(
        [string]$Url,
        [int]$TimeoutSeconds = 60,
        [hashtable]$Headers = @{}
    )

    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    while ((Get-Date) -lt $deadline) {
        try {
            $response = Invoke-WebRequest -Uri $Url -Headers $Headers -UseBasicParsing -TimeoutSec 5
            if ($response.StatusCode -ge 200 -and $response.StatusCode -lt 500) {
                return $true
            }
        } catch {
            if ($_.Exception.Response) {
                $statusCode = [int]$_.Exception.Response.StatusCode
                if ($statusCode -ge 200 -and $statusCode -lt 500) {
                    return $true
                }
            }
        }
        Start-Sleep -Seconds 2
    }

    return $false
}

function Require-Path {
    param(
        [string]$Path,
        [string]$Message
    )

    if (-not (Test-Path $Path)) {
        throw $Message
    }
}

function Set-OracleEnvironment {
    $env:DEVQUEST_DATA_MODE = "oracle"
    $env:DEVQUEST_AI_MODE = "real"
    $env:DB_USER = $dbUser
    $env:DB_PASSWORD = $dbPassword
    $env:DB_DSN = $dbAlias
    $env:DB_WALLET_DIR = $oracleWalletDir
    $env:DB_WALLET_PASSWORD = $dbWalletPassword
    $env:TNS_ADMIN = $oracleWalletDir
    $env:ORACLE_DB_THICK_MODE = "1"
    $env:ORACLE_CLIENT_LIB_DIR = $oracleClientDir
}

Write-Host "Starting DevQuest from $root" -ForegroundColor Cyan

if (-not (Test-Path $backendDir)) {
    throw "Backend folder not found: $backendDir"
}

if (-not (Test-Path $frontendDir)) {
    throw "Frontend folder not found: $frontendDir"
}

if (-not (Test-Path $venvPython)) {
    Write-Host "Creating backend virtual environment..." -ForegroundColor Yellow
    Push-Location $backendDir
    try {
        py -3 -m venv .venv
        & .\.venv\Scripts\python.exe -m pip install --upgrade pip
        & .\.venv\Scripts\python.exe -m pip install -r requirements.txt
    } finally {
        Pop-Location
    }
}

Require-Path $oracleWalletDir "Oracle wallet folder not found: $oracleWalletDir"
Require-Path (Join-Path $oracleWalletDir "tnsnames.ora") "Oracle wallet is missing tnsnames.ora at $oracleWalletDir"
Require-Path (Join-Path $oracleWalletDir "sqlnet.ora") "Oracle wallet is missing sqlnet.ora at $oracleWalletDir"
Require-Path (Join-Path $oracleWalletDir "ewallet.pem") "Oracle wallet is missing ewallet.pem at $oracleWalletDir"
Require-Path $oracleClientDir "Oracle Instant Client folder not found: $oracleClientDir"
Require-Path (Join-Path $oracleClientDir "oci.dll") "Oracle Instant Client is missing oci.dll at $oracleClientDir"

Set-OracleEnvironment

$frontendNodeModules = Join-Path $frontendDir "node_modules"
$rootNodeModules = Join-Path $root "node_modules"
if (-not (Test-Path $frontendNodeModules) -and (Test-Path $rootNodeModules)) {
    Write-Host "Moving repo-root node_modules into frontend..." -ForegroundColor Yellow
    Move-Item -LiteralPath $rootNodeModules -Destination $frontendNodeModules
}

$reactScripts = Join-Path $frontendNodeModules "react-scripts\bin\react-scripts.js"
if (-not (Test-Path $reactScripts)) {
    throw "Missing frontend dependency: $reactScripts"
}

$buildIndex = Join-Path $frontendDir "build\index.html"
$sourcePaths = @(
    (Join-Path $frontendDir "src"),
    (Join-Path $frontendDir "public"),
    (Join-Path $frontendDir "package.json")
)

$needsBuild = -not (Test-Path $buildIndex)
if (-not $needsBuild) {
    $buildTime = (Get-Item $buildIndex).LastWriteTimeUtc
    foreach ($path in $sourcePaths) {
        if (Test-Path $path) {
            try {
                $latest = Get-ChildItem $path -Recurse -File -ErrorAction Stop |
                    Sort-Object LastWriteTimeUtc -Descending |
                    Select-Object -First 1
            } catch {
                $needsBuild = $true
                break
            }
            if ($latest -and $latest.LastWriteTimeUtc -gt $buildTime) {
                $needsBuild = $true
                break
            }
        }
    }
}

if ($needsBuild) {
    Write-Host "Building frontend..." -ForegroundColor Yellow
    Push-Location $frontendDir
    try {
        npm run build
    } finally {
        Pop-Location
    }
}

Stop-PortProcess -Port 8000
Stop-PortProcess -Port 3000

Write-Host "Starting backend on http://127.0.0.1:8000 ..." -ForegroundColor Green
$backendCommand = @"
`$env:DEVQUEST_DATA_MODE='oracle'
`$env:DEVQUEST_AI_MODE='real'
`$env:DB_USER='$dbUser'
`$env:DB_PASSWORD='$dbPassword'
`$env:DB_DSN='$dbAlias'
`$env:DB_WALLET_DIR='$oracleWalletDir'
`$env:DB_WALLET_PASSWORD='$dbWalletPassword'
`$env:TNS_ADMIN='$oracleWalletDir'
`$env:ORACLE_DB_THICK_MODE='1'
`$env:ORACLE_CLIENT_LIB_DIR='$oracleClientDir'
Set-Location '$backendDir'
.\.venv\Scripts\python.exe -m uvicorn main:app --host 127.0.0.1 --port 8000
"@
Start-Process -FilePath "powershell" `
    -ArgumentList "-NoProfile", "-Command", $backendCommand `
    -WorkingDirectory $backendDir `
    -RedirectStandardOutput $backendOut `
    -RedirectStandardError $backendErr | Out-Null

if (-not (Wait-ForHttp -Url "http://127.0.0.1:8000/" -TimeoutSeconds 60)) {
    throw "Backend did not become ready. Check $backendErr"
}

if (-not (Wait-ForHttp -Url "http://127.0.0.1:8000/api/v1/tasks" -TimeoutSeconds 60)) {
    throw "Backend root is up, but the Oracle-backed task API did not become ready. Check $backendErr"
}

Write-Host "Starting frontend on http://127.0.0.1:3000 ..." -ForegroundColor Green
Start-Process -FilePath "node" `
    -ArgumentList "local-static-server.js" `
    -WorkingDirectory $frontendDir `
    -RedirectStandardOutput $frontendOut `
    -RedirectStandardError $frontendErr | Out-Null

if (-not (Wait-ForHttp -Url "http://127.0.0.1:3000/" -TimeoutSeconds 60)) {
    throw "Frontend did not become ready. Check $frontendErr"
}

Write-Host ""
Write-Host "DevQuest is up." -ForegroundColor Green
Write-Host "Frontend: http://127.0.0.1:3000"
Write-Host "Backend:  http://127.0.0.1:8000"
Write-Host "API Docs: http://127.0.0.1:8000/docs"
Write-Host "DB Mode:  oracle (tasksdb_tp via thick mode)"

Start-Process "http://127.0.0.1:3000"
