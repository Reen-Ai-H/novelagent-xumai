[CmdletBinding()]
param(
    [switch]$Login,
    [switch]$DeviceLogin,
    [switch]$Info,
    [switch]$Force,
    [string]$EnvId = "xvmai-d1grww3kw98852ee1",
    [string]$ServiceName = "xumai-public-case"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$siteRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location -LiteralPath $siteRoot

function Get-TcbInvocation {
    $tcb = Get-Command tcb.cmd -ErrorAction SilentlyContinue
    if (-not $tcb) {
        $tcb = Get-Command tcb -ErrorAction SilentlyContinue
    }

    if ($tcb) {
        return [pscustomobject]@{
            Executable = $tcb.Source
            Prefix = @()
        }
    }

    $npx = Get-Command npx.cmd -ErrorAction SilentlyContinue
    if (-not $npx) {
        $npx = Get-Command npx -ErrorAction SilentlyContinue
    }
    if (-not $npx) {
        throw "找不到 Node.js/npm。请先安装 Node.js 18 或更高版本。"
    }

    return [pscustomobject]@{
        Executable = $npx.Source
        Prefix = @("--yes", "--package=@cloudbase/cli", "tcb")
    }
}

function Invoke-Tcb {
    param([Parameter(Mandatory = $true)][string[]]$Arguments)

    $invocation = Get-TcbInvocation
    $executable = $invocation.Executable
    $prefix = [string[]]$invocation.Prefix
    & $executable @prefix @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "CloudBase CLI 执行失败，退出码 $LASTEXITCODE。"
    }
}

if ($Login -and $DeviceLogin) {
    throw "-Login 和 -DeviceLogin 只能选择一个。"
}

if ($DeviceLogin) {
    Write-Host "即将进入设备码登录。授权链接可以在任意已登录腾讯云的浏览器中打开。"
    Invoke-Tcb -Arguments @("login", "--flow", "device")
    Write-Host "登录完成。之后可直接运行本脚本部署。"
    exit 0
}

if ($Login) {
    Write-Host "即将进入终端密钥登录。密钥只交给 CloudBase CLI，不会写入项目文件。"
    Invoke-Tcb -Arguments @("login", "--key")
    Write-Host "登录完成。之后可直接运行本脚本部署。"
    exit 0
}

if ($Info) {
    Invoke-Tcb -Arguments @("app", "info", $ServiceName, "--env-id", $EnvId, "--json")
    exit 0
}

$deployArguments = @(
    "app", "deploy", $ServiceName,
    "--env-id", $EnvId,
    "--framework", "static",
    "--output-dir", "./",
    "--deploy-path", "/",
    "--ignore", "README.md,Deploy-CloudBase.ps1,Deploy-CloudBase.cmd,cloudbaserc.json"
)

if ($Force) {
    $deployArguments += "--force"
}

Invoke-Tcb -Arguments $deployArguments
$publicUrl = "https://$ServiceName-$EnvId.webapps.tcloudbase.com/"
Write-Host "部署完成。公开地址：$publicUrl"
