@echo off
chcp 65001 >nul
title VS Code to Kiro Config Migration
powershell -NoProfile -ExecutionPolicy Bypass -Command "$m='#PS'+'TART#'; $c=[IO.File]::ReadAllText('%~f0',[Text.Encoding]::UTF8); Invoke-Expression $c.Substring($c.IndexOf($m)+$m.Length)"
pause
exit /b
#PSTART#
$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

$KiroProtectedPrefixes = @(
    'kiro','kiroAgent','kiro.agent','kiro-agent',
    'kiroChat','kiro.chat','kiroSpec','kiro.spec',
    'kiroHook','kiro.hook','kiroSteering','kiro.steering',
    'kiroMcp','kiro.mcp'
)
function Test-KiroKey([string]$key) {
    $lower = $key.ToLower()
    foreach ($p in $KiroProtectedPrefixes) {
        $pl = $p.ToLower()
        if ($lower -eq $pl -or $lower.StartsWith("$pl.") -or $lower.StartsWith("${pl}:")) { return $true }
    }
    return $false
}

function Write-Title($text) {
    Write-Host ""; Write-Host ("=" * 70) -ForegroundColor Cyan
    Write-Host "  $text" -ForegroundColor Cyan; Write-Host ("=" * 70) -ForegroundColor Cyan
}
function Write-Step($text)  { Write-Host "[*] $text"  -ForegroundColor Yellow }
function Write-Ok($text)    { Write-Host "[OK] $text" -ForegroundColor Green }
function Write-Warn($text)  { Write-Host "[!] $text"  -ForegroundColor DarkYellow }
function Write-Err($text)   { Write-Host "[X] $text"  -ForegroundColor Red }
function Find-UserDir([string[]]$candidates) {
    foreach ($c in $candidates) { if (Test-Path $c) { return (Resolve-Path $c).Path } }
    return $null
}
function Find-Cli([string[]]$names) {
    foreach ($n in $names) { $cmd = Get-Command $n -ErrorAction SilentlyContinue; if ($cmd) { return $cmd.Source } }
    return $null
}
function Copy-WithBackup([string]$src, [string]$dst) {
    if (-not (Test-Path $src)) { Write-Warn "源不存在，跳过: $src"; return }
    $dstParent = Split-Path $dst -Parent
    if (-not (Test-Path $dstParent)) { New-Item -ItemType Directory -Path $dstParent -Force | Out-Null }
    if (Test-Path $dst) {
        $backupDir = Join-Path $script:KiroUser '_backups'
        if (-not (Test-Path $backupDir)) { New-Item -ItemType Directory -Path $backupDir -Force | Out-Null }
        $stamp = Get-Date -Format 'yyyyMMdd_HHmmss'
        $leafName = Split-Path $dst -Leaf
        $backup = Join-Path $backupDir "$leafName.bak_$stamp"
        if ((Get-Item $dst).PSIsContainer) { Copy-Item -Path $dst -Destination $backup -Recurse -Force }
        else { Copy-Item -Path $dst -Destination $backup -Force }
        Write-Warn "已备份 -> $backup"
    }
    if ((Get-Item $src).PSIsContainer) { Copy-Item -Path $src -Destination $dst -Recurse -Force }
    else { Copy-Item -Path $src -Destination $dst -Force }
    Write-Ok "已迁移: $(Split-Path $src -Leaf)"
}

