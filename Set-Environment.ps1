[CmdletBinding()]
param(
    [ValidateSet("openai", "dashscope")]
    [string]$Provider = "openai",
    [string]$BaseUrl = "",
    [string]$Model = "",
    [double]$Temperature = 0.7,
    [switch]$Clear
)

$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$envPath = Join-Path $projectRoot ".env"
$examplePath = Join-Path $projectRoot ".env.example"

if (-not (Test-Path -LiteralPath $envPath)) {
    Copy-Item -LiteralPath $examplePath -Destination $envPath
}

$apiKey = ""
if (-not $Clear) {
    $secureKey = Read-Host "Enter $Provider API key (input is hidden)" -AsSecureString
    $keyPtr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secureKey)
    try {
        $apiKey = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($keyPtr)
    }
    finally {
        [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($keyPtr)
    }
}

$values = [ordered]@{
    OPENAI_API_KEY = if ($Provider -eq "openai") { $apiKey } else { "" }
    DASHSCOPE_API_KEY = if ($Provider -eq "dashscope") { $apiKey } else { "" }
    OPENAI_BASE_URL = if ($Provider -eq "openai") { $BaseUrl } else { "" }
    DASHSCOPE_BASE_URL = if ($Provider -eq "dashscope") { $BaseUrl } else { "" }
    LLM_BASE_URL = $BaseUrl
    LLM_MODEL = $Model
    OPENAI_MODEL = if ($Provider -eq "openai") { $Model } else { "" }
    DASHSCOPE_MODEL = if ($Provider -eq "dashscope") { $Model } else { "" }
    LLM_TEMPERATURE = $Temperature.ToString([Globalization.CultureInfo]::InvariantCulture)
}

$lines = @(Get-Content -LiteralPath $envPath)
foreach ($name in $values.Keys) {
    $replacement = "{0}={1}" -f $name, [string]$values[$name]
    $found = $false
    $lines = @($lines | ForEach-Object {
        if ($_ -match "^$([regex]::Escape($name))=") {
            $found = $true
            $replacement
        }
        else {
            $_
        }
    })
    if (-not $found) {
        $lines += $replacement
    }
}

$utf8NoBom = New-Object System.Text.UTF8Encoding($false)
[IO.File]::WriteAllLines($envPath, $lines, $utf8NoBom)

if ($Clear) {
    Write-Host "Cleared local model API key: $envPath"
}
else {
    Write-Host "Wrote local model configuration: $envPath"
    Write-Host "Provider: $Provider. Restart the service to apply changes."
}
