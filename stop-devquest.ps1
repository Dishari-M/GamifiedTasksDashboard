$ErrorActionPreference = "Stop"

$root = $PSScriptRoot
$runDir = Join-Path $root ".devquest"
$backendPidFile = Join-Path $runDir "backend.pid"
$frontendPidFile = Join-Path $runDir "frontend.pid"

function Stop-PidFileProcess {
    param([string]$PidFile)

    if (-not (Test-Path $PidFile)) {
        return
    }

    try {
        $processId = [int](Get-Content -Path $PidFile -Raw)
        $process = Get-Process -Id $processId -ErrorAction SilentlyContinue
        if ($process) {
            Write-Host "Stopping Gamified Tasks Dashboard process $processId ..." -ForegroundColor DarkYellow
            Stop-Process -Id $processId -Force -ErrorAction Stop
        }
    } catch {
    } finally {
        Remove-Item -LiteralPath $PidFile -Force -ErrorAction SilentlyContinue
    }
}

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

Stop-PidFileProcess -PidFile $backendPidFile
Stop-PidFileProcess -PidFile $frontendPidFile
Stop-PortProcess -Port 8000
Stop-PortProcess -Port 3000

Write-Host "Gamified Tasks Dashboard backend and frontend servers are stopped." -ForegroundColor Green
