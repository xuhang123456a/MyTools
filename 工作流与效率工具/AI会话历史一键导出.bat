@powershell -NoProfile -ExecutionPolicy Bypass -Command "$scriptDir = (Get-Item -LiteralPath '%~f0').DirectoryName; $cliArgs = '%*'; iex ((Get-Content -LiteralPath '%~f0' -Raw -Encoding UTF8) -replace '(?s)^.*?#__PS__\r?\n','')" & goto :eof
#__PS__
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

$mainPy = Join-Path $scriptDir "AI会话历史一键导出工具\main.py"

# 查找 Python
$python = (Get-Command python, py -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Source -First 1)
if (-not $python) {
    $cands = @(
        "$env:LOCALAPPDATA\Programs\Python\Python313\python.exe",
        "$env:LOCALAPPDATA\Programs\Python\Python312\python.exe",
        "$env:LOCALAPPDATA\Programs\Python\Python311\python.exe",
        "$env:LOCALAPPDATA\Programs\Python\Python310\python.exe",
        "$env:ProgramFiles\Python313\python.exe",
        "$env:ProgramFiles\Python312\python.exe",
        "$env:ProgramFiles\Python311\python.exe"
    )
    foreach ($c in $cands) { if (Test-Path $c) { $python = $c; break } }
}

if (-not $python) {
    Write-Host "[错误] 未检测到 Python 环境，请先安装 Python 3.8+！" -ForegroundColor Red
    Read-Host "按回车键退出..."
    exit 1
}

if ([string]::IsNullOrWhiteSpace($cliArgs)) {
    Start-Process $python -ArgumentList "`"$mainPy`" --gui"
} else {
    $argList = $cliArgs.Split(' ') | Where-Object { $_ -ne '' }
    & $python "$mainPy" $argList
}
