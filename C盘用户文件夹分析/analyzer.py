import os
import sys
import json
import time
import argparse
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor

# Set UTF-8 encoding for stdout/stderr
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8')

# Built-in Knowledge Base of Known Dot-Folders
KNOWLEDGE_BASE = {
    # AI 智能编程与智能体
    ".gemini": {
        "app": "Google Antigravity / Gemini CLI",
        "category": "AI 编程智能体",
        "desc": "Antigravity 智能体核心工作空间，存放会话上下文、项目记忆、系统配置及多账号认证。",
        "risk": "🔴 严禁删除",
        "risk_level": "CRITICAL",
        "can_symlink": True,
        "advice": "删除将导致当前正在对话的 Antigravity 丢失所有项目记忆、上下文历史和配置。"
    },
    ".antigravity_tools": {
        "app": "Antigravity Tools 辅助增强工具",
        "category": "AI 辅助工具",
        "desc": "Antigravity 多账号管理、代理分流配置及 Token 消耗监控数据库。",
        "risk": "🟡 谨慎保留",
        "risk_level": "CAUTION",
        "can_symlink": False,
        "advice": "存放账号切换配置与代理设置，建议保留。"
    },
    ".claude": {
        "app": "Anthropic Claude Code (官方 CLI Agent)",
        "category": "AI 编程智能体",
        "desc": "Claude 命令行开发工具的登录凭证 (.credentials.json)、CLAUDE.md、会话与项目历史。",
        "risk": "🟡 谨慎保留",
        "risk_level": "CAUTION",
        "can_symlink": True,
        "advice": "删除后再次使用 Claude Code CLI 需要重新进行网页登录授权。"
    },
    ".codex": {
        "app": "OpenAI Codex / Codex 客户端",
        "category": "AI 编程智能体",
        "desc": "Codex 执行沙盒环境 (.sandbox)、全局状态快照与环境配置。",
        "risk": "🟡 可清理沙盒",
        "risk_level": "CAUTION",
        "can_symlink": True,
        "advice": "若体积过大，可清理其中的 .sandbox 缓存目录或使用软链接迁移至其他盘。"
    },
    ".codex-session-delete": {
        "app": "Codex++ (Codex 增强加载器/主题补丁)",
        "category": "AI 辅助工具",
        "desc": "Codex++ 启动器日志 (codex-plus.log)、Dream-Skin 皮肤备份与会话清理配置。",
        "risk": "🟢 可安全清理",
        "risk_level": "SAFE_CACHE",
        "can_symlink": False,
        "advice": "主要为主题皮肤备份与历史运行日志，可安全清空或删除。"
    },
    ".kiro": {
        "app": "Kiro AI IDE / Agent 客户端",
        "category": "AI 编程智能体",
        "desc": "Kiro AI 编程环境，包含 Powers 技能包、扩展插件、历史会话与上下文索引。",
        "risk": "🟡 按需保留",
        "risk_level": "CAUTION",
        "can_symlink": True,
        "advice": "若不再使用 Kiro 可直接删除；若仍在使用且体积巨大（>1GB），推荐软链接迁移。"
    },
    ".qoder": {
        "app": "Qoder (腾讯云 AI 研发助手桌面端)",
        "category": "AI 编程智能体",
        "desc": "Qoder IDE 核心主目录，包含安装插件、代码画布 (Canvas)、MCP 服务与会话环境。",
        "risk": "🟡 按需保留",
        "risk_level": "CAUTION",
        "can_symlink": True,
        "advice": "若经常使用 Qoder 建议保留或软链接；若已弃用可直接删除释放空间。"
    },
    ".qoder-cn": {
        "app": "Qoder 国内独立版实例",
        "category": "AI 编程智能体",
        "desc": "Qoder 国内版独立实例产生的扩展与配置缓存。",
        "risk": "🟡 按需保留",
        "risk_level": "CAUTION",
        "can_symlink": True,
        "advice": "若仅使用主版 Qoder，可清理该独立版残留。"
    },
    ".workbuddy": {
        "app": "WorkBuddy (腾讯企业级 AI Agent 平台)",
        "category": "AI 编程智能体",
        "desc": "WorkBuddy 客户端核心存储，内含 SQLite 数据库、MCP 代理、iOA 认证缓存与会话记录。",
        "risk": "🟡 谨慎保留",
        "risk_level": "CAUTION",
        "can_symlink": True,
        "advice": "企业日常使用不可删除；若已卸载该软件可直接清除释放空间。"
    },
    ".workbuddy-key-fallback": {
        "app": "WorkBuddy 密钥降级目录",
        "category": "AI 辅助工具",
        "desc": "WorkBuddy 连接器 API Key 备用降级目录。",
        "risk": "🟡 随主程序保留",
        "risk_level": "CAUTION",
        "can_symlink": False,
        "advice": "体积极小，建议随 WorkBuddy 主程序一同保留。"
    },
    ".copilot": {
        "app": "GitHub Copilot CLI / 扩展",
        "category": "AI 辅助工具",
        "desc": "GitHub Copilot 全局配置、IDE 联机缓存与 MCP 服务配置 (mcp-config.json)。",
        "risk": "🟡 建议保留",
        "risk_level": "CAUTION",
        "can_symlink": False,
        "advice": "存储 Copilot 全局设置，建议保留。"
    },
    ".cline": {
        "app": "Cline (VS Code 自主 AI 编程插件)",
        "category": "AI 辅助工具",
        "desc": "Cline 插件的本地历史工作数据与任务快照。",
        "risk": "🟢 可安全清理",
        "risk_level": "SAFE_CACHE",
        "can_symlink": False,
        "advice": "存放任务历史，插件运行时会自动按需重建。"
    },
    ".roo-cline": {
        "app": "Roo Cline (Roo Code AI 插件)",
        "category": "AI 辅助工具",
        "desc": "Roo Code (Cline 分支) 插件的任务数据与本地配置。",
        "risk": "🟢 可安全清理",
        "risk_level": "SAFE_CACHE",
        "can_symlink": False,
        "advice": "存放会话与任务快照。"
    },
    ".cursor": {
        "app": "Cursor AI IDE",
        "category": "AI 编程智能体",
        "desc": "Cursor 编辑器的用户配置、扩展、索引缓存与历史会话。",
        "risk": "🟡 建议保留",
        "risk_level": "CAUTION",
        "can_symlink": True,
        "advice": "若使用 Cursor 则需保留，插件多时可通过软链接迁移至其他盘。"
    },
    ".windsurf": {
        "app": "Windsurf (Codeium AI IDE)",
        "category": "AI 编程智能体",
        "desc": "Windsurf IDE 的用户级数据、Cortex 记忆模型与扩展插件。",
        "risk": "🟡 建议保留",
        "risk_level": "CAUTION",
        "can_symlink": True,
        "advice": "若使用 Windsurf 请保留，支持软链接迁移。"
    },
    ".trae": {
        "app": "Trae (字节跳动 AI IDE)",
        "category": "AI 编程智能体",
        "desc": "Trae IDE 的用户配置、插件扩展与工作流状态。",
        "risk": "🟡 建议保留",
        "risk_level": "CAUTION",
        "can_symlink": True,
        "advice": "使用 Trae 时请保留。"
    },
    ".supermaven": {
        "app": "Supermaven (极速代码补全插件)",
        "category": "AI 辅助工具",
        "desc": "Supermaven 激活状态与本地配置 (config.json)。",
        "risk": "🟡 建议保留",
        "risk_level": "CAUTION",
        "can_symlink": False,
        "advice": "删除后需要在编辑器中重新输入 Activation Token。"
    },
    ".cc-switch": {
        "app": "CC-Switch (AI 助手多账号切换器)",
        "category": "AI 辅助工具",
        "desc": "用于在 Claude Code / Codex / Copilot 间多账号一键轮换的凭据数据库与配置。",
        "risk": "🟡 建议保留",
        "risk_level": "CAUTION",
        "can_symlink": False,
        "advice": "保存了多个绑定的 OAuth 登录 Token，删除后需重新绑定各平台账号。"
    },
    ".semantic_search": {
        "app": "本地代码语义检索模块",
        "category": "AI 辅助工具",
        "desc": "存放本地代码语义检索专用的向量嵌入模型文件 (models/)。",
        "risk": "🟢 可重建缓存",
        "risk_level": "SAFE_CACHE",
        "can_symlink": True,
        "advice": "删除后相关 AI 工具在首次进行代码库语义搜索时会自动重新下载。"
    },
    ".cliguard": {
        "app": "CLI Guard (终端高危指令安全守护)",
        "category": "终端安全守护",
        "desc": "终端命令执行安全拦截与权限守护进程，监控高危 CLI 指令执行。",
        "risk": "🔴 严禁删除",
        "risk_level": "CRITICAL",
        "can_symlink": False,
        "advice": "企业安全基线守护进程相关文件，切勿随意删除。"
    },
    ".ollama": {
        "app": "Ollama 本地大模型运行框架",
        "category": "AI 模型框架",
        "desc": "Ollama 本地运行环境，默认存储下载的所有本地开源大模型文件 (models/)。",
        "risk": "🟢 模型可软链接",
        "risk_level": "CAUTION",
        "can_symlink": True,
        "advice": "通常体积巨大（数 GB 至数十 GB），强烈推荐使用软链接迁移到大容量数据盘！"
    },
    ".huggingface": {
        "app": "Hugging Face Hub CLI / Transformers",
        "category": "AI 模型框架",
        "desc": "Hugging Face 登录凭证 (token) 与本地模型元数据缓存。",
        "risk": "🟢 缓存可清理",
        "risk_level": "SAFE_CACHE",
        "can_symlink": True,
        "advice": "保存了 HF 登录 Token 与模型下载缓存，可迁移或清理。"
    },

    # 开发工具与 IDE
    ".vscode": {
        "app": "Visual Studio Code",
        "category": "开发工具 / IDE",
        "desc": "VS Code 全局插件安装目录 (extensions/) 与命令行工具。",
        "risk": "🔴 核心插件库",
        "risk_level": "CRITICAL",
        "can_symlink": True,
        "advice": "直接删除会导致 VS Code 所有已安装插件丢失！若体积过大强烈推荐使用软链接整体迁移到其他盘。"
    },
    ".vscode-insiders": {
        "app": "VS Code Insiders (预览版)",
        "category": "开发工具 / IDE",
        "desc": "VS Code Insiders 预览版扩展与 CLI 运行环境。",
        "risk": "🔴 核心插件库",
        "risk_level": "CRITICAL",
        "can_symlink": True,
        "advice": "Insiders 版插件目录，推荐软链接迁移。"
    },
    ".vscode-shared": {
        "app": "VS Code / 派生 IDE 共享存储",
        "category": "开发工具 / IDE",
        "desc": "VS Code 及其派生版本间共享的持久化键值存储 (sharedStorage)。",
        "risk": "🟢 可安全清理",
        "risk_level": "SAFE_CACHE",
        "can_symlink": False,
        "advice": "临时共享存储，删除后软件会自动重建。"
    },
    ".android": {
        "app": "Android Studio / Android SDK",
        "category": "移动开发 SDK",
        "desc": "Android 开发者调试证书 (debug.keystore)、ADB 授权公私钥 (adbkey) 与 AVD 模拟器硬件配置。",
        "risk": "🔴 建议保留",
        "risk_level": "CRITICAL",
        "can_symlink": True,
        "advice": "删除后每次连接真机调试都需要重新在手机上弹窗授权确认。"
    },
    ".ld9virtualbox": {
        "app": "雷电模拟器 9 (LDPlayer 9)",
        "category": "安卓模拟器 / 虚拟机",
        "desc": "雷电模拟器后台 VirtualBox 虚拟化底层服务的运行日志文件 (VBoxSVC.log.1~10)。",
        "risk": "🟢 可安全删除",
        "risk_level": "SAFE_CACHE",
        "can_symlink": False,
        "advice": "全部为历史运行日志，模拟器启动时会自动生成新日志，可随意清空。"
    },
    ".dlv": {
        "app": "Delve (Go 语言官方调试器)",
        "category": "编程调试工具",
        "desc": "Go 语言调试器 dlv 的个性化配置文件 (config.yml)。",
        "risk": "🟢 建议保留",
        "risk_level": "SAFE_CACHE",
        "can_symlink": False,
        "advice": "体积极小，存储 Go 调试参数配置。"
    },

    # 语言 SDK 与包管理缓存
    ".gradle": {
        "app": "Gradle (Java/Android 构建工具)",
        "category": "包管理 / 构建工具",
        "desc": "全局 Gradle 依赖缓存，存放 Maven/Google 源下载的 jar/aar 包、Wrapper 发行包与 Daemon 守护日志。",
        "risk": "🟢 可安全清空",
        "risk_level": "SAFE_CACHE",
        "can_symlink": True,
        "advice": "全为下载缓存！删除可瞬间释放数 GB 空间。强烈推荐使用软链接迁移到其他盘！"
    },
    ".m2": {
        "app": "Apache Maven",
        "category": "包管理 / 构建工具",
        "desc": "Maven 本地仓库 (repository/)，存放 Java 项目下载的所有第三方依赖 jar 包。",
        "risk": "🟢 依赖缓存",
        "risk_level": "SAFE_CACHE",
        "can_symlink": True,
        "advice": "全为构建依赖，可安全删除或推荐软链接迁移至其他盘。"
    },
    ".nuget": {
        "app": "Microsoft NuGet (.NET 包管理器)",
        "category": "包管理 / 构建工具",
        "desc": ".NET / C# 全局包缓存目录 (packages/)，存放 dotnet restore 下载的 NuGet 包。",
        "risk": "🟢 可安全清空",
        "risk_level": "SAFE_CACHE",
        "can_symlink": True,
        "advice": "可使用 `dotnet nuget locals all --clear` 或直接删除释放数 GB 空间，项目编译时会自动重新拉取。"
    },
    ".dotnet": {
        "app": "Microsoft .NET SDK",
        "category": "语言 SDK / 运行时",
        "desc": ".NET SDK 首次运行标记 (Sentinel)、遥测数据 (Telemetry) 与 Workload 清单。",
        "risk": "🟡 建议保留",
        "risk_level": "CAUTION",
        "can_symlink": False,
        "advice": "体积微小，属于 .NET SDK 运行状态标记。"
    },
    ".cargo": {
        "app": "Rust Cargo 包管理器",
        "category": "包管理 / 构建工具",
        "desc": "Rust Crates 下载缓存 (registry/)、Git 源码依赖与全局安装的 Cargo 二进制程序 (bin/)。",
        "risk": "🟢 缓存可迁移",
        "risk_level": "SAFE_CACHE",
        "can_symlink": True,
        "advice": "通常体积巨大（数 GB），强烈建议通过环境变量 CARGO_HOME 或软链接迁移到大容量盘。"
    },
    ".rustup": {
        "app": "Rustup (Rust 工具链安装器)",
        "category": "语言 SDK / 工具链",
        "desc": "存放安装的 Rust 编译器工具链 (toolchains/) 与目标架构库。",
        "risk": "🔴 核心工具链",
        "risk_level": "CRITICAL",
        "can_symlink": True,
        "advice": "属于 Rust 编译器核心本体，删除将导致 rustc/cargo 无法运行，推荐软链接整体迁移。"
    },
    ".bundle": {
        "app": "Ruby Bundler",
        "category": "包管理 / 构建工具",
        "desc": "Ruby 语言依赖包管理器 Bundler 的全局 gem 下载缓存。",
        "risk": "🟢 可安全清理",
        "risk_level": "SAFE_CACHE",
        "can_symlink": False,
        "advice": "若不开发 Ruby 项目可安全删除释放空间。"
    },
    ".npm": {
        "app": "Node.js npm 包管理器",
        "category": "包管理 / 构建工具",
        "desc": "npm 下载的 tarball 模块包缓存 (_cacache/)。",
        "risk": "🟢 可安全清空",
        "risk_level": "SAFE_CACHE",
        "can_symlink": True,
        "advice": "可运行 `npm cache clean --force` 或直接删除，不影响已有项目运行。"
    },
    ".yarn": {
        "app": "Yarn 包管理器",
        "category": "包管理 / 构建工具",
        "desc": "Yarn 全局离线镜像与依赖缓存。",
        "risk": "🟢 可安全清理",
        "risk_level": "SAFE_CACHE",
        "can_symlink": True,
        "advice": "可安全清空释放空间。"
    },
    ".pnpm-store": {
        "app": "pnpm 包管理器",
        "category": "包管理 / 构建工具",
        "desc": "pnpm 全局硬链接依赖内容寻址库 (Content-addressable store)。",
        "risk": "🟢 建议软链接",
        "risk_level": "SAFE_CACHE",
        "can_symlink": True,
        "advice": "体积较大，推荐软链接迁移至开发数据盘。"
    },

    # 系统底层、安全密钥与 XDG 跨平台规范
    ".ssh": {
        "app": "OpenSSH 客户端",
        "category": "系统安全 / 远程凭证",
        "desc": "极度重要的 SSH 密钥库！包含 Git / Linux 服务器连接私钥 (id_rsa)、公钥及服务器指纹 (known_hosts)。",
        "risk": "🚨 绝对禁止随意删除",
        "risk_level": "CRITICAL",
        "can_symlink": False,
        "advice": "删除将导致所有配置了 SSH 密钥的 GitHub/GitLab 仓库无法推送，所有远程服务器连接鉴权失败！"
    },
    ".aws": {
        "app": "Amazon AWS CLI / SDK",
        "category": "云服务 CLI",
        "desc": "AWS 命令行工具的凭据文件 (credentials)、配置文件 (config) 及 SSO 登录会话缓存。",
        "risk": "🟡 建议保留",
        "risk_level": "CAUTION",
        "can_symlink": False,
        "advice": "保存了 AWS 访问密钥或 SSO 登录会话，删除后需重新 `aws configure`。"
    },
    ".azure": {
        "app": "Microsoft Azure CLI",
        "category": "云服务 CLI",
        "desc": "Azure CLI 登录 Token 与订阅配置缓存。",
        "risk": "🟡 建议保留",
        "risk_level": "CAUTION",
        "can_symlink": False,
        "advice": "删除后需重新 `az login`。"
    },
    ".kube": {
        "app": "Kubernetes (kubectl)",
        "category": "容器编排 / 集群配置",
        "desc": "Kubernetes 集群连接配置 (config)，包含集群 API 地址与访问证书。",
        "risk": "🔴 严禁删除",
        "risk_level": "CRITICAL",
        "can_symlink": False,
        "advice": "删除将导致 kubectl 无法连接任何 K8s 集群。"
    },
    ".docker": {
        "app": "Docker Desktop / Docker CLI",
        "category": "容器工具",
        "desc": "Docker Hub 登录凭证、上下文配置与构建器缓存状态。",
        "risk": "🟡 建议保留",
        "risk_level": "CAUTION",
        "can_symlink": False,
        "advice": "保存了镜像仓库登录凭证与 Docker 环境配置。"
    },
    ".cache": {
        "app": "Linux/XDG 规范通用缓存目录",
        "category": "XDG 标准缓存",
        "desc": "各种跨平台工具（如 Codex 运行时、Gem、OpenCode、pip、ripgrep 等）存放的临时下载与编译缓存。",
        "risk": "🟢 可重点瘦身",
        "risk_level": "SAFE_CACHE",
        "can_symlink": True,
        "advice": "属于标准缓存目录，可定期清理其内部的子目录（如 codex-runtimes）腾出巨大空间。"
    },
    ".config": {
        "app": "Linux/XDG 规范通用配置目录",
        "category": "XDG 标准配置",
        "desc": "跨平台工具（如 Git、OpenCode、GitHub CLI、Gem 等）的标准配置文件存放目录。",
        "risk": "🟡 建议保留",
        "risk_level": "CAUTION",
        "can_symlink": True,
        "advice": "存放软件配置而非体积文件，体积一般不大，建议保留。"
    },
    ".local": {
        "app": "Linux/XDG 规范用户级软件与数据",
        "category": "XDG 标准本地程序",
        "desc": "存放用户级独立安装的命令行工具 (bin/ 内有 uv、kiro-cli、python 等) 及 share/ 应用程序数据。",
        "risk": "🟡 谨慎操作",
        "risk_level": "CAUTION",
        "can_symlink": True,
        "advice": "包含独立的 Python/CLI 可执行程序，若删除可能导致终端命令失效。"
    }
}


