# Start voting-api + listener when Docker Desktop is ready (Windows).
# Use with: Task Scheduler "At log on" or Startup folder.
#
# 1. Edit $ComposeDir if your repo path is different.
# 2. Ensure Docker Desktop starts with Windows (Docker Desktop Settings).
# 3. Register this script (see README "Tự chạy khi bật Docker Desktop").

$ErrorActionPreference = "Stop"

# <<< CHANGE THIS to your voting-api folder on Windows >>>
$ComposeDir = "C:\path\to\voting-api"

$LogDir = Join-Path $env:USERPROFILE "Documents"
$LogFile = Join-Path $LogDir "voting-api-docker-start.log"

function Write-Log([string]$Message) {
    $line = "{0} {1}" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss"), $Message
    Add-Content -Path $LogFile -Value $line
    Write-Host $line
}

if (-not (Test-Path $ComposeDir)) {
    Write-Log "ERROR: Compose dir not found: $ComposeDir"
    exit 1
}

Set-Location $ComposeDir
Write-Log "Waiting for Docker engine..."

$deadline = (Get-Date).AddMinutes(5)
$ready = $false
while ((Get-Date) -lt $deadline) {
    try {
        docker info 2>$null | Out-Null
        if ($LASTEXITCODE -eq 0) {
            $ready = $true
            break
        }
    } catch {
        # ignore until Docker is up
    }
    Start-Sleep -Seconds 5
}

if (-not $ready) {
    Write-Log "ERROR: Docker engine not ready within 5 minutes"
    exit 1
}

Write-Log "Docker ready. Starting compose stack..."
docker compose up -d
if ($LASTEXITCODE -ne 0) {
    Write-Log "ERROR: docker compose up failed with exit $LASTEXITCODE"
    exit $LASTEXITCODE
}

Write-Log "OK: voting-api stack started"
docker compose ps | Out-String | ForEach-Object { Write-Log $_ }
