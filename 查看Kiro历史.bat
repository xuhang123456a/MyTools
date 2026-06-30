@powershell -NoProfile -ExecutionPolicy Bypass -Command "iex ((Get-Content -LiteralPath '%~f0' -Raw -Encoding UTF8) -replace '(?s)^.*?#__PS__\r?\n','')" & goto :eof
#__PS__
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$base  = Join-Path $env:APPDATA 'Kiro\User\globalStorage\kiro.kiroagent'
$wsDir = Join-Path $base 'workspace-sessions'

# ---- 自动识别 Kiro 可执行文件（多策略，提升跨机器兼容性）----
function Find-Kiro {
    # 1) PATH 中的 kiro / kiro.cmd
    $g = Get-Command kiro -ErrorAction SilentlyContinue
    if ($g -and $g.Source) {
        $src = $g.Source
        if ($src -like '*.exe') { return $src }
        $exe = Join-Path (Split-Path (Split-Path $src)) 'Kiro.exe'
        if (Test-Path $exe) { return $exe }
        return $src
    }
    # 2) 常见安装路径
    foreach ($c in @(
        "$env:LOCALAPPDATA\Programs\Kiro\Kiro.exe",
        "$env:LOCALAPPDATA\Programs\kiro\Kiro.exe",
        "$env:ProgramFiles\Kiro\Kiro.exe",
        "${env:ProgramFiles(x86)}\Kiro\Kiro.exe"
    )) { if (Test-Path $c) { return $c } }
    # 3) 注册表卸载信息里的安装位置
    foreach ($rp in @(
        'HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\*',
        'HKLM:\Software\Microsoft\Windows\CurrentVersion\Uninstall\*',
        'HKLM:\Software\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall\*'
    )) {
        try {
            $hit = Get-ItemProperty $rp -ErrorAction SilentlyContinue |
                   Where-Object { $_.DisplayName -like 'Kiro*' -and $_.InstallLocation }
            foreach ($h in $hit) {
                $exe = Join-Path $h.InstallLocation 'Kiro.exe'
                if (Test-Path $exe) { return $exe }
            }
        } catch {}
    }
    return $null
}
$kiro = Find-Kiro

# 解码工作区目录名：Kiro 用 _ 同时表示 base64 的 / 和填充符 =
function Decode-WsName([string]$name) {
    $b = $name.Replace('-', '+')
    foreach ($pad in 2, 1, 0) {
        if ($b.Length -lt $pad) { continue }
        $body = $b.Substring(0, $b.Length - $pad).Replace('_', '/')
        $cand = $body + ('=' * $pad)
        try { $bytes = [System.Convert]::FromBase64String($cand) } catch { continue }
        $str = [System.Text.Encoding]::UTF8.GetString($bytes)
        $re = [System.Convert]::ToBase64String([System.Text.Encoding]::UTF8.GetBytes($str)).Replace('+', '-').Replace('/', '_').Replace('=', '_')
        if ($re -eq $name) { return $str }
    }
    return '<解码失败>'
}

function To-Time([string]$ms) {
    try { return [DateTimeOffset]::FromUnixTimeMilliseconds([long]$ms).LocalDateTime.ToString('yyyy-MM-dd HH:mm') }
    catch { return '' }
}

function Get-Items {
    $list = @()
    if (-not (Test-Path $wsDir)) { return $list }
    $dirs = Get-ChildItem $wsDir -Directory | Sort-Object LastWriteTime -Descending
    foreach ($d in $dirs) {
        $sessions = @()
        $sf = Join-Path $d.FullName 'sessions.json'
        if (Test-Path $sf) {
            try {
                $json = Get-Content $sf -Raw -Encoding UTF8 | ConvertFrom-Json
                foreach ($s in @($json)) {
                    if ($null -ne $s -and $s.title) {
                        $sessions += [PSCustomObject]@{ Title = ($s.title -replace '\s+', ' '); Date = (To-Time $s.dateCreated) }
                    }
                }
            } catch {}
        }
        $list += [PSCustomObject]@{
            Path = (Decode-WsName $d.Name); EncName = $d.Name; Modified = $d.LastWriteTime; Sessions = $sessions
        }
    }
    return $list
}

