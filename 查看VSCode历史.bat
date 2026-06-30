@powershell -NoProfile -ExecutionPolicy Bypass -Command "iex ((Get-Content -LiteralPath '%~f0' -Raw -Encoding UTF8) -replace '(?s)^.*?#__PS__\r?\n','')" & goto :eof
#__PS__
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$base  = Join-Path $env:APPDATA 'Code\User'
$wsDir = Join-Path $base 'workspaceStorage'

# ---- 自动识别 VSCode 可执行文件（多策略，提升跨机器兼容性）----
function Find-Code {
    $g = Get-Command code -ErrorAction SilentlyContinue
    if ($g -and $g.Source) {
        $src = $g.Source
        $exe = Join-Path (Split-Path (Split-Path $src)) 'Code.exe'
        if (Test-Path $exe) { return $exe }
        return $src
    }
    foreach ($c in @(
        "$env:LOCALAPPDATA\Programs\Microsoft VS Code\Code.exe",
        "$env:ProgramFiles\Microsoft VS Code\Code.exe",
        "${env:ProgramFiles(x86)}\Microsoft VS Code\Code.exe"
    )) { if (Test-Path $c) { return $c } }
    foreach ($rp in @(
        'HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\*',
        'HKLM:\Software\Microsoft\Windows\CurrentVersion\Uninstall\*',
        'HKLM:\Software\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall\*'
    )) {
        try {
            $hit = Get-ItemProperty $rp -ErrorAction SilentlyContinue |
                   Where-Object { $_.DisplayName -like '*Visual Studio Code*' -and $_.InstallLocation }
            foreach ($h in $hit) {
                $exe = Join-Path $h.InstallLocation 'Code.exe'
                if (Test-Path $exe) { return $exe }
            }
        } catch {}
    }
    return $null
}
$code = Find-Code

