# ==============================================================================
# 跨设备/重装系统：全自动软件安装脚本 (基于你当前电脑环境深度定制)
# 使用方式：右键 -> 使用 PowerShell 运行，或在 PowerShell 终端执行 ./install-apps.ps1
# ==============================================================================

# 确保以管理员权限运行提示
$isAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) {
    Write-Warning "【提示】建议右键点击该脚本并选择「以管理员身份运行」，可避免频繁弹出 UAC 提权确认框！"
}

Write-Host "=============================================" -ForegroundColor Cyan
Write-Host " 开始同步安装当前环境的核心软件列表 (winget)..." -ForegroundColor Cyan
Write-Host "=============================================" -ForegroundColor Cyan

# 软件清单分组定义
$categories = [ordered]@{
    "系统必备运行库" = @(
        @{ Name = "VC++ 2015-2022 运行库 (x64)"; Id = "Microsoft.VCRedist.2015+.x64" },
        @{ Name = "VC++ 2015-2022 运行库 (x86)"; Id = "Microsoft.VCRedist.2015+.x86" }
    );
    "开发工具 & 语言环境" = @(
        @{ Name = "Git"; Id = "Git.Git" },
        @{ Name = "GitHub Desktop"; Id = "GitHub.GitHubDesktop" },
        @{ Name = "TortoiseGit (小乌龟)"; Id = "TortoiseGit.TortoiseGit" },
        @{ Name = "Windows Terminal (终端)"; Id = "Microsoft.WindowsTerminal" },
        @{ Name = "WSL (Linux子系统)"; Id = "Microsoft.WSL" },
        @{ Name = "Ripgrep (命令行极速搜索)"; Id = "BurntSushi.ripgrep.MSVC" },
        @{ Name = "VS Code"; Id = "Microsoft.VisualStudioCode" },
        @{ Name = "Visual Studio Community 2026"; Id = "Microsoft.VisualStudio.Community" },
        @{ Name = "Android Studio"; Id = "Google.AndroidStudio" },
        @{ Name = "Node.js (LTS)"; Id = "OpenJS.NodeJS.LTS" },
        @{ Name = "Go 语言环境"; Id = "GoLang.Go" },
        @{ Name = "Java JDK 17"; Id = "Oracle.JDK.17" },
        @{ Name = ".NET SDK 10"; Id = "Microsoft.DotNet.SDK.10" },
        @{ Name = "Python 管理器"; Id = "Python.PythonInstallManager" },
        @{ Name = "Unity Hub"; Id = "Unity.UnityHub" }
    );
    "AI Agent & 笔记知识库" = @(
        @{ Name = "Antigravity"; Id = "Google.Antigravity" },
        @{ Name = "Antigravity Tools"; Id = "lbjlaq.AntigravityTools" },
        @{ Name = "Kiro (Amazon)"; Id = "Amazon.Kiro" },
        @{ Name = "Obsidian (知识库)"; Id = "Obsidian.Obsidian" }
    );
    "浏览器 & 办公通讯" = @(
        @{ Name = "360 极速浏览器 X"; Id = "360.360Chrome.X" },
        @{ Name = "QQ (NT最新版)"; Id = "Tencent.QQ.NT" },
        @{ Name = "微信 (WeChat)"; Id = "Tencent.WeChat.Universal" },
        @{ Name = "钉钉 (DingTalk)"; Id = "Alibaba.DingTalk.Mainland" },
        @{ Name = "WorkBuddy (腾讯)"; Id = "Tencent.WorkBuddy" },
        @{ Name = "WPS Office"; Id = "Kingsoft.WPSOffice.CN" }
    );
    "网盘 & 远程协作 & 网络" = @(
        @{ Name = "坚果云"; Id = "Nutstore.Nutstore" },
        @{ Name = "百度网盘"; Id = "Baidu.BaiduNetdisk" },
        @{ Name = "夸克网盘"; Id = "Alibaba.QuarkCloudDrive" },
        @{ Name = "ToDesk 远程控制"; Id = "Youqu.ToDesk" },
        @{ Name = "UU 远程"; Id = "NetEase.UURemote" },
        @{ Name = "Clash Verge Rev"; Id = "ClashVergeRev.ClashVergeRev" }
    );
    "日常常用小工具" = @(
        @{ Name = "PixPin (截图工具)"; Id = "PixPin.PixPin" },
        @{ Name = "ImageGlass (看图)"; Id = "DuongDieuPhap.ImageGlass" },
        @{ Name = "PotPlayer (播放器)"; Id = "Daum.PotPlayer" },
        @{ Name = "WinRAR"; Id = "RARLab.WinRAR" },
        @{ Name = "360 压缩"; Id = "360.360Zip" }
    )
}

foreach ($category in $categories.Keys) {
    Write-Host "`n----------------------------------------" -ForegroundColor DarkGray
    Write-Host "正在处理分类: 【$category】" -ForegroundColor Yellow
    Write-Host "----------------------------------------" -ForegroundColor DarkGray
    
    foreach ($app in $categories[$category]) {
        Write-Host "-> 正在安装/检查: $($app.Name) ($($app.Id))..." -ForegroundColor Cyan
        winget install --id $app.Id -e --accept-package-agreements --accept-source-agreements --silent
    }
}

Write-Host "`n=============================================" -ForegroundColor Green
Write-Host " 恭喜！当前环境的所有核心软件已全部部署完毕！" -ForegroundColor Green
Write-Host "=============================================" -ForegroundColor Green
pause
