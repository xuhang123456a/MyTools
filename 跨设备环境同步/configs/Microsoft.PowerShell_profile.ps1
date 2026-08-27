# ==============================================================================
# 开发者高生产力 PowerShell Profile 配置文件
# ==============================================================================

# ------------------------------------------------------------------------------
# 1. 终端常用高效快捷别名 (Aliases)
# ------------------------------------------------------------------------------
Set-Alias -Name g -Value git
Set-Alias -Name ll -Value Get-ChildItem

# 快捷打开当前目录
function Open-Here { explorer.exe . }
Set-Alias -Name cde -Value Open-Here

# 快速清屏
function Clear-Screen-Fast { Clear-Host }
Set-Alias -Name cls -Value Clear-Screen-Fast

# ------------------------------------------------------------------------------
# 2. Git 快捷增强函数
# ------------------------------------------------------------------------------
function g-log {
    git log --graph --pretty=format:'%Cred%h%Creset -%C(yellow)%d%Creset %s %Cgreen(%cr) %C(bold blue)<%an>%Creset' --abbrev-commit
}
function g-st { git status -sb }
function g-push { git push origin (git branch --show-current) }
function g-pull { git pull origin (git branch --show-current) }

# ------------------------------------------------------------------------------
# 3. 终端网络代理一键开关 (解决终端拉取 GitHub/AI 模型超时)
# ------------------------------------------------------------------------------
function set-proxy {
    param([int]$port = 7890)
    $env:HTTP_PROXY = "http://127.0.0.1:$port"
    $env:HTTPS_PROXY = "http://127.0.0.1:$port"
    $env:ALL_PROXY = "socks5://127.0.0.1:$port"
    Write-Host "[√] 终端代理已开启 -> 127.0.0.1:$port" -ForegroundColor Green
}

function unset-proxy {
    $env:HTTP_PROXY = ""
    $env:HTTPS_PROXY = ""
    $env:ALL_PROXY = ""
    Write-Host "[X] 终端代理已关闭" -ForegroundColor Yellow
}

# ------------------------------------------------------------------------------
# 4. 常用维护快捷指令
# ------------------------------------------------------------------------------
function update-all {
    Write-Host "正在通过 winget 一键升级系统中所有可更新软件..." -ForegroundColor Cyan
    winget upgrade --all --accept-package-agreements --accept-source-agreements
}

Write-Host "--------------------------------------------------------" -ForegroundColor DarkGray
Write-Host " 🚀 开发者终端增强环境已加载 (输入 set-proxy 开启代理, update-all 升级全机软件)" -ForegroundColor DarkCyan
Write-Host "--------------------------------------------------------" -ForegroundColor DarkGray
