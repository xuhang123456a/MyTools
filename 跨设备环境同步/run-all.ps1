# ==============================================================================
# 开发者跨设备/重装系统：总控编排脚本 (Master Runner)
# ==============================================================================

$baseDir = Split-Path -Parent $MyInvocation.MyCommand.Definition

Clear-Host
Write-Host "================================================================" -ForegroundColor Cyan
Write-Host "     🚀 开发者全套环境一键部署与同步总控向导 (Zero-Cost Sync)      " -ForegroundColor Yellow
Write-Host "================================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host " [1] 全部执行 (推荐: 依序执行软件安装、变量注入、存储挂载与配置分发)" -ForegroundColor Green
Write-Host " [2] 仅安装 38 款核心软件 (install-apps.ps1)" -ForegroundColor White
Write-Host " [3] 仅注入全局环境变量与镜像源 (init-env.ps1)" -ForegroundColor White
Write-Host " [4] 仅挂载便携工具箱与大模型存储池 (setup-portable-storage.ps1)" -ForegroundColor White
Write-Host " [5] 仅分发终端 Profile 与 MCP 配置文件 (sync-configs.ps1)" -ForegroundColor White
Write-Host " [Q] 退出" -ForegroundColor DarkGray
Write-Host ""

$choice = Read-Host "请选择要执行的操作 [默认回车直接执行 1 - 全部]"
if ([string]::IsNullOrWhiteSpace($choice)) { $choice = "1" }

function Run-ScriptStep {
    param([string]$ScriptName, [string]$StepTitle)
    Write-Host "`n========================================================" -ForegroundColor Magenta
    Write-Host " >>> 步骤执行中: $StepTitle ($ScriptName)" -ForegroundColor Yellow
    Write-Host "========================================================" -ForegroundColor Magenta
    $scriptPath = Join-Path $baseDir $ScriptName
    if (Test-Path $scriptPath) {
        & $scriptPath
    } else {
        Write-Error "未找到脚本: $scriptPath"
    }
}

switch ($choice) {
    "1" {
        Run-ScriptStep "setup-portable-storage.ps1" "初始化非系统盘便携工具箱与模型存储池"
        Run-ScriptStep "init-env.ps1" "注入全局 API Keys 与国内极速开发源"
        Run-ScriptStep "sync-configs.ps1" "分发终端增强 Profile 与 MCP 配置文件"
        Run-ScriptStep "install-apps.ps1" "通过 Winget 静默安装 38 款核心软件"
        Write-Host "`n🎉 全部 4 大模块已全部执行完毕！环境已完美恢复！" -ForegroundColor Green
    }
    "2" { Run-ScriptStep "install-apps.ps1" "通过 Winget 静默安装 38 款核心软件" }
    "3" { Run-ScriptStep "init-env.ps1" "注入全局 API Keys 与国内极速开发源" }
    "4" { Run-ScriptStep "setup-portable-storage.ps1" "初始化非系统盘便携工具箱与模型存储池" }
    "5" { Run-ScriptStep "sync-configs.ps1" "分发终端增强 Profile 与 MCP 配置文件" }
    "Q" { Write-Host "已退出。" -ForegroundColor Yellow; exit }
    "q" { Write-Host "已退出。" -ForegroundColor Yellow; exit }
    default { Write-Warning "无效选项，操作已取消。" }
}