# 把 file:///c%3A/Users/... 这种 URI 还原成 Windows 路径
function Convert-Uri([string]$uri) {
    if (-not $uri) { return $null }
    try {
        $u = [Uri]$uri
        if ($u.IsFile) {
            $lp = $u.LocalPath.Replace('/', '\')
            if ($lp -match '^\\([A-Za-z]:)') { $lp = $lp.Substring(1) }
            return $lp
        }
    } catch {}
    $p = $uri -replace '^file:///', '' -replace '^file://', ''
    $p = [Uri]::UnescapeDataString($p)
    $p = $p.Replace('/', '\')
    if ($p -match '^\\([A-Za-z]:)') { $p = $p.Substring(1) }
    return $p
}

function To-Time($ms) {
    try { return [DateTimeOffset]::FromUnixTimeMilliseconds([long]$ms).LocalDateTime.ToString('yyyy-MM-dd HH:mm') }
    catch { return '' }
}

# 把 JSON 字符串字面量解码(处理 \n \uXXXX \" 等)
function Unescape-Json([string]$s) {
    try { return ('"' + $s + '"' | ConvertFrom-Json) }
    catch { return $s }
}

# 从一个 chatSessions\*.jsonl 取标题与时间。
# 标题直接用会话自带的 customTitle 字段(你在 VSCode 里给会话重命名后就会写入)，
# 还没命名的显示 (未命名)。从未发过消息的空会话(只开了没用)直接忽略不显示。
function Get-SessionInfo([string]$file) {
    try {
        # 标题：customTitle(可能被重命名多次，取最后一次)
        $title = $null
        $tm = Select-String -Path $file -Pattern '"customTitle":"((?:[^"\\]|\\.)*)"' -Encoding UTF8 -AllMatches
        if ($tm) {
            $lastLine = $tm[-1]
            $raw = $lastLine.Matches[$lastLine.Matches.Count - 1].Groups[1].Value
            if ($raw.Trim().Length -gt 0) { $title = Unescape-Json $raw }
        }
        # 没有 customTitle 时，确认是否真的用过(发过消息)，没用过就跳过
        if (-not $title) {
            $used = Select-String -Path $file -Pattern '"message":\{"text":"' -Encoding UTF8 -Quiet
            if (-not $used) { return $null }
            $title = '(未命名)'
        }
        # 时间：creationDate(第一行快照里)
        $date = ''
        $dm = Select-String -Path $file -Pattern '"creationDate":(\d+)' -Encoding UTF8 -List | Select-Object -First 1
        if ($dm) { $date = To-Time $dm.Matches[0].Groups[1].Value }
        $title = ($title -replace '\s+', ' ').Trim()
        if ($title.Length -eq 0) { $title = '(未命名)' }
        return [PSCustomObject]@{ Title = $title; Date = $date }
    } catch { return $null }
}

function Get-Items {
    $list = @()
    if (-not (Test-Path $wsDir)) { return $list }
    $dirs = Get-ChildItem $wsDir -Directory | Sort-Object LastWriteTime -Descending
    foreach ($d in $dirs) {
        $path = $null
        $type = '文件夹'
        $wsJson = Join-Path $d.FullName 'workspace.json'
        if (Test-Path $wsJson) {
            try {
                $w = Get-Content $wsJson -Raw -Encoding UTF8 | ConvertFrom-Json
                if ($w.folder)    { $path = Convert-Uri $w.folder;    $type = '文件夹' }
                elseif ($w.workspace) { $path = Convert-Uri $w.workspace; $type = '工作区' }
            } catch {}
        }
        if (-not $path) { $path = '<未知 (' + $d.Name + ')>' }

        $sessions = @()
        $csDir = Join-Path $d.FullName 'chatSessions'
        if (Test-Path $csDir) {
            foreach ($f in (Get-ChildItem $csDir -Filter *.jsonl -ErrorAction SilentlyContinue)) {
                $info = Get-SessionInfo $f.FullName
                if ($info) { $sessions += $info }
            }
        }
        $list += [PSCustomObject]@{
            Path = $path; Type = $type; Hash = $d.Name; Modified = $d.LastWriteTime; Sessions = $sessions
        }
    }
    return $list
}

function Show-Info {
    Write-Host ''
    Write-Host '===================== VSCode 历史记录 =====================' -ForegroundColor Cyan
    Write-Host "根目录: $base" -ForegroundColor DarkGray
    if ($code) { Write-Host "VSCode 程序: $code" -ForegroundColor DarkGray }
    else { Write-Host 'VSCode 程序: 未找到(仍可查看记录，但无法自动打开工作区)' -ForegroundColor Red }
    Write-Host ''
    Write-Host '【这个文件夹里都放了些啥】' -ForegroundColor Green
    Write-Host '  workspaceStorage\    - 核心。每个打开过的工作区一个子文件夹(名字是哈希)，'
    Write-Host '                         workspace.json 记录该工作区/文件夹的真实路径，'
    Write-Host '                         chatSessions\<uuid>.jsonl 是 Copilot 聊天记录'
    Write-Host '  globalStorage\       - 全局插件数据(含 storage.json 等)'
    Write-Host '  History\             - 文件编辑的本地历史(local history)'
    Write-Host '  settings.json        - 用户设置'
    Write-Host '  注: 标题取会话自带的 customTitle(在 VSCode 里重命名会话即可设置)；'
    Write-Host '      还没命名的显示(未命名)；从没发过消息的空会话已自动忽略。'
    Write-Host '===========================================================' -ForegroundColor Cyan
}

function Show-List($items) {
    Write-Host ''
    Write-Host '【各工作区及其聊天会话】(按最后修改时间倒序)' -ForegroundColor Green
    Write-Host ''
    $i = 0
    foreach ($it in $items) {
        $i++
        Write-Host ("[{0}] " -f $i) -ForegroundColor Yellow -NoNewline
        Write-Host $it.Path -ForegroundColor White -NoNewline
        Write-Host ("   [{0}] ({1} 个会话, 最后修改 {2})" -f $it.Type, $it.Sessions.Count, $it.Modified.ToString('yyyy-MM-dd HH:mm')) -ForegroundColor DarkGray
        if ($it.Sessions.Count -eq 0) { Write-Host '       (无聊天记录)' -ForegroundColor DarkGray }
        else {
            foreach ($s in ($it.Sessions | Sort-Object Date -Descending)) {
                $t = $s.Title
                if ($t.Length -gt 60) { $t = $t.Substring(0, 60) + '...' }
                Write-Host ("       - {0}" -f $t) -ForegroundColor Gray -NoNewline
                if ($s.Date) { Write-Host ("   [{0}]" -f $s.Date) -ForegroundColor DarkGray } else { Write-Host '' }
            }
        }
        Write-Host ''
    }
    Write-Host ("共 {0} 个工作区。" -f $items.Count) -ForegroundColor Cyan
}

# 彻底删除某工作区在 VSCode 里的本地数据(整个 workspaceStorage\<hash> 目录)
function Remove-Workspace($item) {
    $dir = Join-Path $wsDir $item.Hash
    if (-not (Test-Path $dir)) { Write-Host '该工作区存储目录已不存在。' -ForegroundColor Red; return $false }
    Write-Host ''
    Write-Host '!! 危险操作 !! 即将彻底删除该工作区在 VSCode 里的全部本地数据:' -ForegroundColor Red
    Write-Host ("   工作区: {0}" -f $item.Path) -ForegroundColor Yellow
    Write-Host ("   存储目录: {0}" -f $dir) -ForegroundColor Yellow
    Write-Host ("   含 {0} 个聊天会话、编辑状态(state.vscdb)等，删除后不可恢复。" -f $item.Sessions.Count) -ForegroundColor Yellow
    Write-Host '   说明: 你的实际项目文件不受影响。' -ForegroundColor DarkGray
    Write-Host '         "打开最近"列表里的该条目可能仍残留(VSCode 存于全局数据库，本工具不改它以免损坏)，' -ForegroundColor DarkGray
    Write-Host '         如需清除可在 VSCode 的"打开最近"里右键移除。' -ForegroundColor DarkGray
    $c = Read-Host '确认删除请输入大写 YES (其它任意键取消)'
    if ($c -cne 'YES') { Write-Host '已取消，未删除任何内容。' -ForegroundColor Green; return $false }
    try {
        Remove-Item -LiteralPath $dir -Recurse -Force -ErrorAction Stop
        Write-Host '已删除该工作区的全部本地数据。' -ForegroundColor Green
        return $true
    } catch {
        Write-Host ("删除失败: {0}" -f $_.Exception.Message) -ForegroundColor Red
        Write-Host '可能是 VSCode 正在运行占用了文件，请先完全关闭 VSCode 再重试。' -ForegroundColor Red
        return $false
    }
}

# ===== 主流程 =====
Show-Info
Write-Host ''
Write-Host '正在扫描会话记录，请稍候...' -ForegroundColor DarkGray
$items = Get-Items
Show-List $items

while ($true) {
    Write-Host ''
    Write-Host '-----------------------------------------------------------' -ForegroundColor DarkCyan
    Write-Host '请选择操作:' -ForegroundColor Yellow
    Write-Host '  输入数字  -> 用 VSCode 打开对应编号的工作区'
    Write-Host '  D 数字    -> 彻底删除对应编号工作区的本地数据(需输入 YES 确认)'
    Write-Host '  O         -> 打开 VSCode 用户数据文件夹'
    Write-Host '  L         -> 重新显示列表'
    Write-Host '  Q         -> 退出'
    $sel = Read-Host '你的选择'
    $sel = $sel.Trim()

    if ($sel -match '^[Qq]$' -or $sel -eq '') { break }
    elseif ($sel -match '^[Oo]$') {
        if (Test-Path $base) { Start-Process explorer.exe $base; Write-Host '已打开用户数据文件夹。' -ForegroundColor Green }
        else { Write-Host "目录不存在: $base" -ForegroundColor Red }
    }
    elseif ($sel -match '^[Ll]$') { Show-List $items }
    elseif ($sel -match '^[Dd]\s*\d*$') {
        $num = ($sel -replace '\D', '')
        if ($num -eq '') { $num = (Read-Host '请输入要删除的工作区编号').Trim() }
        if ($num -match '^\d+$') {
            $n = [int]$num
            if ($n -ge 1 -and $n -le $items.Count) {
                if (Remove-Workspace $items[$n - 1]) { $items = Get-Items; Show-List $items }
            } else { Write-Host ("编号超出范围(1-{0})。" -f $items.Count) -ForegroundColor Red }
        } else { Write-Host '无效编号。' -ForegroundColor Red }
    }
    elseif ($sel -match '^\d+$') {
        $n = [int]$sel
        if ($n -ge 1 -and $n -le $items.Count) {
            $target = $items[$n - 1].Path
            if (-not $code) { Write-Host '未找到 VSCode 程序，无法自动打开。请手动启动 VSCode 后用"打开文件夹"。' -ForegroundColor Red }
            elseif ($target -like '<*') { Write-Host '该工作区路径未知，无法打开。' -ForegroundColor Red }
            elseif (-not (Test-Path $target)) { Write-Host ("路径已不存在: {0}" -f $target) -ForegroundColor Red }
            else {
                Write-Host ("正在用 VSCode 打开: {0}" -f $target) -ForegroundColor Green
                # 用 cmd 的 start 拉起，让 VSCode 脱离本窗口的进程树/Job；
                # 否则点窗口的 X 关闭本工具时，Windows 会把同一 Job 里的 VSCode 一起杀掉。
                Start-Process -FilePath $env:ComSpec -ArgumentList ('/c start "" "{0}" "{1}"' -f $code, $target) -WindowStyle Hidden
            }
        } else { Write-Host ("编号超出范围(1-{0})。" -f $items.Count) -ForegroundColor Red }
    }
    else { Write-Host '无效输入。' -ForegroundColor Red }
}