def get_link_target(path):
    """Check if the directory is a symlink or Windows Junction and return its target."""
    try:
        if os.path.islink(path):
            return os.readlink(path)
    except Exception:
        pass
    
    try:
        import ctypes
        GetFileAttributesW = ctypes.windll.kernel32.GetFileAttributesW
        FILE_ATTRIBUTE_REPARSE_POINT = 0x400
        attrs = GetFileAttributesW(path)
        if attrs != -1 and (attrs & FILE_ATTRIBUTE_REPARSE_POINT):
            realpath = os.path.realpath(path)
            if realpath.lower() != path.lower():
                return realpath
            return "已链接 (Junction / Reparse Point)"
    except Exception:
        pass
    return None


def calculate_dir_stats(path):
    """Fast directory size and file count calculator."""
    total_size = 0
    file_count = 0
    top_entries = []
    
    try:
        top_entries = [entry.name for entry in os.scandir(path)][:8]
    except Exception:
        pass

    try:
        for root, dirs, files in os.walk(path):
            file_count += len(files)
            for f in files:
                try:
                    fp = os.path.join(root, f)
                    total_size += os.path.getsize(fp)
                except Exception:
                    pass
    except Exception:
        pass
    
    return total_size, file_count, top_entries


def heuristic_analysis(folder_name, top_entries, full_path):
    """Infer purpose and origin for unknown folders using heuristic rules."""
    name_lower = folder_name.lower()
    
    if name_lower.startswith(".venv") or "venv" in name_lower or "env" in name_lower:
        if any(e in top_entries for e in ["pyvenv.cfg", "Scripts", "Lib", "bin"]):
            return {
                "app": f"Python 虚拟环境 ({folder_name})",
                "category": "Python 开发环境",
                "desc": f"针对特定项目创建的独立 Python 虚拟环境，包含专属的 Python 解释器与第三方库。",
                "risk": "🟢 按需删除",
                "risk_level": "SAFE_CACHE",
                "can_symlink": True,
                "advice": "若对应项目已完成或不再开发，可直接删除该虚拟环境。"
            }

    if name_lower == ".git":
        return {
            "app": "Git 版本控制仓库元数据",
            "category": "版本控制",
            "desc": "Git 仓库的核心版本库目录，包含所有提交历史、分支与 HEAD 指针。",
            "risk": "🔴 严禁删除",
            "risk_level": "CRITICAL",
            "can_symlink": False,
            "advice": "删除将导致整个目录脱离 Git 版本管理并丢失本地未推送的版本历史。"
        }

    if "log" in name_lower or any(".log" in e for e in top_entries):
        return {
            "app": f"软件日志目录 ({folder_name})",
            "category": "运行日志",
            "desc": f"特定应用程序或脚本运行时输出的诊断日志文件。",
            "risk": "🟢 可安全清理",
            "risk_level": "SAFE_CACHE",
            "can_symlink": False,
            "advice": "主要为日志排查文件，若无故障排查需求可清空。"
        }

    app_hint = ""
    for entry in top_entries:
        if entry.endswith(".json") or entry.endswith(".toml") or entry.endswith(".yaml") or entry.endswith(".yml"):
            try:
                cfg_path = os.path.join(full_path, entry)
                if os.path.getsize(cfg_path) < 10240:
                    with open(cfg_path, 'r', encoding='utf-8', errors='ignore') as fp:
                        raw = fp.read()
                        if "name" in raw or "app" in raw or "description" in raw:
                            app_hint = f"（内含配置文件 {entry}）"
            except Exception:
                pass

    return {
        "app": f"未知软件 / 自定义工具 ({folder_name})",
        "category": "其他配置/缓存",
        "desc": f"由第三方工具、开发脚本或自定义环境生成的配置文件目录{app_hint}。",
        "risk": "🟡 建议保留",
        "risk_level": "CAUTION",
        "can_symlink": True,
        "advice": "若不确定产生该文件夹的具体软件，建议先重命名观察几天，无异常后再行删除。"
    }