function Migrate-SettingsSmart {
    $srcFile = Join-Path $VSCodeUser 'settings.json'
    $dstFile = Join-Path $KiroUser 'settings.json'
    if (-not (Test-Path $srcFile)) { Write-Warn "VS Code settings.json 不存在。"; return }
    $srcRaw = Get-Content $srcFile -Raw -Encoding UTF8
    $srcClean = ($srcRaw -split "`n" | Where-Object { $_ -notmatch '^\s*//' }) -join "`n"
    $srcClean = $srcClean -replace ',(\s*[}\]])', '$1'
    try { $srcObj = $srcClean | ConvertFrom-Json } catch { Write-Err "解析失败: $($_.Exception.Message)"; return }
    $kiroKeys = @{}
    if (Test-Path $dstFile) {
        $backupDir = Join-Path $script:KiroUser '_backups'
        if (-not (Test-Path $backupDir)) { New-Item -ItemType Directory -Path $backupDir -Force | Out-Null }
        $stamp = Get-Date -Format 'yyyyMMdd_HHmmss'
        Copy-Item $dstFile (Join-Path $backupDir "settings.json.bak_$stamp") -Force
        Write-Warn "已备份 settings.json"
        $dstRaw = Get-Content $dstFile -Raw -Encoding UTF8
        $dstClean = ($dstRaw -split "`n" | Where-Object { $_ -notmatch '^\s*//' }) -join "`n"
        $dstClean = $dstClean -replace ',(\s*[}\]])', '$1'
        try {
            $dstObj = $dstClean | ConvertFrom-Json
            foreach ($prop in $dstObj.PSObject.Properties) { if (Test-KiroKey $prop.Name) { $kiroKeys[$prop.Name] = $prop.Value } }
        } catch { Write-Warn "Kiro settings 解析失败，将整体覆盖。" }
    }
    $merged = [ordered]@{}
    foreach ($prop in $srcObj.PSObject.Properties) { if (-not (Test-KiroKey $prop.Name)) { $merged[$prop.Name] = $prop.Value } }
    foreach ($kv in $kiroKeys.GetEnumerator()) { $merged[$kv.Key] = $kv.Value }
    [IO.File]::WriteAllText($dstFile, ($merged | ConvertTo-Json -Depth 20), [Text.Encoding]::UTF8)
    Write-Ok "settings.json 智能合并完成。"
    if ($kiroKeys.Count -gt 0) {
        Write-Ok "保留了 $($kiroKeys.Count) 个 Kiro 特有设置："
        foreach ($k in $kiroKeys.Keys) { Write-Host "    * $k" -ForegroundColor Green }
    }
}

function Migrate-Keybindings { Copy-WithBackup (Join-Path $VSCodeUser 'keybindings.json') (Join-Path $KiroUser 'keybindings.json') }
function Migrate-Snippets    { Copy-WithBackup (Join-Path $VSCodeUser 'snippets')         (Join-Path $KiroUser 'snippets') }
function Migrate-Tasks       { Copy-WithBackup (Join-Path $VSCodeUser 'tasks.json')       (Join-Path $KiroUser 'tasks.json') }
function Migrate-Extensions {
    if (-not $CodeCli) { Write-Err "缺少 code CLI。"; return }
    $listFile = Join-Path ([Environment]::GetFolderPath('Desktop')) 'vscode-extensions.txt'
    Write-Step "导出扩展清单 -> $listFile"
    & $CodeCli --list-extensions | Out-File -FilePath $listFile -Encoding utf8
    $exts = Get-Content $listFile | Where-Object { $_.Trim() -ne '' }
    Write-Ok "共 $($exts.Count) 个扩展。"
    if (-not $KiroCli) { Write-Warn "缺少 kiro CLI，清单已在桌面。"; return }
    $go = Read-Host "在 Kiro 中安装？(y/N)"
    if ($go -notmatch '^[Yy]') { return }
    $fail = @()
    foreach ($e in $exts) {
        Write-Step "安装 $e"
        try { & $KiroCli --install-extension $e 2>&1 | Out-Null
            if ($LASTEXITCODE -eq 0) { Write-Ok $e } else { $fail += $e; Write-Warn "失败: $e" }
        } catch { $fail += $e; Write-Warn "失败: $e" }
    }
    if ($fail.Count -gt 0) { Write-Warn "$($fail.Count) 个失败："; $fail | ForEach-Object { Write-Host "    - $_" -ForegroundColor DarkYellow } }
    else { Write-Ok "全部成功。" }
}
function Migrate-All { Migrate-SettingsSmart; Migrate-Keybindings; Migrate-Snippets; Migrate-Tasks; Migrate-Extensions }

