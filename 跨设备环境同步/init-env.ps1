# ==============================================================================
# 跨设备/重装系统：全局用户环境变量与开发镜像源一键初始化脚本
# 使用方式：在此处填入你的常用 API Key / 路径，右键选择使用 PowerShell 运行
# ==============================================================================

Write-Host "=============================================" -ForegroundColor Cyan
Write-Host " 正在注入全局用户环境变量与常用开发镜像源..." -ForegroundColor Cyan
Write-Host "=============================================" -ForegroundColor Cyan

# ------------------------------------------------------------------------------
# 1. AI Agent 与大模型 API Keys (所有客户端及 CLI Agent 均可自动读取)
# ------------------------------------------------------------------------------
$apiKeys = @{
    # 替换为你自己的实际 Key
    "OPENAI_API_KEY"       = "sk-your-openai-api-key-here"
    "DEEPSEEK_API_KEY"     = "sk-your-deepseek-api-key-here"
    "ANTHROPIC_API_KEY"    = "sk-your-anthropic-api-key-here"
    "SILICONFLOW_API_KEY"  = "sk-your-siliconflow-key-here"
}

foreach ($key in $apiKeys.Keys) {
    if ($apiKeys[$key] -notmatch "your-.*-here") {
        [Environment]::SetEnvironmentVariable($key, $apiKeys[$key], "User")
        Write-Host "[+] 已设置 API Key: $key" -ForegroundColor Green
    } else {
        Write-Host "[-] 跳过未填写的 Key: $key" -ForegroundColor DarkGray
    }
}

# ------------------------------------------------------------------------------
# 2. 本地大模型与缓存目录外置 (重装系统免重新下载几十 GB)
# ------------------------------------------------------------------------------
# 建议将模型和缓存存放在 D 盘或非系统盘
$storagePaths = @{
    "OLLAMA_MODELS"        = "D:\AI_Models\ollama"
    "HF_HOME"              = "D:\AI_Models\huggingface"
}

foreach ($pathVar in $storagePaths.Keys) {
    $targetDir = $storagePaths[$pathVar]
    if (-not (Test-Path $targetDir)) {
        New-Item -ItemType Directory -Path $targetDir -Force | Out-Null
    }
    [Environment]::SetEnvironmentVariable($pathVar, $targetDir, "User")
    Write-Host "[+] 已设置存储路径: $pathVar -> $targetDir" -ForegroundColor Green
}

# ------------------------------------------------------------------------------
# 3. 国内极速开发镜像源 (彻底告别拉取超时)
# ------------------------------------------------------------------------------
$mirrors = @{
    "GOPROXY"              = "https://goproxy.cn,direct"
    "NPM_CONFIG_REGISTRY"  = "https://registry.npmmirror.com"
    "HF_ENDPOINT"          = "https://hf-mirror.com"
    "PIP_INDEX_URL"        = "https://pypi.tuna.tsinghua.edu.cn/simple"
}

foreach ($mirror in $mirrors.Keys) {
    [Environment]::SetEnvironmentVariable($mirror, $mirrors[$mirror], "User")
    Write-Host "[+] 已配置镜像源: $mirror = $($mirrors[$mirror])" -ForegroundColor Green
}

Write-Host "`n=============================================" -ForegroundColor Green
Write-Host " 全局环境变量注入完成！重启终端或软件即可生效。" -ForegroundColor Green
Write-Host "=============================================" -ForegroundColor Green