def analyze_user_directory(target_dir=None, target_drive="D:"):
    if not target_dir:
        target_dir = os.path.expanduser("~")
    
    print("\n" + "=" * 80)
    print("🚀 Windows 用户目录点号文件夹智能分析引擎 (User Directory Analyzer)")
    print(f"📁 扫描目标路径: {target_dir}")
    print(f"🕒 扫描开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 80 + "\n")

    if not os.path.exists(target_dir):
        print(f"❌ 错误: 目标路径不存在 -> {target_dir}")
        return

    try:
        all_entries = os.listdir(target_dir)
    except Exception as e:
        print(f"❌ 访问目录失败: {e}")
        return

    dot_folders = [d for d in all_entries if d.startswith('.') and os.path.isdir(os.path.join(target_dir, d))]
    dot_folders.sort(key=lambda x: x.lower())

    print(f"🔍 发现 {len(dot_folders)} 个点号文件夹，正在并发计算体积并深度识别...\n")

    analyzed_items = []
    
    with ThreadPoolExecutor(max_workers=8) as executor:
        futures = {}
        for d in dot_folders:
            p = os.path.join(target_dir, d)
            futures[d] = executor.submit(calculate_dir_stats, p)
        
        for d in dot_folders:
            p = os.path.join(target_dir, d)
            total_size, file_count, top_entries = futures[d].result()
            link_target = get_link_target(p)
            
            if d.lower() in KNOWLEDGE_BASE:
                info = KNOWLEDGE_BASE[d.lower()].copy()
            else:
                info = heuristic_analysis(d, top_entries, p)

            size_mb = round(total_size / (1024 * 1024), 2)
            analyzed_items.append({
                "name": d,
                "path": p,
                "size_bytes": total_size,
                "size_mb": size_mb,
                "file_count": file_count,
                "top_entries": top_entries,
                "is_link": bool(link_target),
                "link_target": link_target,
                "app": info["app"],
                "category": info["category"],
                "desc": info["desc"],
                "risk": info["risk"],
                "risk_level": info["risk_level"],
                "can_symlink": info.get("can_symlink", True),
                "advice": info["advice"]
            })

    analyzed_items.sort(key=lambda x: x["size_bytes"], reverse=True)

    total_bytes = sum(x["size_bytes"] for x in analyzed_items)
    total_files = sum(x["file_count"] for x in analyzed_items)
    total_mb = round(total_bytes / (1024 * 1024), 2)
    total_gb = round(total_bytes / (1024 * 1024 * 1024), 2)

    print(f"{'文件夹名称':<25} | {'体积(MB)':<10} | {'文件数':<7} | {'所属软件 / 工具':<22} | {'安全度'}")
    print("-" * 90)
    for item in analyzed_items:
        link_tag = " (🔗已软链接)" if item["is_link"] else ""
        print(f"{item['name'] + link_tag:<25} | {item['size_mb']:<10.2f} | {item['file_count']:<7} | {item['app'][:20]:<22} | {item['risk']}")
    
    print("-" * 90)
    print(f"📊 总计: {len(analyzed_items)} 个文件夹 | 总大小: {total_gb:.2f} GB ({total_mb:.2f} MB) | 总文件数: {total_files} 个\n")

    output_doc_path = generate_markdown_report(target_dir, analyzed_items, total_gb, total_mb, total_files, target_drive)
    print(f"✅ 分析报告已成功生成: {output_doc_path}\n")
    return output_doc_path


def generate_markdown_report(target_dir, items, total_gb, total_mb, total_files, target_drive):
    timestamp_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    file_timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    username = os.path.basename(target_dir.rstrip("\\/"))
    script_dir = os.path.dirname(os.path.abspath(__file__))
    output_dir = os.path.join(script_dir, "reports")
    os.makedirs(output_dir, exist_ok=True)
    report_file = os.path.join(output_dir, f"用户目录点号文件夹全面解析报告_{username}_{file_timestamp}.md")
    standard_report_file = os.path.join(output_dir, "用户目录点号文件夹全面解析报告_最新.md")

    categories = {}
    for item in items:
        cat = item["category"]
        if cat not in categories:
            categories[cat] = []
        categories[cat].append(item)

    big_items = [x for x in items if x["size_mb"] >= 300 and not x["is_link"] and x["can_symlink"]]

    md = []
    md.append(f"# Windows 用户目录（{target_dir}）点号文件夹全面解析报告\n\n")
    md.append(f"> **生成时间**：{timestamp_str}  \n")
    md.append(f"> **分析路径**：`{target_dir}`  \n")
    md.append(f"> **当前用户**：`{username}`  \n")
    md.append(f"> **统计对象**：以 `.`（点号）开头的系统/开发/AI隐藏配置与缓存文件夹（共计 {len(items)} 个）\n\n")
    md.append("---\n\n")

    md.append("## 📊 一、 核心统计与空间分布\n\n")
    md.append(f"* **点号文件夹总数**：`{len(items)}` 个\n")
    md.append(f"* **总磁盘空间占用**：**`{total_gb:.2f} GB`** (`{total_mb:,.2f} MB`)\n")
    md.append(f"* **文件总数**：`{total_files:,}` 个\n\n")

    md.append("### 🏆 磁盘占用 TOP 5 文件夹\n")
    for i, item in enumerate(items[:5], 1):
        link_str = " *(🔗 当前为软链接)*" if item["is_link"] else ""
        md.append(f"{i}. **`{item['name']}`** —— **`{item['size_mb']:,.2f} MB`** ({item['app']}){link_str}\n")
    md.append("\n---\n\n")

    md.append("## 🗂️ 二、 分类详细解析表\n\n")

    for cat_name, cat_items in categories.items():
        cat_total_mb = sum(x["size_mb"] for x in cat_items)
        md.append(f"### 📁 {cat_name}（共 {len(cat_items)} 个，合计 `{cat_total_mb:,.2f} MB`）\n\n")
        md.append("| 文件夹名称 | 体积大小 | 产生软件 / 组件 | 功能作用与存储内容 | 清理建议与风险判定 |\n")
        md.append("| :--- | :--- | :--- | :--- | :--- |\n")
        for item in cat_items:
            link_note = f"<br>*(🔗 链接指向: `{item['link_target']}`)*" if item["is_link"] else ""
            desc_formatted = item['desc'].replace('\n', '<br>')
            advice_formatted = item['advice'].replace('\n', '<br>')
            md.append(f"| **`{item['name']}`**{link_note} | **{item['size_mb']:,.2f} MB**<br>({item['file_count']} 个文件) | **{item['app']}** | {desc_formatted} | **{item['risk']}**<br>{advice_formatted} |\n")
        md.append("\n")

    md.append("---\n\n")

    md.append("## 🧹 三、 C 盘空间瘦身与软链接无痛迁移方案\n\n")

    safe_clean_items = [x for x in items if x["risk_level"] == "SAFE_CACHE" and x["size_mb"] > 10 and not x["is_link"]]
    if safe_clean_items:
        safe_mb = sum(x["size_mb"] for x in safe_clean_items)
        md.append(f"### 1. 🟢 零风险直接释放区（预计可直接释放约 `{safe_mb:,.2f} MB`）\n")
        md.append("以下文件夹仅存放下载缓存、构建中间件或历史日志，清空后软件在需要时会自动重新拉取，不影响配置：\n\n")
        for x in safe_clean_items:
            md.append(f"* **`{x['name']}`** (`{x['size_mb']:,.2f} MB`)：{x['advice']}\n")
        md.append("\n")

    if big_items:
        md.append(f"### 2. 🚀 推荐软链接迁移区（体积大于 300MB 的文件夹）\n")
        md.append(f"这些文件夹体积庞大（例如依赖库、IDE 插件或模型），直接删除会导致软件无法工作，但可以使用 **Windows Junction 软链接** 将其无感迁移到数据盘（如 `{target_drive}` 盘）：\n\n")
        
        md.append("```cmd\n:: ========================================================================\n")
        md.append(f":: 一键软链接迁移脚本（以迁移至 {target_drive}\\UserLinks 为例）\n")
        md.append(":: 注意：迁移前请确保对应的开发工具/软件已经完全退出！\n")
        md.append(f":: ========================================================================\n\n")
        md.append(f"mkdir \"{target_drive}\\UserLinks\" 2>nul\n\n")

        for item in big_items:
            src_path = item["path"]
            dst_path = f"{target_drive}\\UserLinks\\{item['name']}"
            md.append(f":: --- 迁移 {item['name']} ({item['size_mb']:,.2f} MB) ---\n")
            md.append(f"move \"{src_path}\" \"{dst_path}\"\n")
            md.append(f"mklink /J \"{src_path}\" \"{dst_path}\"\n\n")
        
        md.append("```\n\n")

    md.append("### 3. 🔴 严禁触碰的红线区\n")
    md.append("* **`.ssh`**：存放 Git / 服务器 SSH 登录私钥，删除将导致无法推送代码或连接服务器！\n")
    md.append("* **`.gemini`**：当前对话与 Antigravity 智能体环境的核心上下文与记忆数据。\n")
    md.append("* **`.vscode`**：直接删除会导致 VS Code 所有已安装插件丢失。\n")
    md.append("* **`.android`**：存放真机调试证书与模拟器硬件配置。\n\n")

    report_content = "".join(md)

    with open(report_file, "w", encoding="utf-8") as f:
        f.write(report_content)
    
    with open(standard_report_file, "w", encoding="utf-8") as f:
        f.write(report_content)

    return report_file


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Windows 用户目录点号文件夹深度分析与瘦身建议工具")
    parser.add_argument("-p", "--path", help="要扫描的用户目录路径 (默认: 当前用户目录 %%USERPROFILE%%)", default=None)
    parser.add_argument("-d", "--drive", help="推荐软链接迁移的目标盘符 (默认: D:)", default="D:")
    args = parser.parse_args()

    analyze_user_directory(args.path, args.drive)
