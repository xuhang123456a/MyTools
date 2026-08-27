# ==============================================================================
# 跨设备/重装系统：环境配置文件一键分发脚本
# 作用：自动将本项目中的 PowerShell Profile、Git 配置、MCP 配置复制到系统对应目录
# ==============================================================================

Write-Host "=============================================" -ForegroundColor Cyan
Write-Host " 正在一键分发开发者个性化环境配置..." -ForegroundColor Cyan
Write-Host "=============================================" -ForegroundColor Cyan

$baseDir = Split-Path -Parent $MyInvocation.MyCommand.Definition

# ------------------------------------------------------------------------------
# 1. 部署 PowerShell Profile 终端配置
# ------------------------------------------------------------------------------
$psProfileDir = [System.IO.Path]::GetDirectoryName($PROFILE)
if (-not (Test-Path $psProfileDir)) {
    New-Item -ItemType Directory -Path $psProfileDir -Force | Out-Null
}
$sourcePsProfile = Join-Path $baseDir "configs\Microsoft.PowerShell_profile.ps1"
if (Test-Path $sourcePsProfile) {
    Copy-Item -Path $sourcePsProfile -Destination $PROFILE -Force
    Write-Host "[+] PowerShell 配置文件已同步至: $PROFILE" -ForegroundColor Green
}

# ------------------------------------------------------------------------------
# 2. 部署 Git 全局配置 (防换行符错乱、提高性能)
# ------------------------------------------------------------------------------
Write-Host "[+] 正在优化 Git 全局配置..." -ForegroundColor Cyan
git config --global core.autocrlf false
git config --global core.quotepath false
git config --global init.defaultBranch main
git config --global pull.rebase false
Write-Host "[+] Git 基础优化配置已就绪 (autocrlf=false, defaultBranch=main)" -ForegroundColor Green

# ------------------------------------------------------------------------------
# 3. 部署 Claude Desktop / MCP 配置文件
# ------------------------------------------------------------------------------
$claudeConfigDir = Join-Path $env:APPDATA "Claude"
if (-not (Test-Path $claudeConfigDir)) {
    New-Item -ItemType Directory -Path $claudeConfigDir -Force | Out-Null
}
$sourceMcp = Join-Path $baseDir "configs\claude_desktop_config.json"
$targetMcp = Join-Path $claudeConfigDir "claude_desktop_config.json"
if (Test-Path $sourceMcp) {
    Copy-Item -Path $sourceMcp -Destination $targetMcp -Force
    Write-Host "[+] MCP 配置文件已同步至: $targetMcp" -ForegroundColor Green
}

Write-Host "`n=============================================" -ForegroundColor Green
Write-Host " 所有核心配置文件已一键分发到位！" -ForegroundColor Green
Write-Host "=============================================" -ForegroundColor Green