function Compare-JsonFiles([string]$fileA, [string]$fileB, [string]$labelA, [string]$labelB) {
    if (-not (Test-Path $fileA)) { Write-Warn "$labelA 不存在"; return }
    if (-not (Test-Path $fileB)) { Write-Warn "$labelB 不存在"; return }
    $a = Get-Content $fileA -Raw -Encoding UTF8; $b = Get-Content $fileB -Raw -Encoding UTF8
    if ($a.Trim() -eq $b.Trim()) { Write-Ok "完全一致。"; return }
    $cleanA = (($a -split "`n" | Where-Object { $_ -notmatch '^\s*//' }) -join "`n") -replace ',(\s*[}\]])', '$1'
    $cleanB = (($b -split "`n" | Where-Object { $_ -notmatch '^\s*//' }) -join "`n") -replace ',(\s*[}\]])', '$1'
    try { $objA = $cleanA | ConvertFrom-Json; $objB = $cleanB | ConvertFrom-Json } catch {
        Write-Warn "JSON 解析失败，文本差异："; $diff = Compare-Object ($a -split "`n") ($b -split "`n")
        if ($diff.Count -gt 20) { Write-Host "  $($diff.Count) 处差异" } else { $diff | ForEach-Object { Write-Host "  $($_.SideIndicator) $($_.InputObject)" } }
        return
    }
    $propsA = $objA.PSObject.Properties | ForEach-Object { $_.Name }
    $propsB = $objB.PSObject.Properties | ForEach-Object { $_.Name }
    $allKeys = ($propsA + $propsB) | Sort-Object -Unique
    $onlyInA = @(); $onlyInB = @(); $differ = @()
    foreach ($k in $allKeys) {
        $inA = $k -in $propsA; $inB = $k -in $propsB
        if ($inA -and -not $inB) { $onlyInA += $k }
        elseif ($inB -and -not $inA) { $onlyInB += $k }
        else { $vA = ($objA.$k | ConvertTo-Json -Depth 5 -Compress); $vB = ($objB.$k | ConvertTo-Json -Depth 5 -Compress); if ($vA -ne $vB) { $differ += $k } }
    }
    if ($onlyInA.Count -eq 0 -and $onlyInB.Count -eq 0 -and $differ.Count -eq 0) { Write-Ok "内容等价。"; return }
    if ($onlyInA.Count -gt 0) { Write-Host "  仅 $labelA ($($onlyInA.Count)):" -ForegroundColor Magenta; $onlyInA | ForEach-Object { Write-Host "    + $_" } }
    if ($onlyInB.Count -gt 0) { Write-Host "  仅 $labelB ($($onlyInB.Count)):" -ForegroundColor Magenta; $onlyInB | ForEach-Object { Write-Host "    + $_" } }
    if ($differ.Count -gt 0) {
        Write-Host "  值不同 ($($differ.Count)):" -ForegroundColor Magenta
        foreach ($k in $differ) {
            $vA = $objA.$k | ConvertTo-Json -Depth 2 -Compress; $vB = $objB.$k | ConvertTo-Json -Depth 2 -Compress
            if ($vA.Length -gt 60) { $vA = $vA.Substring(0,57)+'...' }; if ($vB.Length -gt 60) { $vB = $vB.Substring(0,57)+'...' }
            Write-Host "    $k" -ForegroundColor White
            Write-Host "      $labelA`: $vA" -ForegroundColor Gray; Write-Host "      $labelB`: $vB" -ForegroundColor Gray
        }
    }
}

