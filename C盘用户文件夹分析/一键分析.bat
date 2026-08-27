@echo off
chcp 65001 >nul
title Windows 用户目录点号文件夹深度分析工具

echo ================================================================================
echo           Windows 用户目录点号文件夹深度分析与空间优化报告生成器
echo ================================================================================
echo.

where python >nul 2>nul
if %ERRORLEVEL% equ 0 (
    echo [*] 检测到系统已安装 Python，使用高性能 Python 引擎分析...
    python "%~dp0analyzer.py"
) else (
    echo [*] 未检测到 Python 环境，自动切换为 Windows 原生 PowerShell 引擎...
    powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0analyzer.ps1"
)

echo.
echo ================================================================================
echo [*] 分析已完成！报告已保存在 当前目录下的 reports 文件夹中。
echo ================================================================================
echo.

set "LATEST_REPORT=%~dp0reports\用户目录点号文件夹全面解析报告_最新.md"
if exist "%LATEST_REPORT%" (
    echo 是否现在打开生成的分析报告？(Y/N)
    set /p CHOICE="请输入选择 [默认 Y]: "
    if /i "%CHOICE%"=="" set CHOICE=Y
    if /i "%CHOICE%"=="Y" start "" "%LATEST_REPORT%"
)

pause
