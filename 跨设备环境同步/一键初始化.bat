@echo off
chcp 65001 >nul
title 开发者环境一键初始化向导
echo ========================================================
echo   正在以管理员权限和安全绕过模式启动全套环境恢复向导...
echo ========================================================
echo.

:: 自动请求管理员提权
>nul 2>&1 "%SYSTEMROOT%\system32\cacls.exe" "%SYSTEMROOT%\system32\config\system"
if '%errorlevel%' NEQ '0' (
    echo [提示] 正在请求 Windows 管理员权限...
    goto UACPrompt
) else ( goto gotAdmin )

:UACPrompt
    echo Set UAC = CreateObject^("Shell.Application"^) > "%temp%\getadmin.vbs"
    echo UAC.ShellExecute "%~s0", "", "", "runas", 1 >> "%temp%\getadmin.vbs"
    "%temp%\getadmin.vbs"
    exit /B

:gotAdmin
    if exist "%temp%\getadmin.vbs" ( del "%temp%\getadmin.vbs" )
    pushd "%CD%"
    CD /D "%~dp0"

:: 绕过 PowerShell 脚本执行策略，直接运行主编排脚本
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0run-all.ps1"

pause