function Compare-Dirs([string]$dirA, [string]$dirB, [string]$labelA, [string]$labelB) {
    if (-not (Test-Path $dirA)) { Write-Warn "$labelA 不存在"; return }
    if (-not (Test-Path $dirB)) { Write-Warn "$labelB 不存在"; return }
    $filesA = Get-ChildItem $dirA -File -Recurse | ForEach-Object { $_.Name }
    $filesB = Get-ChildItem $dirB -File -Recurse | ForEach-Object { $_.Name }
    $onlyA = $filesA | Where-Object { $_ -notin $filesB }; $onlyB = $filesB | Where-Object { $_ -notin $filesA }
    if ($onlyA.Count -eq 0 -and $onlyB.Count -eq 0) { Write-Ok "一致。" }
    else {
        if ($onlyA.Count -gt 0) { Write-Host "  仅 $labelA ($($onlyA.Count)):" -ForegroundColor Magenta; $onlyA | ForEach-Object { Write-Host "    + $_" } }
        if ($onlyB.Count -gt 0) { Write-Host "  仅 $labelB ($($onlyB.Count)):" -ForegroundColor Magenta; $onlyB | ForEach-Object { Write-Host "    + $_" } }
    }
}
function Show-Diff {
    Write-Title "VS Code vs Kiro 差异对比"
    Write-Step "settings.json"
    Compare-JsonFiles (Join-Path $VSCodeUser 'settings.json') (Join-Path $KiroUser 'settings.json') 'VS Code' 'Kiro'
    Write-Host ""; Write-Step "keybindings.json"
    Compare-JsonFiles (Join-Path $VSCodeUser 'keybindings.json') (Join-Path $KiroUser 'keybindings.json') 'VS Code' 'Kiro'
    Write-Host ""; Write-Step "snippets"
    Compare-Dirs (Join-Path $VSCodeUser 'snippets') (Join-Path $KiroUser 'snippets') 'VS Code' 'Kiro'
    Write-Host ""; Write-Step "tasks.json"
    $ta = Join-Path $VSCodeUser 'tasks.json'; $tb = Join-Path $KiroUser 'tasks.json'
    if ((Test-Path $ta) -and (Test-Path $tb)) { if ((Get-Content $ta -Raw -Encoding UTF8).Trim() -eq (Get-Content $tb -Raw -Encoding UTF8).Trim()) { Write-Ok "一致。" } else { Write-Warn "不同。" } }
    elseif (-not (Test-Path $ta)) { Write-Warn "VS Code 无 tasks.json" } else { Write-Warn "Kiro 无 tasks.json" }
    Write-Host ""; Write-Step "Extensions"
    if ($CodeCli -and $KiroCli) {
        $extV = & $CodeCli --list-extensions 2>$null | Where-Object { $_.Trim() -ne '' }
        $extK = & $KiroCli --list-extensions 2>$null | Where-Object { $_.Trim() -ne '' }
        $onlyV = $extV | Where-Object { $_ -notin $extK }; $onlyK = $extK | Where-Object { $_ -notin $extV }
        Write-Host "  VS Code: $($extV.Count), Kiro: $($extK.Count)"
        if ($onlyV.Count -gt 0) { Write-Host "  仅 VS Code ($($onlyV.Count)):" -ForegroundColor Magenta; $onlyV | ForEach-Object { Write-Host "    + $_" } }
        if ($onlyK.Count -gt 0) { Write-Host "  仅 Kiro ($($onlyK.Count)):" -ForegroundColor Magenta; $onlyK | ForEach-Object { Write-Host "    + $_" } }
        if ($onlyV.Count -eq 0 -and $onlyK.Count -eq 0) { Write-Ok "一致。" }
    } else { Write-Warn "需要 code 和 kiro CLI 都可用。" }
}

function Get-AllBackups {
    $results = @()
    $backupDir = Join-Path $script:KiroUser '_backups'
    if (Test-Path $backupDir) {
        Get-ChildItem $backupDir | Where-Object { $_.Name -match '\.bak_\d{8}_\d{6}' } | ForEach-Object { $results += $_ }
    }
    Get-ChildItem $script:KiroUser -File | Where-Object { $_.Name -match '\.bak_\d{8}_\d{6}' } | ForEach-Object { $results += $_ }
    Get-ChildItem $script:KiroUser -Directory | Where-Object { $_.Name -match '\.bak_\d{8}_\d{6}' } | ForEach-Object { $results += $_ }
    return $results | Sort-Object LastWriteTime -Descending
}
function Show-Backups {
    $files = Get-AllBackups
    if ($files.Count -eq 0) { Write-Warn "暂无备份。"; return }
    Write-Step "找到 $($files.Count) 个备份文件："
    Write-Host ""
    foreach ($f in $files) {
        $size = if ($f.PSIsContainer) { '[DIR]' } else { '{0:N1} KB' -f ($f.Length/1KB) }
        $loc = if ($f.DirectoryName -match '_backups') { '' } else { ' [旧版位置]' }
        Write-Host "  $($f.Name)  $size  $loc" -ForegroundColor Gray
    }
    Write-Host ""
    $backupDir = Join-Path $script:KiroUser '_backups'
    if (Test-Path $backupDir) { Start-Process explorer.exe $backupDir } else { Start-Process explorer.exe $script:KiroUser }
    Write-Ok "已打开目录。"
}

