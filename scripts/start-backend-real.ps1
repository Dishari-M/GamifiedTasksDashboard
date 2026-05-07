param(
    [string]$HostAddress = "127.0.0.1",
    [int]$Port = 8000,
    [switch]$Restart,
    [switch]$NoVerify
)

$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent $PSScriptRoot
$BackendDir = Join-Path $RepoRoot "backend"
$PythonExe = Join-Path $BackendDir ".venv\Scripts\python.exe"
$BackendEnvFile = Join-Path $BackendDir ".env.real.local"
$DownloadedEnvFile = Join-Path $RepoRoot "env.real.download"
$EnvFile = if (Test-Path -LiteralPath $BackendEnvFile) { $BackendEnvFile } else { $DownloadedEnvFile }
$OutLog = Join-Path $BackendDir "uvicorn-8000-real.out.log"
$ErrLog = Join-Path $BackendDir "uvicorn-8000-real.err.log"
$OracleClientDir = "C:\oracle\instantclient_23_0"

function Import-EnvFile {
    param([string]$Path)

    if (-not (Test-Path -LiteralPath $Path)) {
        throw "Missing env file: $Path"
    }

    Get-Content -LiteralPath $Path | ForEach-Object {
        $line = $_.Trim()
        if (-not $line -or $line.StartsWith("#")) {
            return
        }

        $equals = $line.IndexOf("=")
        if ($equals -lt 1) {
            return
        }

        $name = $line.Substring(0, $equals).Trim()
        $value = $line.Substring($equals + 1).Trim()
        if (($value.StartsWith('"') -and $value.EndsWith('"')) -or ($value.StartsWith("'") -and $value.EndsWith("'"))) {
            $value = $value.Substring(1, $value.Length - 2)
        }

        [Environment]::SetEnvironmentVariable($name, $value, "Process")
    }
}

function Get-ListenerPid {
    param([int]$LocalPort)

    $line = netstat -ano -p tcp |
        Select-String -Pattern "^\s*TCP\s+\S+:$LocalPort\s+\S+\s+LISTENING\s+(\d+)" |
        Select-Object -First 1

    if ($line -and $line.Matches[0].Groups.Count -gt 1) {
        return [int]$line.Matches[0].Groups[1].Value
    }

    return $null
}

function Test-Backend {
    param([string]$BaseUrl)

    try {
        $response = Invoke-WebRequest -Uri $BaseUrl -UseBasicParsing -TimeoutSec 5
        return $response.StatusCode -eq 200
    }
    catch {
        return $false
    }
}

if (-not (Test-Path -LiteralPath $PythonExe)) {
    throw "Missing backend venv Python: $PythonExe"
}

Import-EnvFile -Path $EnvFile

if (-not [Environment]::GetEnvironmentVariable("ORACLE_DB_THICK_MODE", "Process")) {
    [Environment]::SetEnvironmentVariable("ORACLE_DB_THICK_MODE", "1", "Process")
}
if (-not [Environment]::GetEnvironmentVariable("ORACLE_CLIENT_LIB_DIR", "Process")) {
    [Environment]::SetEnvironmentVariable("ORACLE_CLIENT_LIB_DIR", $OracleClientDir, "Process")
}
if (-not [Environment]::GetEnvironmentVariable("TNS_ADMIN", "Process")) {
    [Environment]::SetEnvironmentVariable("TNS_ADMIN", [Environment]::GetEnvironmentVariable("DB_WALLET_DIR", "Process"), "Process")
}
if (-not [Environment]::GetEnvironmentVariable("DB_POOL_MIN", "Process")) {
    [Environment]::SetEnvironmentVariable("DB_POOL_MIN", "1", "Process")
}
if (-not [Environment]::GetEnvironmentVariable("DB_POOL_MAX", "Process")) {
    [Environment]::SetEnvironmentVariable("DB_POOL_MAX", "10", "Process")
}
if (-not [Environment]::GetEnvironmentVariable("DB_POOL_INCREMENT", "Process")) {
    [Environment]::SetEnvironmentVariable("DB_POOL_INCREMENT", "1", "Process")
}

$RequiredEnv = @(
    "DB_USER",
    "DB_PASSWORD",
    "DB_DSN",
    "DB_WALLET_DIR",
    "DB_WALLET_PASSWORD",
    "DEVQUEST_DATA_MODE",
    "DEVQUEST_AI_MODE",
    "DEVQUEST_AI_PROVIDER",
    "OCI_AUTH_TYPE",
    "OCI_CONFIG_FILE",
    "OCI_CONFIG_PROFILE",
    "OCI_REGION",
    "OCI_COMPARTMENT_ID",
    "OCI_GENAI_ENDPOINT",
    "OCI_GENAI_SERVING_MODE",
    "OCI_GENAI_REQUEST_FORMAT",
    "OCI_GENAI_MODEL_ID",
    "ORACLE_DB_THICK_MODE",
    "ORACLE_CLIENT_LIB_DIR",
    "TNS_ADMIN",
    "DB_POOL_MIN",
    "DB_POOL_MAX",
    "DB_POOL_INCREMENT"
)

