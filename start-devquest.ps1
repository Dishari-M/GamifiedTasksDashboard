$ErrorActionPreference = "Stop"

$root = $PSScriptRoot
$backendDir = Join-Path $root "backend"
$frontendDir = Join-Path $root "frontend"
$venvPython = Join-Path $backendDir ".venv\Scripts\python.exe"
$backendOut = Join-Path $backendDir "uvicorn.out.log"
$backendErr = Join-Path $backendDir "uvicorn.err.log"
$frontendOut = Join-Path $frontendDir "static-server.out.log"
$frontendErr = Join-Path $frontendDir "static-server.err.log"
$runDir = Join-Path $root ".devquest"
$backendPidFile = Join-Path $runDir "backend.pid"
$frontendPidFile = Join-Path $runDir "frontend.pid"
$oracleWalletDir = Join-Path $env:USERPROFILE ".oracle\wallet_tasksdb"
$oracleClientCandidates = @(
    "C:\oracle\instantclient_23_0",
    (Join-Path $env:USERPROFILE "Downloads\instantclient-basic-windows.x64-23.26.1.0.0\instantclient_23_0")
)
$oracleClientDir = $oracleClientCandidates |
    Where-Object { Test-Path (Join-Path $_ "oci.dll") } |
    Select-Object -First 1
$dbUser = "DEVQUEST_APP"
$dbPassword = "Teamaurora2026"
$dbWalletPassword = "TeamAurora2026"
$dbAlias = "tasksdb_tp"

function Stop-PortProcess {
    param([int]$Port)

    $processIds = netstat -ano -p tcp |
        ForEach-Object {
            if ($_ -match '^\s*TCP\s+(\S+)\s+\S+\s+LISTENING\s+(\d+)\s*$') {
                $localAddress = $Matches[1]
                $processId = [int]$Matches[2]
                if ($localAddress -match "[:.]$Port$") {
                    $processId
                }
            }
        } |
        Sort-Object -Unique

    foreach ($processId in $processIds) {
        try {
            if ($processId -and $processId -ne 0) {
                Write-Host "Stopping process $processId on port $Port ..." -ForegroundColor DarkYellow
                Stop-Process -Id $processId -Force -ErrorAction Stop
            }
        } catch {
        }
    }
}

function Stop-PidFileProcess {
    param([string]$PidFile)

    if (-not (Test-Path $PidFile)) {
        return
    }

    try {
        $processId = [int](Get-Content -Path $PidFile -Raw)
        $process = Get-Process -Id $processId -ErrorAction SilentlyContinue
        if ($process) {
            Write-Host "Stopping previous DevQuest process $processId ..." -ForegroundColor DarkYellow
            Stop-Process -Id $processId -Force -ErrorAction Stop
        }
    } catch {
    } finally {
        Remove-Item -LiteralPath $PidFile -Force -ErrorAction SilentlyContinue
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
    $env:DB_POOL_SIZE = "10"
    $env:DB_POOL_MIN = "1"
    $env:DB_POOL_MAX = "10"
    $env:DB_POOL_INCREMENT = "1"
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

New-Item -ItemType Directory -Path $runDir -Force | Out-Null

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

Stop-PidFileProcess -PidFile $backendPidFile
Stop-PidFileProcess -PidFile $frontendPidFile
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
`$env:DB_POOL_SIZE='10'
`$env:DB_POOL_MIN='1'
`$env:DB_POOL_MAX='10'
`$env:DB_POOL_INCREMENT='1'
Set-Location '$backendDir'
.\.venv\Scripts\python.exe -m uvicorn main:app --host 127.0.0.1 --port 8000
"@
$backendProcess = Start-Process -FilePath "powershell" `
    -ArgumentList "-NoProfile", "-Command", $backendCommand `
    -WorkingDirectory $backendDir `
    -RedirectStandardOutput $backendOut `
    -RedirectStandardError $backendErr `
    -WindowStyle Hidden `
    -PassThru
Set-Content -Path $backendPidFile -Value $backendProcess.Id

if (-not (Wait-ForHttp -Url "http://127.0.0.1:8000/" -TimeoutSeconds 60)) {
    throw "Backend did not become ready. Check $backendErr"
}

if (-not (Wait-ForHttp -Url "http://127.0.0.1:8000/api/v1/tasks" -TimeoutSeconds 60)) {
    throw "Backend root is up, but the Oracle-backed task API did not become ready. Check $backendErr"
}

Write-Host "Starting frontend on http://127.0.0.1:3000 ..." -ForegroundColor Green
$frontendProcess = Start-Process -FilePath "node" `
    -ArgumentList "local-static-server.js" `
    -WorkingDirectory $frontendDir `
    -RedirectStandardOutput $frontendOut `
    -RedirectStandardError $frontendErr `
    -WindowStyle Hidden `
    -PassThru
Set-Content -Path $frontendPidFile -Value $frontendProcess.Id

if (-not (Wait-ForHttp -Url "http://127.0.0.1:3000/" -TimeoutSeconds 60)) {
    throw "Frontend did not become ready. Check $frontendErr"
}

Write-Host ""
Write-Host "DevQuest is up." -ForegroundColor Green
Write-Host "Frontend: http://127.0.0.1:3000"
Write-Host "Backend:  http://127.0.0.1:8000"
Write-Host "API Docs: http://127.0.0.1:8000/docs"
Write-Host "DB Mode:  oracle (tasksdb_tp via thick mode)"
Write-Host "Stop:     .\stop-devquest.cmd"

try {
    Start-Process "http://127.0.0.1:3000"
} catch {
    Write-Host "Browser auto-open skipped: $($_.Exception.Message)" -ForegroundColor DarkYellow
}