function Restore-Backup {
    $files = Get-AllBackups
    if ($files.Count -eq 0) { Write-Warn "暂无备份可恢复。"; return }
    Write-Title "恢复备份"
    Write-Host ""
    for ($i = 0; $i -lt $files.Count; $i++) {
        $f = $files[$i]
        $size = if ($f.PSIsContainer) { '[DIR]' } else { '{0:N1} KB' -f ($f.Length/1KB) }
        $time = $f.LastWriteTime.ToString('yyyy-MM-dd HH:mm:ss')
        $loc = if ($f.DirectoryName -match '_backups') { '' } else { ' [旧]' }
        Write-Host "  $($i+1)) $($f.Name)  $size  [$time]$loc"
    }
    Write-Host "  0) 取消" -ForegroundColor Gray; Write-Host ""
    $sel = Read-Host "选择序号"
    if ($sel -eq '0' -or $sel -eq '') { return }
    $idx = 0
    if (-not [int]::TryParse($sel, [ref]$idx)) { Write-Warn "无效。"; return }
    if ($idx -lt 1 -or $idx -gt $files.Count) { Write-Warn "超出范围。"; return }
    $chosen = $files[$idx - 1]
    $originalName = $chosen.Name -replace '\.bak_\d{8}_\d{6}$', ''
    if ($originalName -eq $chosen.Name) {
        Write-Warn "无法识别原始文件名。"
        $originalName = Read-Host "输入目标文件名（如 settings.json）"
        if (-not $originalName) { return }
    }
    $targetPath = Join-Path $script:KiroUser $originalName
    Write-Host ""
    Write-Host "  备份: $($chosen.FullName)" -ForegroundColor Cyan
    Write-Host "  恢复到: $targetPath" -ForegroundColor Cyan; Write-Host ""
    $confirm = Read-Host "确认恢复？(y/N)"
    if ($confirm -notmatch '^[Yy]') { return }
    if ($chosen.PSIsContainer) {
        if (Test-Path $targetPath) { Remove-Item $targetPath -Recurse -Force }
        Copy-Item -Path $chosen.FullName -Destination $targetPath -Recurse -Force
    } else { Copy-Item -Path $chosen.FullName -Destination $targetPath -Force }
    Write-Ok "已恢复: $originalName"
    $del = Read-Host "删除该备份？(y/N)"
    if ($del -match '^[Yy]') { Remove-Item $chosen.FullName -Recurse -Force; Write-Ok "备份已删除。" }
}
function Open-UserDirs {
    if ($VSCodeUser) { Start-Process explorer.exe $VSCodeUser; Write-Ok "已打开 VS Code: $VSCodeUser" } else { Write-Warn "VS Code 目录未知。" }
    if ($KiroUser)   { Start-Process explorer.exe $KiroUser;   Write-Ok "已打开 Kiro: $KiroUser" }   else { Write-Warn "Kiro 目录未知。" }
}

function Show-Intro {
    Clear-Host
    Write-Title "VS Code  ->  Kiro  配置迁移工具"
    Write-Host @"
【这个工具是做什么的】
  Kiro 基于 Code OSS（VS Code 的开源内核），大部分 VS Code 用户配置
  都能直接复用，但 Kiro 没有 VS Code 的云端 Settings Sync，无法一键
  同步。本工具帮你把 VS Code 的本地用户配置安全地迁移到 Kiro。

【可以迁移哪些内容】
  对应 VS Code「设置同步」的各个部分：
  1) Settings      用户设置        settings.json
                   -> 智能合并：用 VS Code 的值覆盖，但自动保留 Kiro
                      自己的设置（kiro / kiroAgent / kiro.* 前缀，例如
                      Kiro Agent: Trusted Commands），不会被冲掉。
  2) Keybindings   键位绑定        keybindings.json
  3) Snippets      代码片段        snippets 文件夹
  4) User Tasks    用户任务        tasks.json
  5) Extensions    扩展(插件)      用命令行导出 VS Code 清单后逐个安装
  注：UI State（窗口布局、最近打开等）两者机制不同，无法可靠迁移。

