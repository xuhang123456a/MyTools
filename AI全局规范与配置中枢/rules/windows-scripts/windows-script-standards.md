# 🪟 Windows 脚本开发规范 (Batch & PowerShell Standards)

> **适用范围**：所有涉及 Windows 批处理 (`.bat` / `.cmd`) 与 PowerShell (`.ps1`) 脚本编写、用户交互与脚本执行任务。
> **核心目标**：彻底杜绝控制台乱码、CMD 解析语法崩溃、UAC 提权失败与无感闪退。

---

## 一、 批处理脚本 (`.bat` / `.cmd`) 核心红线

### 1. 编码陷阱与“纯 ASCII 极简引导”黄金法则
- **原因**：Windows `cmd.exe` 双击运行批处理文件时，默认强制使用当前系统的 ANSI 代码页（中文系统为 CP936 / GBK）。若批处理文件以 UTF-8 编码保存且包含中文字符（含中文注释 `::` 或 `echo` 提示），CMD 会因多字节解码错位产生灾难性语法截断（如中文注释被识别为非法命令 `'津级'`、`Start-Process` 被切断识别为 `'t-Process'` 等）。
- **红线规定**：
  - **凡是供用户双击启动的 `.bat` 入口脚本，内部代码严禁包含任何非 ASCII 字符（100% 纯 ASCII 英文编写，无中文字符、无中文注释）**。
  - 所有复杂的业务逻辑、中文彩色输出、交互提示与防闪退逻辑，**统一交由后置调起的 PowerShell 脚本承担**，批处理仅作为纯净无损的“跳板启动器”。

### 2. 双击无感 UAC 管理员提权标准模板
所有需要管理员权限的批处理脚本，统一采用以下经全平台实战验证的 3 行纯 ASCII 提权模板：

```bat
@echo off
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "Start-Process powershell.exe -Verb RunAs -ArgumentList '-NoProfile -ExecutionPolicy Bypass -File \"\"%~dp0<Script_Name>.ps1\"\"'"
```
- **关键细节**：
  - 必须使用 `cd /d "%~dp0"` 确保工作目录锚定在脚本所在文件夹；
  - 必须内联两层双引号 `\"\"%~dp0...\"\"`，确保路径中即使含有空格或中文也能被正确转义传递给子进程；
  - 必须附加 `-NoProfile -ExecutionPolicy Bypass` 确保不受用户个人 Profile 脚本与 ExecutionPolicy 策略限制。

---

## 二、 PowerShell 脚本 (`.ps1`) 编码与执行规范

### 1. 强制 UTF-8 with BOM 规范
- **红线要求**：
  - Windows 自带的经典 Windows PowerShell (5.1) 解析无 BOM 的 UTF-8 脚本时，会强行当作系统 ANSI (GBK) 处理，只要出现中文字符（与 `[`、`]`、`"` 等字节冲突），就会报 `MissingArrayIndexExpression` 等解析错误导致瞬时闪退。
  - **凡包含中文界面的 `.ps1` 脚本，必须强制保存为 UTF-8 with BOM (`utf-8-sig`) 编码**。

### 2. 控制台窗口停留与防闪退准则
- **红线要求**：
  - **严禁**在脚本末尾仅使用 `[Console]::ReadKey()`。在非交互式管道、重定向或特定虚拟终端下，调用此方法会直接抛出 `InvalidOperationException` 导致脚本崩溃关闭。
  - **标准停留模板**：
    ```powershell
    Write-Host "`n[提示] 执行完毕，请按回车键退出..." -ForegroundColor Yellow
    [void][System.Console]::ReadLine()
    ```
    `[System.Console]::ReadLine()` 在全版本 Windows PowerShell、PowerShell 7 及各类控制台宿主下均能零异常稳定等待用户敲击回车。