function Show-Info {
    Write-Host ''
    Write-Host '======================= Kiro 历史记录 =======================' -ForegroundColor Cyan
    Write-Host "根目录: $base" -ForegroundColor DarkGray
    if ($kiro) { Write-Host "Kiro 程序: $kiro" -ForegroundColor DarkGray }
    else { Write-Host 'Kiro 程序: 未找到(仍可查看记录，但无法自动打开工作区)' -ForegroundColor Red }
    Write-Host ''
    Write-Host '【这个文件夹里都放了些啥】' -ForegroundColor Green
    Write-Host '  workspace-sessions\  - 核心。每个工作区一个子文件夹(名字是工作区路径的编码)，'
    Write-Host '                         里面 <uuid>.json 是一段段完整对话，sessions.json 是该工作区的会话索引'
    Write-Host '  sessions\            - 全局会话索引(sessions.json)'
    Write-Host '  .diffs\              - 对话过程中对你文件做的改动差异(diff)记录'
    Write-Host '  dev_data\            - 使用统计，如 tokens_generated.jsonl 记录每次 token 用量'
    Write-Host '  default\ 及哈希目录  - 按账号 profile 划分的执行记录(executions：每次执行的 id/类型/状态/起止时间)'
    Write-Host '  config.json          - 插件配置'
    Write-Host '  profile.json         - 账号/服务 profile 信息(AWS CodeWhisperer ARN 等)'
    Write-Host '============================================================' -ForegroundColor Cyan
}