【关于扩展的限制】
  Kiro 多使用 Open VSX 市场，部分微软自家插件（C#、Pylance、Remote
  系列等）在该市场可能不存在或版本不同，会安装失败。这是无法做到
  100% 一致的主要原因，脚本会把失败的清单单独列出来。

【安全机制】
  * 任何覆盖操作前，都会先把 Kiro 现有文件备份到
    Kiro User\_backups\ 目录，文件名带时间戳。
  * 菜单里的「恢复备份(r)」可随时还原；「查看备份(b)」可打开目录
    自行删除不需要的备份。

【使用建议】
  * 迁移前请先关闭 Kiro，避免配置文件被占用导致写入失败。
  * 本脚本只读 VS Code、只写 Kiro，不会改动你的 VS Code 配置。
  * 可直接拷贝给其他电脑使用，路径由环境变量自动探测。
"@ -ForegroundColor Gray
    Write-Host ""
    Read-Host "阅读完毕，按 Enter 开始检测目录"
}

function Resolve-Dirs {
    Write-Title "检测目录"
    $appdata = $env:APPDATA; $userHome = $env:USERPROFILE
    $script:VSCodeUser = Find-UserDir @((Join-Path $appdata 'Code\User'),(Join-Path $appdata 'Code - Insiders\User'),(Join-Path $appdata 'VSCodium\User'))
    $script:KiroUser = Find-UserDir @((Join-Path $appdata 'Kiro\User'),(Join-Path $userHome '.kiro\User'))
    if ($script:VSCodeUser) { Write-Ok "VS Code: $script:VSCodeUser" } else { Write-Err "未找到 VS Code 目录" }
    if ($script:KiroUser) { Write-Ok "Kiro:    $script:KiroUser" }
    else {
        Write-Warn "未找到 Kiro 目录（可能 Kiro 还没运行过一次）。"
        $m = Read-Host "手动输入 Kiro User 目录路径（回车跳过）"
        if ($m -and (Test-Path $m)) { $script:KiroUser = (Resolve-Path $m).Path; Write-Ok "Kiro: $script:KiroUser" }
    }
    $script:CodeCli = Find-Cli @('code','code-insiders','codium')
    $script:KiroCli = Find-Cli @('kiro')
    if ($script:CodeCli) { Write-Ok "code CLI: $script:CodeCli" } else { Write-Warn "未找到 code CLI（扩展功能不可用）" }
    if ($script:KiroCli) { Write-Ok "kiro CLI: $script:KiroCli" } else { Write-Warn "未找到 kiro CLI（扩展安装不可用）" }
    Write-Host ""
    Read-Host "按 Enter 进入菜单"
}
function Show-Menu {
    while ($true) {
        Write-Host ""
        Write-Title "菜单"
        Write-Host "  1) 迁移 Settings（智能合并，保留 Kiro 特有设置）"
        Write-Host "  2) 迁移 Keybindings"
        Write-Host "  3) 迁移 Snippets"
        Write-Host "  4) 迁移 Tasks"
        Write-Host "  5) 迁移 Extensions"
        Write-Host "  6) 一键迁移全部" -ForegroundColor Green
        Write-Host ""
        Write-Host "  d) 对比差异"
        Write-Host "  b) 查看备份"
        Write-Host "  r) 恢复备份"
        Write-Host "  o) 打开 VS Code / Kiro 用户目录"
        Write-Host "  0) 退出" -ForegroundColor Gray
        Write-Host ""
        $choice = Read-Host "选项"
        try {
            switch ($choice.ToLower()) {
                '1' { Migrate-SettingsSmart }
                '2' { Migrate-Keybindings }
                '3' { Migrate-Snippets }
                '4' { Migrate-Tasks }
                '5' { Migrate-Extensions }
                '6' { Migrate-All }
                'd' { Show-Diff }
                'b' { Show-Backups }
                'r' { Restore-Backup }
                'o' { Open-UserDirs }
                '0' { Write-Host "已退出。" -ForegroundColor Gray; return }
                default { Write-Warn "无效。" }
            }
        } catch { Write-Err "出错: $($_.Exception.Message)" }
    }
}
Show-Intro; Resolve-Dirs; Show-Menu