$missing = $RequiredEnv | Where-Object { -not [Environment]::GetEnvironmentVariable($_, "Process") }
if ($missing) {
    throw "Missing required environment variables in ${EnvFile}: $($missing -join ', ')"
}

$DefaultEnv = [ordered]@{
    "DB_POOL_SIZE" = "10"
    "DB_POOL_MIN" = "2"
    "DB_POOL_MAX" = "10"
    "DB_POOL_INCREMENT" = "1"
    "OCI_GENAI_CONNECT_TIMEOUT_SECONDS" = "5"
    "OCI_GENAI_READ_TIMEOUT_SECONDS" = "20"
}

foreach ($entry in $DefaultEnv.GetEnumerator()) {
    if (-not [Environment]::GetEnvironmentVariable($entry.Key, "Process")) {
        [Environment]::SetEnvironmentVariable($entry.Key, $entry.Value, "Process")
    }
}

$existingPid = Get-ListenerPid -LocalPort $Port
if ($existingPid) {
    if ($Restart) {
        Stop-Process -Id $existingPid -Force
        Start-Sleep -Seconds 1
    }
    else {
        $url = "http://${HostAddress}:$Port"
        if (Test-Backend -BaseUrl $url) {
            Write-Host "Backend already running at $url (PID $existingPid)."
            exit 0
        }
        throw "Port $Port is already in use by PID $existingPid. Re-run with -Restart to stop it first."
    }
}

$Runner = Join-Path $env:TEMP "devquest-backend-real-$Port.cmd"
$BatchLines = @(
    "@echo off",
    "cd /d `"$BackendDir`"",
    "set `"DB_USER=$env:DB_USER`"",
    "set `"DB_PASSWORD=$env:DB_PASSWORD`"",
    "set `"DB_DSN=$env:DB_DSN`"",
    "set `"DB_WALLET_DIR=$env:DB_WALLET_DIR`"",
    "set `"DB_WALLET_PASSWORD=$env:DB_WALLET_PASSWORD`"",
    "set `"DB_POOL_SIZE=$env:DB_POOL_SIZE`"",
    "set `"DB_POOL_MIN=$env:DB_POOL_MIN`"",
    "set `"DB_POOL_MAX=$env:DB_POOL_MAX`"",
    "set `"DB_POOL_INCREMENT=$env:DB_POOL_INCREMENT`"",
    "set `"DEVQUEST_DATA_MODE=$env:DEVQUEST_DATA_MODE`"",
    "set `"DEVQUEST_AI_MODE=$env:DEVQUEST_AI_MODE`"",
    "set `"DEVQUEST_AI_PROVIDER=$env:DEVQUEST_AI_PROVIDER`"",
    "set `"OCI_AUTH_TYPE=$env:OCI_AUTH_TYPE`"",
    "set `"OCI_CONFIG_FILE=$env:OCI_CONFIG_FILE`"",
    "set `"OCI_CONFIG_PROFILE=$env:OCI_CONFIG_PROFILE`"",
    "set `"OCI_REGION=$env:OCI_REGION`"",
    "set `"OCI_COMPARTMENT_ID=$env:OCI_COMPARTMENT_ID`"",
    "set `"OCI_GENAI_ENDPOINT=$env:OCI_GENAI_ENDPOINT`"",
    "set `"OCI_GENAI_SERVING_MODE=$env:OCI_GENAI_SERVING_MODE`"",
    "set `"OCI_GENAI_REQUEST_FORMAT=$env:OCI_GENAI_REQUEST_FORMAT`"",
    "set `"OCI_GENAI_MODEL_ID=$env:OCI_GENAI_MODEL_ID`"",
    "set `"OCI_GENAI_CONNECT_TIMEOUT_SECONDS=$env:OCI_GENAI_CONNECT_TIMEOUT_SECONDS`"",
    "set `"OCI_GENAI_READ_TIMEOUT_SECONDS=$env:OCI_GENAI_READ_TIMEOUT_SECONDS`"",
    "`"$PythonExe`" -m uvicorn main:app --host $HostAddress --port $Port > `"$OutLog`" 2> `"$ErrLog`""
)
Set-Content -LiteralPath $Runner -Value $BatchLines -Encoding ASCII

$shell = New-Object -ComObject WScript.Shell
[void]$shell.Run("cmd.exe /c `"$Runner`"", 0, $false)
Write-Host "Started backend launcher."

if (-not $NoVerify) {
    $url = "http://${HostAddress}:$Port"
    $started = $false
    for ($attempt = 1; $attempt -le 20; $attempt++) {
        Start-Sleep -Seconds 1
        if (Test-Backend -BaseUrl $url) {
            $started = $true
            break
        }
    }

    if (-not $started) {
        Write-Host "Backend did not respond at $url within 20 seconds."
        Write-Host "Error log: $ErrLog"
        Get-Content -Tail 80 -LiteralPath $ErrLog -ErrorAction SilentlyContinue
        exit 1
    }
}

$backendPid = Get-ListenerPid -LocalPort $Port
Write-Host "Backend running at http://${HostAddress}:$Port (PID $backendPid)."
Write-Host "Logs:"
Write-Host "  $OutLog"
Write-Host "  $ErrLog"
