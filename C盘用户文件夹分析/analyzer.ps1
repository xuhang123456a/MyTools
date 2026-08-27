<#
.SYNOPSIS
    Windows 用户目录点号文件夹深度分析与瘦身报告生成器 (原生 PowerShell 免环境版)
.DESCRIPTION
    0 依赖，直接在任意 Windows 10/11 机器上运行。
    扫描用户目录下的所有点号文件夹，统计大小、分析归属软件、检测软链接状态并生成 Markdown 报告。
#>
param (
    [string]$ScanPath = $env:USERPROFILE,
    [string]$TargetDrive = "D:"
)

[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8

# 内置知识库
$KB = @{
    ".gemini" = @{ App = "Google Antigravity / Gemini CLI"; Category = "AI 编程智能体"; Desc = "Antigravity 智能体核心工作空间，存放会话上下文、项目记忆、系统配置及多账号认证。"; Risk = "🔴 严禁删除"; RiskLevel = "CRITICAL"; CanSymlink = $true; Advice = "删除将导致当前正在对话的 Antigravity 丢失所有项目记忆、上下文历史和配置。" }
    ".antigravity_tools" = @{ App = "Antigravity Tools 辅助增强工具"; Category = "AI 辅助工具"; Desc = "Antigravity 多账号管理、代理分流配置及 Token 消耗监控数据库。"; Risk = "🟡 谨慎保留"; RiskLevel = "CAUTION"; CanSymlink = $false; Advice = "存放账号切换配置与代理设置，建议保留。" }
    ".claude" = @{ App = "Anthropic Claude Code (官方 CLI Agent)"; Category = "AI 编程智能体"; Desc = "Claude 命令行开发工具的登录凭证 (.credentials.json)、CLAUDE.md、会话与项目历史。"; Risk = "🟡 谨慎保留"; RiskLevel = "CAUTION"; CanSymlink = $true; Advice = "删除后再次使用 Claude Code CLI 需要重新进行网页登录授权。" }
    ".codex" = @{ App = "OpenAI Codex / Codex 客户端"; Category = "AI 编程智能体"; Desc = "Codex 执行沙盒环境 (.sandbox)、全局状态快照与环境配置。"; Risk = "🟡 可清理沙盒"; RiskLevel = "CAUTION"; CanSymlink = $true; Advice = "若体积过大，可清理其中的 .sandbox 缓存目录或使用软链接迁移至其他盘。" }
    ".codex-session-delete" = @{ App = "Codex++ (Codex 增强加载器/主题补丁)"; Category = "AI 辅助工具"; Desc = "Codex++ 启动器日志 (codex-plus.log)、Dream-Skin 皮肤备份与会话清理配置。"; Risk = "🟢 可安全清理"; RiskLevel = "SAFE_CACHE"; CanSymlink = $false; Advice = "主要为主题皮肤备份与历史运行日志，可安全清空或删除。" }
    ".kiro" = @{ App = "Kiro AI IDE / Agent 客户端"; Category = "AI 编程智能体"; Desc = "Kiro AI 编程环境，包含 Powers 技能包、扩展插件、历史会话与上下文索引。"; Risk = "🟡 按需保留"; RiskLevel = "CAUTION"; CanSymlink = $true; Advice = "若不再使用 Kiro 可直接删除；若仍在使用且体积巨大（>1GB），推荐软链接迁移。" }
    ".qoder" = @{ App = "Qoder (腾讯云 AI 研发助手桌面端)"; Category = "AI 编程智能体"; Desc = "Qoder IDE 核心主目录，包含安装插件、代码画布 (Canvas)、MCP 服务与会话环境。"; Risk = "🟡 按需保留"; RiskLevel = "CAUTION"; CanSymlink = $true; Advice = "若经常使用 Qoder 建议保留或软链接；若已弃用可直接删除释放空间。" }
    ".qoder-cn" = @{ App = "Qoder 国内独立版实例"; Category = "AI 编程智能体"; Desc = "Qoder 国内版独立实例产生的扩展与配置缓存。"; Risk = "🟡 按需保留"; RiskLevel = "CAUTION"; CanSymlink = $true; Advice = "若仅使用主版 Qoder，可清理该独立版残留。" }
    ".workbuddy" = @{ App = "WorkBuddy (腾讯企业级 AI Agent 平台)"; Category = "AI 编程智能体"; Desc = "WorkBuddy 客户端核心存储，内含 SQLite 数据库、MCP 代理、iOA 认证缓存与会话记录。"; Risk = "🟡 谨慎保留"; RiskLevel = "CAUTION"; CanSymlink = $true; Advice = "企业日常使用不可删除；若已卸载该软件可直接清除释放空间。" }
    ".workbuddy-key-fallback" = @{ App = "WorkBuddy 密钥降级目录"; Category = "AI 辅助工具"; Desc = "WorkBuddy 连接器 API Key 备用降级目录。"; Risk = "🟡 随主程序保留"; RiskLevel = "CAUTION"; CanSymlink = $false; Advice = "体积极小，建议随 WorkBuddy 主程序一同保留。" }
    ".copilot" = @{ App = "GitHub Copilot CLI / 扩展"; Category = "AI 辅助工具"; Desc = "GitHub Copilot 全局配置、IDE 联机缓存与 MCP 服务配置 (mcp-config.json)。"; Risk = "🟡 建议保留"; RiskLevel = "CAUTION"; CanSymlink = $false; Advice = "存储 Copilot 全局设置，建议保留。" }
    ".cline" = @{ App = "Cline (VS Code 自主 AI 编程插件)"; Category = "AI 辅助工具"; Desc = "Cline 插件的本地历史工作数据与任务快照。"; Risk = "🟢 可安全清理"; RiskLevel = "SAFE_CACHE"; CanSymlink = $false; Advice = "存放任务历史，插件运行时会自动按需重建。" }
    ".roo-cline" = @{ App = "Roo Cline (Roo Code AI 插件)"; Category = "AI 辅助工具"; Desc = "Roo Code (Cline 分支) 插件的任务数据与本地配置。"; Risk = "🟢 可安全清理"; RiskLevel = "SAFE_CACHE"; CanSymlink = $false; Advice = "存放会话与任务快照。" }
    ".cursor" = @{ App = "Cursor AI IDE"; Category = "AI 编程智能体"; Desc = "Cursor 编辑器的用户配置、扩展、索引缓存与历史会话。"; Risk = "🟡 建议保留"; RiskLevel = "CAUTION"; CanSymlink = $true; Advice = "若使用 Cursor 则需保留，插件多时可通过软链接迁移至其他盘。" }
    ".windsurf" = @{ App = "Windsurf (Codeium AI IDE)"; Category = "AI 编程智能体"; Desc = "Windsurf IDE 的用户级数据、Cortex 记忆模型与扩展插件。"; Risk = "🟡 建议保留"; RiskLevel = "CAUTION"; CanSymlink = $true; Advice = "若使用 Windsurf 请保留，支持软链接迁移。" }
    ".trae" = @{ App = "Trae (字节跳动 AI IDE)"; Category = "AI 编程智能体"; Desc = "Trae IDE 的用户配置、插件扩展与工作流状态。"; Risk = "🟡 建议保留"; RiskLevel = "CAUTION"; CanSymlink = $true; Advice = "使用 Trae 时请保留。" }
    ".supermaven" = @{ App = "Supermaven (极速代码补全插件)"; Category = "AI 辅助工具"; Desc = "Supermaven 激活状态与本地配置 (config.json)。"; Risk = "🟡 建议保留"; RiskLevel = "CAUTION"; CanSymlink = $false; Advice = "删除后需要在编辑器中重新输入 Activation Token。" }
    ".cc-switch" = @{ App = "CC-Switch (AI 助手多账号切换器)"; Category = "AI 辅助工具"; Desc = "用于在 Claude Code / Codex / Copilot 间多账号一键轮换的凭据数据库与配置。"; Risk = "🟡 建议保留"; RiskLevel = "CAUTION"; CanSymlink = $false; Advice = "保存了多个绑定的 OAuth 登录 Token，删除后需重新绑定各平台账号。" }
    ".semantic_search" = @{ App = "本地代码语义检索模块"; Category = "AI 辅助工具"; Desc = "存放本地代码语义检索专用的向量嵌入模型文件 (models/)。"; Risk = "🟢 可重建缓存"; RiskLevel = "SAFE_CACHE"; CanSymlink = $true; Advice = "删除后相关 AI 工具在首次进行代码库语义搜索时会自动重新下载。" }
    ".cliguard" = @{ App = "CLI Guard (终端高危指令安全守护)"; Category = "终端安全守护"; Desc = "终端命令执行安全拦截与权限守护进程，监控高危 CLI 指令执行。"; Risk = "🔴 严禁删除"; RiskLevel = "CRITICAL"; CanSymlink = $false; Advice = "企业安全基线守护进程相关文件，切勿随意删除。" }
    ".ollama" = @{ App = "Ollama 本地大模型运行框架"; Category = "AI 模型框架"; Desc = "Ollama 本地运行环境，默认存储下载的所有本地开源大模型文件 (models/)。"; Risk = "🟢 模型可软链接"; RiskLevel = "CAUTION"; CanSymlink = $true; Advice = "通常体积巨大（数 GB 至数十 GB），强烈推荐使用软链接迁移到大容量数据盘！" }
    ".huggingface" = @{ App = "Hugging Face Hub CLI / Transformers"; Category = "AI 模型框架"; Desc = "Hugging Face 登录凭证 (token) 与本地模型元数据缓存。"; Risk = "🟢 缓存可清理"; RiskLevel = "SAFE_CACHE"; CanSymlink = $true; Advice = "保存了 HF 登录 Token 与模型下载缓存，可迁移或清理。" }
    ".vscode" = @{ App = "Visual Studio Code"; Category = "开发工具 / IDE"; Desc = "VS Code 全局插件安装目录 (extensions/) 与命令行工具。"; Risk = "🔴 核心插件库"; RiskLevel = "CRITICAL"; CanSymlink = $true; Advice = "直接删除会导致 VS Code 所有已安装插件丢失！若体积过大强烈推荐使用软链接整体迁移到其他盘。" }
    ".vscode-insiders" = @{ App = "VS Code Insiders (预览版)"; Category = "开发工具 / IDE"; Desc = "VS Code Insiders 预览版扩展与 CLI 运行环境。"; Risk = "🔴 核心插件库"; RiskLevel = "CRITICAL"; CanSymlink = $true; Advice = "Insiders 版插件目录，推荐软链接迁移。" }
    ".vscode-shared" = @{ App = "VS Code / 派生 IDE 共享存储"; Category = "开发工具 / IDE"; Desc = "VS Code 及其派生版本间共享的持久化键值存储 (sharedStorage)。"; Risk = "🟢 可安全清理"; RiskLevel = "SAFE_CACHE"; CanSymlink = $false; Advice = "临时共享存储，删除后软件会自动重建。" }
    ".android" = @{ App = "Android Studio / Android SDK"; Category = "移动开发 SDK"; Desc = "Android 开发者调试证书 (debug.keystore)、ADB 授权公私钥 (adbkey) 与 AVD 模拟器硬件配置。"; Risk = "🔴 建议保留"; RiskLevel = "CRITICAL"; CanSymlink = $true; Advice = "删除后每次连接真机调试都需要重新在手机上弹窗授权确认。" }
    ".ld9virtualbox" = @{ App = "雷电模拟器 9 (LDPlayer 9)"; Category = "安卓模拟器 / 虚拟机"; Desc = "雷电模拟器后台 VirtualBox 虚拟化底层服务的运行日志文件 (VBoxSVC.log.1~10)。"; Risk = "🟢 可安全删除"; RiskLevel = "SAFE_CACHE"; CanSymlink = $false; Advice = "全部为历史运行日志，模拟器启动时会自动生成新日志，可随意清空。" }
    ".dlv" = @{ App = "Delve (Go 语言官方调试器)"; Category = "编程调试工具"; Desc = "Go 语言调试器 dlv 的个性化配置文件 (config.yml)。"; Risk = "🟢 建议保留"; RiskLevel = "SAFE_CACHE"; CanSymlink = $false; Advice = "体积极小，存储 Go 调试参数配置。" }
    ".gradle" = @{ App = "Gradle (Java/Android 构建工具)"; Category = "包管理 / 构建工具"; Desc = "全局 Gradle 依赖缓存，存放 Maven/Google 源下载的 jar/aar 包、Wrapper 发行包与 Daemon 守护日志。"; Risk = "🟢 可安全清空"; RiskLevel = "SAFE_CACHE"; CanSymlink = $true; Advice = "全为下载缓存！删除可瞬间释放数 GB 空间。强烈推荐使用软链接迁移到其他盘！" }
    ".m2" = @{ App = "Apache Maven"; Category = "包管理 / 构建工具"; Desc = "Maven 本地仓库 (repository/)，存放 Java 项目下载的所有第三方依赖 jar 包。"; Risk = "🟢 依赖缓存"; RiskLevel = "SAFE_CACHE"; CanSymlink = $true; Advice = "全为构建依赖，可安全删除或推荐软链接迁移至其他盘。" }
    ".nuget" = @{ App = "Microsoft NuGet (.NET 包管理器)"; Category = "包管理 / 构建工具"; Desc = ".NET / C# 全局包缓存目录 (packages/)，存放 dotnet restore 下载的 NuGet 包。"; Risk = "🟢 可安全清空"; RiskLevel = "SAFE_CACHE"; CanSymlink = $true; Advice = "可使用 `dotnet nuget locals all --clear` 或直接删除释放数 GB 空间，项目编译时会自动重新拉取。" }
    ".dotnet" = @{ App = "Microsoft .NET SDK"; Category = "语言 SDK / 运行时"; Desc = ".NET SDK 首次运行标记 (Sentinel)、遥测数据 (Telemetry) 与 Workload 清单。"; Risk = "🟡 建议保留"; RiskLevel = "CAUTION"; CanSymlink = $false; Advice = "体积微小，属于 .NET SDK 运行状态标记。" }
    ".cargo" = @{ App = "Rust Cargo 包管理器"; Category = "包管理 / 构建工具"; Desc = "Rust Crates 下载缓存 (registry/)、Git 源码依赖与全局安装的 Cargo 二进制程序 (bin/)。"; Risk = "🟢 缓存可迁移"; RiskLevel = "SAFE_CACHE"; CanSymlink = $true; Advice = "通常体积巨大（数 GB），强烈建议通过环境变量 CARGO_HOME 或软链接迁移到大容量盘。" }
    ".rustup" = @{ App = "Rustup (Rust 工具链安装器)"; Category = "语言 SDK / 工具链"; Desc = "存放安装的 Rust 编译器工具链 (toolchains/) 与目标架构库。"; Risk = "🔴 核心工具链"; RiskLevel = "CRITICAL"; CanSymlink = $true; Advice = "属于 Rust 编译器核心本体，删除将导致 rustc/cargo 无法运行，推荐软链接整体迁移。" }
    ".bundle" = @{ App = "Ruby Bundler"; Category = "包管理 / 构建工具"; Desc = "Ruby 语言依赖包管理器 Bundler 的全局 gem 下载缓存。"; Risk = "🟢 可安全清理"; RiskLevel = "SAFE_CACHE"; CanSymlink = $false; Advice = "若不开发 Ruby 项目可安全删除释放空间。" }
    ".npm" = @{ App = "Node.js npm 包管理器"; Category = "包管理 / 构建工具"; Desc = "npm 下载的 tarball 模块包缓存 (_cacache/)。"; Risk = "🟢 可安全清空"; RiskLevel = "SAFE_CACHE"; CanSymlink = $true; Advice = "可运行 `npm cache clean --force` 或直接删除，不影响已有项目运行。" }
    ".yarn" = @{ App = "Yarn 包管理器"; Category = "包管理 / 构建工具"; Desc = "Yarn 全局离线镜像与依赖缓存。"; Risk = "🟢 可安全清理"; RiskLevel = "SAFE_CACHE"; CanSymlink = $true; Advice = "可安全清空释放空间。" }
    ".pnpm-store" = @{ App = "pnpm 包管理器"; Category = "包管理 / 构建工具"; Desc = "pnpm 全局硬链接依赖内容寻址库 (Content-addressable store)。"; Risk = "🟢 建议软链接"; RiskLevel = "SAFE_CACHE"; CanSymlink = $true; Advice = "体积较大，推荐软链接迁移至开发数据盘。" }
    ".ssh" = @{ App = "OpenSSH 客户端"; Category = "系统安全 / 远程凭证"; Desc = "极度重要的 SSH 密钥库！包含 Git / Linux 服务器连接私钥 (id_rsa)、公钥及服务器指纹 (known_hosts)。"; Risk = "🚨 绝对禁止随意删除"; RiskLevel = "CRITICAL"; CanSymlink = $false; Advice = "删除将导致所有配置了 SSH 密钥的 GitHub/GitLab 仓库无法推送，所有远程服务器连接鉴权失败！" }
    ".aws" = @{ App = "Amazon AWS CLI / SDK"; Category = "云服务 CLI"; Desc = "AWS 命令行工具的凭据文件 (credentials)、配置文件 (config) 及 SSO 登录会话缓存。"; Risk = "🟡 建议保留"; RiskLevel = "CAUTION"; CanSymlink = $false; Advice = "保存了 AWS 访问密钥或 SSO 登录会话，删除后需重新 `aws configure`。" }
    ".azure" = @{ App = "Microsoft Azure CLI"; Category = "云服务 CLI"; Desc = "Azure CLI 登录 Token 与订阅配置缓存。"; Risk = "🟡 建议保留"; RiskLevel = "CAUTION"; CanSymlink = $false; Advice = "删除后需重新 `az login`。" }
    ".kube" = @{ App = "Kubernetes (kubectl)"; Category = "容器编排 / 集群配置"; Desc = "Kubernetes 集群连接配置 (config)，包含集群 API 地址与访问证书。"; Risk = "🔴 严禁删除"; RiskLevel = "CRITICAL"; CanSymlink = $false; Advice = "删除将导致 kubectl 无法连接任何 K8s 集群。" }
    ".docker" = @{ App = "Docker Desktop / Docker CLI"; Category = "容器工具"; Desc = "Docker Hub 登录凭证、上下文配置与构建器缓存状态。"; Risk = "🟡 建议保留"; RiskLevel = "CAUTION"; CanSymlink = $false; Advice = "保存了镜像仓库登录凭证与 Docker 环境配置。" }
    ".cache" = @{ App = "Linux/XDG 规范通用缓存目录"; Category = "XDG 标准缓存"; Desc = "各种跨平台工具（如 Codex 运行时、Gem、OpenCode、pip、ripgrep 等）存放的临时下载与编译缓存。"; Risk = "🟢 可重点瘦身"; RiskLevel = "SAFE_CACHE"; CanSymlink = $true; Advice = "属于标准缓存目录，可定期清理其内部的子目录（如 codex-runtimes）腾出巨大空间。" }
    ".config" = @{ App = "Linux/XDG 规范通用配置目录"; Category = "XDG 标准配置"; Desc = "跨平台工具（如 Git、OpenCode、GitHub CLI、Gem 等）的标准配置文件存放目录。"; Risk = "🟡 建议保留"; RiskLevel = "CAUTION"; CanSymlink = $true; Advice = "存放软件配置而非体积文件，体积一般不大，建议保留。" }
    ".local" = @{ App = "Linux/XDG 规范用户级软件与数据"; Category = "XDG 标准本地程序"; Desc = "存放用户级独立安装的命令行工具 (bin/ 内有 uv、kiro-cli、python 等) 及 share/ 应用程序数据。"; Risk = "🟡 谨慎操作"; RiskLevel = "CAUTION"; CanSymlink = $true; Advice = "包含独立的 Python/CLI 可执行程序，若删除可能导致终端命令失效。" }
}

Write-Host "`n================================================================================" -ForegroundColor Cyan
Write-Host "🚀 Windows 用户目录点号文件夹智能分析引擎 (PowerShell 原生免配置版)" -ForegroundColor Green
Write-Host "📁 扫描目标路径: $ScanPath" -ForegroundColor Yellow
Write-Host "🕒 开始时间: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')" -ForegroundColor Gray
Write-Host "================================================================================`n" -ForegroundColor Cyan

if (-not (Test-Path $ScanPath)) {
    Write-Error "❌ 目标路径不存在: $ScanPath"
    exit 1
}

$dotDirs = Get-ChildItem -Path $ScanPath -Directory -Force -ErrorAction SilentlyContinue | Where-Object { $_.Name.StartsWith(".") } | Sort-Object Name
Write-Host "🔍 发现 $($dotDirs.Count) 个点号文件夹，正在统计分析..." -ForegroundColor Cyan

$analyzedItems = [System.Collections.Generic.List[PSCustomObject]]::new()

foreach ($dir in $dotDirs) {
    Write-Host "  正在扫描: $($dir.Name)..." -NoNewline
    
    # 统计大小与文件数
    $measure = Get-ChildItem -Path $dir.FullName -Recurse -File -Force -ErrorAction SilentlyContinue | Measure-Object -Property Length -Sum
    $fileCount = if ($measure.Count) { $measure.Count } else { 0 }
    $sizeBytes = if ($measure.Sum) { $measure.Sum } else { 0 }
    $sizeMB = [math]::Round(($sizeBytes / 1MB), 2)
    
    # 检测软链接
    $itemObj = Get-Item -Path $dir.FullName -Force -ErrorAction SilentlyContinue
    $isLink = [bool]$itemObj.LinkType
    $linkTarget = if ($isLink) { $itemObj.Target -join '; ' } else { "" }

    # 识别软件归属
    $key = $dir.Name.ToLower()
    if ($KB.ContainsKey($key)) {
        $info = $KB[$key]
    } else {
        # 启发式识别
        if ($key -match "venv|env") {
            $info = @{ App = "Python 虚拟环境 ($($dir.Name))"; Category = "Python 开发环境"; Desc = "项目专属 Python 虚拟环境与依赖包。"; Risk = "🟢 按需删除"; RiskLevel = "SAFE_CACHE"; CanSymlink = $true; Advice = "对应项目不再开发时可删除。" }
        } elseif ($key -eq ".git") {
            $info = @{ App = "Git 版本库元数据"; Category = "版本控制"; Desc = "Git 仓库核心版本库，包含提交历史与分支指针。"; Risk = "🔴 严禁删除"; RiskLevel = "CRITICAL"; CanSymlink = $false; Advice = "删除将丢失本地未推送的版本历史。" }
        } elseif ($key -match "log") {
            $info = @{ App = "日志目录 ($($dir.Name))"; Category = "运行日志"; Desc = "应用程序输出的诊断日志文件。"; Risk = "🟢 可安全清理"; RiskLevel = "SAFE_CACHE"; CanSymlink = $false; Advice = "无排查需求时可清空。" }
        } else {
            $info = @{ App = "未知工具 ($($dir.Name))"; Category = "其他配置/缓存"; Desc = "第三方工具或自定义环境生成的配置文件。"; Risk = "🟡 建议保留"; RiskLevel = "CAUTION"; CanSymlink = $true; Advice = "建议保留或先重命名观察。" }
        }
    }

    Write-Host " 完成! ($sizeMB MB)" -ForegroundColor Gray

    $analyzedItems.Add([PSCustomObject]@{
        Name = $dir.Name
        Path = $dir.FullName
        SizeBytes = [double]$sizeBytes
        SizeMB = [double]$sizeMB
        FileCount = [int]$fileCount
        IsLink = $isLink
        LinkTarget = $linkTarget
        App = $info.App
        Category = $info.Category
        Desc = $info.Desc
        Risk = $info.Risk
        RiskLevel = $info.RiskLevel
        CanSymlink = $info.CanSymlink
        Advice = $info.Advice
    })
}

# 排序
$sortedItems = $analyzedItems | Sort-Object SizeBytes -Descending

# 打印控制台表格
Write-Host "`n"
$sortedItems | Select-Object @{Name="文件夹名称";Expression={if($_.IsLink){"$($_.Name) (🔗已链接)"}else{$_.Name}}}, @{Name="体积(MB)";Expression={$_.SizeMB}}, @{Name="文件数";Expression={$_.FileCount}}, @{Name="所属软件 / 工具";Expression={$_.App}}, @{Name="安全度";Expression={$_.Risk}} | Format-Table -AutoSize

$totalBytes = ($sortedItems | Measure-Object -Property SizeBytes -Sum).Sum
$totalMB = [math]::Round(($totalBytes / 1MB), 2)
$totalGB = [math]::Round(($totalBytes / 1GB), 2)
$totalFiles = ($sortedItems | Measure-Object -Property FileCount -Sum).Sum

Write-Host "--------------------------------------------------------------------------------" -ForegroundColor Gray
Write-Host "📊 总计: $($sortedItems.Count) 个文件夹 | 总大小: $totalGB GB ($totalMB MB) | 总文件数: $totalFiles 个`n" -ForegroundColor Green

# 生成 Markdown 报告
$timestampStr = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
$fileTimestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$username = Split-Path $ScanPath -Leaf
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$outputDir = Join-Path $scriptDir "reports"
if (-not (Test-Path $outputDir)) { New-Item -ItemType Directory -Path $outputDir -Force | Out-Null }

$reportFile = Join-Path $outputDir "用户目录点号文件夹全面解析报告_${username}_${fileTimestamp}.md"
$standardFile = Join-Path $outputDir "用户目录点号文件夹全面解析报告_最新.md"

$sb = [System.Text.StringBuilder]::new()
[void]$sb.AppendLine(("# Windows 用户目录（{0}）点号文件夹全面解析报告`n" -f $ScanPath))
[void]$sb.AppendLine(("> **生成时间**：{0}  " -f $timestampStr))
[void]$sb.AppendLine(("> **分析路径**：`{0}`  " -f $ScanPath))
[void]$sb.AppendLine(("> **当前用户**：`{0}`  " -f $username))
[void]$sb.AppendLine(("> **统计对象**：以 `.`（点号）开头的系统/开发/AI隐藏配置与缓存文件夹（共计 {0} 个）`n" -f $sortedItems.Count))
[void]$sb.AppendLine("---`n")

[void]$sb.AppendLine("## 📊 一、 核心统计与空间分布`n")
[void]$sb.AppendLine(("* **点号文件夹总数**：`{0}` 个" -f $sortedItems.Count))
[void]$sb.AppendLine(("* **总磁盘空间占用**：**`{0:N2} GB`** (`{1:N2} MB`)" -f $totalGB, $totalMB))
[void]$sb.AppendLine(("* **文件总数**：`{0:N0}` 个`n" -f $totalFiles))

[void]$sb.AppendLine("### 🏆 磁盘占用 TOP 5 文件夹")
$top5 = $sortedItems | Select-Object -First 5
$rank = 1
foreach ($t in $top5) {
    $linkStr = if ($t.IsLink) { " *(🔗 当前为软链接)*" } else { "" }
    $topLine = "{0}. **`{1}`** —— **`{2:N2} MB`** ({3}){4}" -f $rank, $t.Name, $t.SizeMB, $t.App, $linkStr
    [void]$sb.AppendLine($topLine)
    $rank++
}
[void]$sb.AppendLine("`n---`n")

[void]$sb.AppendLine("## 🗂️ 二、 分类详细解析表`n")
$grouped = $sortedItems | Group-Object Category
foreach ($g in $grouped) {
    $catMB = [math]::Round((($g.Group | Measure-Object -Property SizeBytes -Sum).Sum / 1MB), 2)
    [void]$sb.AppendLine(("### 📁 {0}（共 {1} 个，合计 `{2:N2} MB`）`n" -f $g.Name, $g.Count, $catMB))
    [void]$sb.AppendLine("| 文件夹名称 | 体积大小 | 产生软件 / 组件 | 功能作用与存储内容 | 清理建议与风险判定 |")
    [void]$sb.AppendLine("| :--- | :--- | :--- | :--- | :--- |")
    foreach ($item in $g.Group) {
        $linkNote = if ($item.IsLink) { "<br>*(🔗 链接指向: ``{0}``)*" -f $item.LinkTarget } else { "" }
        $descFmt = $item.Desc.Replace("`n", "<br>")
        $advFmt = $item.Advice.Replace("`n", "<br>")
        $row = "| **`{0}`**{1} | **{2:N2} MB**<br>({3} 个文件) | **{4}** | {5} | **{6}**<br>{7} |" -f $item.Name, $linkNote, $item.SizeMB, $item.FileCount, $item.App, $descFmt, $item.Risk, $advFmt
        [void]$sb.AppendLine($row)
    }
    [void]$sb.AppendLine("")
}

[void]$sb.AppendLine("---`n")
[void]$sb.AppendLine("## 🧹 三、 C 盘空间瘦身与软链接无痛迁移方案`n")

$safeItems = $sortedItems | Where-Object { $_.RiskLevel -eq "SAFE_CACHE" -and $_.SizeMB -gt 10 -and -not $_.IsLink }
if ($safeItems) {
    $safeMB = [math]::Round((($safeItems | Measure-Object -Property SizeBytes -Sum).Sum / 1MB), 2)
    [void]$sb.AppendLine(("### 1. 🟢 零风险直接释放区（预计可直接释放约 `{0:N2} MB`）" -f $safeMB))
    [void]$sb.AppendLine("以下文件夹仅存放下载缓存、构建中间件或历史日志，清空后软件在需要时会自动重新拉取，不影响配置：`n")
    foreach ($s in $safeItems) {
        $cleanLine = "* **`{0}`** (`{1:N2} MB`)：{2}" -f $s.Name, $s.SizeMB, $s.Advice
        [void]$sb.AppendLine($cleanLine)
    }
    [void]$sb.AppendLine("")
}

$bigItems = $sortedItems | Where-Object { $_.SizeMB -ge 300 -and -not $_.IsLink -and $_.CanSymlink }
if ($bigItems) {
    [void]$sb.AppendLine("### 2. 🚀 推荐软链接迁移区（体积大于 300MB 的文件夹）")
    [void]$sb.AppendLine(("这些文件夹体积庞大（例如依赖库、IDE 插件或模型），直接删除会导致软件无法工作，但可以使用 **Windows Junction 软链接** 将其无感迁移到数据盘（如 `{0}` 盘）：`n" -f $TargetDrive))
    [void]$sb.AppendLine('```cmd')
    [void]$sb.AppendLine(":: ========================================================================")
    [void]$sb.AppendLine((":: 一键软链接迁移脚本（以迁移至 {0}\UserLinks 为例）" -f $TargetDrive))
    [void]$sb.AppendLine(":: 注意：迁移前请确保对应的开发工具/软件已经完全退出！")
    [void]$sb.AppendLine(":: ========================================================================`n")
    [void]$sb.AppendLine(("mkdir `"{0}\UserLinks`" 2>nul`n" -f $TargetDrive))
    foreach ($b in $bigItems) {
        [void]$sb.AppendLine((":: --- 迁移 {0} ({1:N2} MB) ---" -f $b.Name, $b.SizeMB))
        [void]$sb.AppendLine(("move `"{0}`" `"{1}\UserLinks\{2}`"" -f $b.Path, $TargetDrive, $b.Name))
        [void]$sb.AppendLine(("mklink /J `"{0}`" `"{1}\UserLinks\{2}`"`n" -f $b.Path, $TargetDrive, $b.Name))
    }
    [void]$sb.AppendLine('```')
    [void]$sb.AppendLine("")
}

[void]$sb.AppendLine("### 3. 🔴 严禁触碰的红线区")
[void]$sb.AppendLine("* **`.ssh`**：存放 Git / 服务器 SSH 登录私钥，删除将导致无法推送代码或连接服务器！")
[void]$sb.AppendLine("* **`.gemini`**：当前对话与 Antigravity 智能体环境的核心上下文与记忆数据。")
[void]$sb.AppendLine("* **`.vscode`**：直接删除会导致 VS Code 所有已安装插件丢失。")
[void]$sb.AppendLine("* **`.android`**：存放真机调试证书与模拟器硬件配置。`n")

[System.IO.File]::WriteAllText($reportFile, $sb.ToString(), [System.Text.Encoding]::UTF8)
[System.IO.File]::WriteAllText($standardFile, $sb.ToString(), [System.Text.Encoding]::UTF8)

Write-Host "✅ 分析报告已生成: $reportFile" -ForegroundColor Green
Write-Host "📄 最新报告已同步: $standardFile`n" -ForegroundColor Green
