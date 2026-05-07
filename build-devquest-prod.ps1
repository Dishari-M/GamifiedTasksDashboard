$ErrorActionPreference = "Stop"

$root = $PSScriptRoot
$frontendDir = Join-Path $root "frontend"
$packageJson = Join-Path $frontendDir "package.json"
$packageLock = Join-Path $frontendDir "package-lock.json"
$nodeModules = Join-Path $frontendDir "node_modules"
$reactScripts = Join-Path $nodeModules "react-scripts\bin\react-scripts.js"
$buildIndex = Join-Path $frontendDir "build\index.html"

function Require-Path {
    param(
        [string]$Path,
        [string]$Message
    )

    if (-not (Test-Path $Path)) {
        throw $Message
    }
}

Write-Host "Building DevQuest production frontend from $root" -ForegroundColor Cyan

Require-Path $frontendDir "Frontend folder not found: $frontendDir"
Require-Path $packageJson "Frontend package.json not found: $packageJson"

$rootNodeModules = Join-Path $root "node_modules"
if (-not (Test-Path $nodeModules) -and (Test-Path $rootNodeModules)) {
    Write-Host "Moving repo-root node_modules into frontend..." -ForegroundColor Yellow
    Move-Item -LiteralPath $rootNodeModules -Destination $nodeModules
}

if (-not (Test-Path $reactScripts)) {
    Write-Host "Installing frontend dependencies..." -ForegroundColor Yellow
    Push-Location $frontendDir
    try {
        if (Test-Path $packageLock) {
            npm ci
        } else {
            npm install
        }
    } finally {
        Pop-Location
    }
}

Write-Host "Running npm run build..." -ForegroundColor Green
Push-Location $frontendDir
try {
    npm run build
} finally {
    Pop-Location
}

Require-Path $buildIndex "Production build did not create $buildIndex"

Write-Host ""
Write-Host "DevQuest production build is ready." -ForegroundColor Green
Write-Host "Build folder: $((Join-Path $frontendDir 'build'))"
Write-Host "To serve locally, run start-devquest.cmd or start node frontend/local-static-server.js after the backend is up."