function Show-List($items) {
    Write-Host ''
    Write-Host '【各工作区及其会话标题】(按最后修改时间倒序)' -ForegroundColor Green
    Write-Host ''
    $i = 0
    foreach ($it in $items) {
        $i++
        Write-Host ("[{0}] " -f $i) -ForegroundColor Yellow -NoNewline
        Write-Host $it.Path -ForegroundColor White -NoNewline
        Write-Host ("   ({0} 个会话, 最后修改 {1})" -f $it.Sessions.Count, $it.Modified.ToString('yyyy-MM-dd HH:mm')) -ForegroundColor DarkGray
        if ($it.Sessions.Count -eq 0) { Write-Host '       (无会话记录)' -ForegroundColor DarkGray }
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

# 彻底删除某工作区的 Kiro 历史(工作区目录 + 全局 sessions 索引/副本 + .diffs)
function Remove-Workspace($item) {
    $dir = Join-Path $wsDir $item.EncName
    if (-not (Test-Path $dir)) { Write-Host '该工作区目录已不存在。' -ForegroundColor Red; return $false }
    Write-Host ''
    Write-Host '!! 危险操作 !! 即将彻底删除该工作区的 Kiro 历史(对话/索引/差异)，不可恢复:' -ForegroundColor Red
    Write-Host ("   工作区: {0}" -f $item.Path) -ForegroundColor Yellow
    Write-Host ("   目录: {0}" -f $dir) -ForegroundColor Yellow
    Write-Host ("   含 {0} 段会话；同时清理全局 sessions 索引与副本、.diffs 差异记录。" -f $item.Sessions.Count) -ForegroundColor Yellow
    Write-Host '   说明: 你的实际项目文件不受影响。' -ForegroundColor DarkGray
    $c = Read-Host '确认删除请输入大写 YES (其它任意键取消)'
    if ($c -cne 'YES') { Write-Host '已取消，未删除任何内容。' -ForegroundColor Green; return $false }

    # 先收集该工作区的 sessionId，用于清理全局数据
    $ids = @()
    $sf = Join-Path $dir 'sessions.json'
    if (Test-Path $sf) {
        try {
            $arr = Get-Content $sf -Raw -Encoding UTF8 | ConvertFrom-Json
            foreach ($s in @($arr)) { if ($s -and $s.sessionId) { $ids += $s.sessionId } }
        } catch {}
    }

    try { Remove-Item -LiteralPath $dir -Recurse -Force -ErrorAction Stop }
    catch {
        Write-Host ("删除工作区目录失败: {0}" -f $_.Exception.Message) -ForegroundColor Red
        Write-Host '可能是 Kiro 正在运行占用了文件，请先完全关闭 Kiro 再重试。' -ForegroundColor Red
        return $false
    }

    # 清理全局 sessions\sessions.json 中属于该工作区的条目
    $gdir = Join-Path $base 'sessions'
    $gIndex = Join-Path $gdir 'sessions.json'
    if (Test-Path $gIndex) {
        try {
            $g = Get-Content $gIndex -Raw -Encoding UTF8 | ConvertFrom-Json
            $keep = @($g) | Where-Object { ($ids -notcontains $_.sessionId) -and ($_.workspaceDirectory -ne $item.Path) }
            $parts = @($keep | ForEach-Object { $_ | ConvertTo-Json -Depth 20 -Compress })
            $out = '[' + ($parts -join ',') + ']'
            Set-Content -LiteralPath $gIndex -Value $out -Encoding UTF8
        } catch {}
    }
    # 删除全局会话副本与差异记录
    $ddir = Join-Path $base '.diffs'
    foreach ($id in $ids) {
        $gf = Join-Path $gdir ($id + '.json')
        if (Test-Path $gf) { Remove-Item -LiteralPath $gf -Force -ErrorAction SilentlyContinue }
        $df = Join-Path $ddir $id
        if (Test-Path $df) { Remove-Item -LiteralPath $df -Recurse -Force -ErrorAction SilentlyContinue }
    }
    Write-Host ("已删除该工作区的全部 Kiro 历史(含 {0} 段会话的全局副本)。" -f $ids.Count) -ForegroundColor Green
    return $true
}

# ===== 主流程 =====
Show-Info
$items = Get-Items
Show-List $items

while ($true) {
    Write-Host ''
    Write-Host '------------------------------------------------------------' -ForegroundColor DarkCyan
    Write-Host '请选择操作:' -ForegroundColor Yellow
    Write-Host '  输入数字  -> 用 Kiro 打开对应编号的工作区'
    Write-Host '  D 数字    -> 彻底删除对应编号工作区的 Kiro 历史(需输入 YES 确认)'
    Write-Host '  O         -> 打开 Kiro 历史记录文件夹'
    Write-Host '  L         -> 重新显示列表'
    Write-Host '  Q         -> 退出'
    $sel = Read-Host '你的选择'
    $sel = $sel.Trim()

    if ($sel -match '^[Qq]$' -or $sel -eq '') { break }
    elseif ($sel -match '^[Oo]$') {
        if (Test-Path $base) { Start-Process explorer.exe $base; Write-Host '已打开历史记录文件夹。' -ForegroundColor Green }
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
            if (-not $kiro) { Write-Host '未找到 Kiro 程序，无法自动打开。请手动启动 Kiro 后用"打开文件夹"。' -ForegroundColor Red }
            elseif ($target -like '<*') { Write-Host '该工作区路径无法解码，无法打开。' -ForegroundColor Red }
            elseif (-not (Test-Path $target)) { Write-Host ("路径已不存在: {0}" -f $target) -ForegroundColor Red }
            else {
                Write-Host ("正在用 Kiro 打开: {0}" -f $target) -ForegroundColor Green
                # 用 cmd 的 start 拉起，让 Kiro 脱离本窗口的进程树/Job；
                # 否则点窗口的 X 关闭本工具时，Windows 会把同一 Job 里的 Kiro 一起杀掉。
                Start-Process -FilePath $env:ComSpec -ArgumentList ('/c start "" "{0}" "{1}"' -f $kiro, $target) -WindowStyle Hidden
            }
        } else { Write-Host ("编号超出范围(1-{0})。" -f $items.Count) -ForegroundColor Red }
    }
    else { Write-Host '无效输入。' -ForegroundColor Red }
}