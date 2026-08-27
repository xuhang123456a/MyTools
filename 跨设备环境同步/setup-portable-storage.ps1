# ==============================================================================
# 跨设备/重装系统：便携数据与绿色工具箱自动化挂载脚本
# 作用：
# 1. 自动创建非系统盘便携工具箱目录 (D:\PortableApps) 并永久挂载到系统 PATH
# 2. 自动创建并初始化非系统盘大模型存储池 (D:\AI_Models)
# ==============================================================================

Write-Host "=============================================" -ForegroundColor Cyan
Write-Host " 正在初始化便携工具箱与大模型存储池..." -ForegroundColor Cyan
Write-Host "=============================================" -ForegroundColor Cyan

# ------------------------------------------------------------------------------
# 1. 创建并挂载独立绿色小工具目录 (D:\MyTools 与 D:\PortableApps) 到 PATH
# ------------------------------------------------------------------------------
$toolDirs = @("D:\MyTools", "D:\PortableApps")
$userPath = [Environment]::GetEnvironmentVariable("Path", "User")
$pathList = $userPath -split ";" | Where-Object { $_ -ne "" }

foreach ($dir in $toolDirs) {
    if (-not (Test-Path $dir)) {
        New-Item -ItemType Directory -Path $dir -Force | Out-Null
        Write-Host "[+] 已就绪工具目录: $dir" -ForegroundColor Green
    }
    if ($pathList -notcontains $dir) {
        $pathList += $dir
        Write-Host "[+] 成功将 $dir 挂载至用户 PATH 环境变量！" -ForegroundColor Green
    } else {
        Write-Host "[*] $dir 已经在 PATH 环境变量中。" -ForegroundColor DarkGray
    }
}
$newUserPath = $pathList -join ";"
[Environment]::SetEnvironmentVariable("Path", $newUserPath, "User")
Write-Host "    (以后把任何免安装 .exe 或脚本丢进 D:\MyTools，Win + R 或终端均可直接秒开)" -ForegroundColor DarkCyan

# ------------------------------------------------------------------------------
# 2. 创建并初始化大模型与 AI 缓存目录结构
# ------------------------------------------------------------------------------
$modelDirs = @(
    "D:\AI_Models\ollama",       # Ollama 模型权重
    "D:\AI_Models\huggingface",  # HuggingFace 模型与分词器缓存
    "D:\AI_Models\lm-studio"     # LM Studio 模型存放区
)

foreach ($dir in $modelDirs) {
    if (-not (Test-Path $dir)) {
        New-Item -ItemType Directory -Path $dir -Force | Out-Null
        Write-Host "[+] 已就绪模型存储目录: $dir" -ForegroundColor Green
    }
}

# ------------------------------------------------------------------------------
# 3. 检查当前 C 盘是否存在历史 Ollama 模型并提示迁移
# ------------------------------------------------------------------------------
$defaultOllamaC = Join-Path $env:USERPROFILE ".ollama\models"
if (Test-Path $defaultOllamaC) {
    $cModelSize = (Get-ChildItem $defaultOllamaC -Recurse -ErrorAction SilentlyContinue | Measure-Object -Property Length -Sum).Sum
    if ($cModelSize -gt 0) {
        $sizeMB = [math]::Round($cModelSize / 1MB, 2)
        Write-Host "`n--------------------------------------------------------" -ForegroundColor Yellow
        Write-Host " [注意] 检测到你的 C 盘中仍有历史 Ollama 模型数据 ($sizeMB MB)！" -ForegroundColor Yellow
        Write-Host " 路径: $defaultOllamaC" -ForegroundColor Yellow
        Write-Host " 建议手动将里面的 manifests 和 blobs 文件夹剪切移动到: D:\AI_Models\ollama" -ForegroundColor Yellow
        Write-Host " 移动后 C 盘将立即释放空间，且模型永久免重新下载！" -ForegroundColor Yellow
        Write-Host "--------------------------------------------------------`n" -ForegroundColor Yellow
    }
}

Write-Host "`n=============================================" -ForegroundColor Green
Write-Host " 便携数据环境与存储池就绪完毕！" -ForegroundColor Green
Write-Host "=============================================" -ForegroundColor Green
