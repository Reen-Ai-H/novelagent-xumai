[CmdletBinding()]
param(
    [int]$Port = 8000,
    [switch]$OpenBrowser
)

$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$python = Join-Path $projectRoot ".venv\Scripts\python.exe"

if (-not (Test-Path -LiteralPath $python)) {
    throw "Python virtual environment not found. Run: py -3 -m venv .venv"
}

$url = "http://127.0.0.1:$Port"
if ($OpenBrowser) {
    Start-Process $url
}

Push-Location $projectRoot
try {
    & $python -m uvicorn main:app --host 127.0.0.1 --port $Port
}
finally {
    Pop-Location
}
