# Windows 用户目录点号文件夹智能分析与空间优化工具

> 🚀 **专为 Windows 平台打造的即插即用型环境分析工具**。  
> 无论是你当前的电脑，还是其他任意 Windows 10/11 机器，都可以**双击一键运行**，全面扫描并深度分析用户目录下所有 `.`（点号）开头的隐藏/配置/缓存文件夹，智能识别所属软件、评估风险等级，并生成高价值的 Markdown 诊断与迁移报告。

---

## 🌟 核心特性

1. **跨机器即插即用（双引擎支持）**：
   * **Python 高效引擎 (`analyzer.py`)**：若目标机器装有 Python，采用并发线程池进行毫秒级极速扫描。
   * **PowerShell 原生引擎 (`analyzer.ps1`)**：**0 依赖**！在没有任何开发环境的纯净 Windows 机器上也能原生稳定运行。
   * **一键启动批处理 (`一键分析.bat`)**：双击自动探测环境并选择最佳引擎运行，分析完成后自动打开最新报告。
2. **海量内置软件知识库（50+ 常见工具）**：
   * **AI 编程与智能体**：Antigravity (`.gemini`)、Claude Code (`.claude`)、Codex (`.codex`)、WorkBuddy (`.workbuddy`)、Qoder (`.qoder`)、Kiro (`.kiro`)、Cursor (`.cursor`)、Windsurf (`.windsurf`)、Trae (`.trae`)、Cline (`.cline`)、Copilot (`.copilot`)、Supermaven (`.supermaven`)、Ollama (`.ollama`) 等。
   * **开发工具与 IDE**：VS Code (`.vscode`)、Android Studio (`.android`)、雷电模拟器 (`.Ld9VirtualBox`)、Delve (`.dlv`) 等。
   * **包管理器与构建缓存**：Gradle (`.gradle`)、Maven (`.m2`)、NuGet (`.nuget`)、Cargo (`.cargo`)、Rustup (`.rustup`)、npm (`.npm`)、Yarn (`.yarn`)、pnpm (`.pnpm-store`)、Bundler (`.bundle`) 等。
   * **系统与安全凭据**：OpenSSH (`.ssh`)、AWS CLI (`.aws`)、Azure (`.azure`)、Kubernetes (`.kube`)、Docker (`.docker`)、XDG 规范 (`.cache`, `.config`, `.local`) 等。
3. **启发式智能嗅探（未知文件夹自动识别）**：
   * 即使遇到知识库外的生僻文件夹，工具会自动解析其内部的 `package.json`、`pyvenv.cfg`、`.toml`、`.yaml`、日志特征及配置文件，智能推断其所属环境与用途。
4. **软链接 / Junction 穿透识别**：
   * 自动探测文件夹是否已经被软链接（Junction / Symlink），精准提取其真实的物理存储路径，防止重复迁移。
5. **一键生成软链接迁移命令**：
   * 针对体积大于 300MB 的重型依赖库（如 `.gradle`、`.vscode`、`.kiro` 等），报告底部自动生成安全的 `mklink /J` 脚本代码，一键复制即可将数据无感搬移至 D 盘！

---

## 🚀 使用方法

### 方式 1：双击一键运行（最推荐）
进入 `D:\MyTools\C盘用户文件夹分析` 文件夹，双击运行 **`一键分析.bat`** 即可。

### 方式 2：使用命令行运行（支持自定义参数）

#### 使用 Python：
```cmd
# 默认扫描当前用户目录并推荐迁移到 D 盘
python analyzer.py

# 扫描指定用户目录并指定迁移盘符为 E:
python analyzer.py -p "C:\Users\张三" -d "E:"
```

#### 使用 PowerShell（免安装 Python）：
```powershell
# 运行 PowerShell 脚本
powershell -ExecutionPolicy Bypass -File .\analyzer.ps1

# 指定扫描路径与迁移盘符
powershell -ExecutionPolicy Bypass -File .\analyzer.ps1 -ScanPath "C:\Users\张三" -TargetDrive "E:"
```

---

## 📁 目录结构说明

```text
D:\MyTools\C盘用户文件夹分析\
│
├── 一键分析.bat                         # [推荐] 双击一键启动脚本（全自动识别 Python / PowerShell）
├── analyzer.py                         # Python 高并发多线程分析引擎
├── analyzer.ps1                        # 原生 PowerShell 免环境分析引擎
├── README.md                           # 工具使用手册与技术说明
├── C盘用户目录点号文件夹全面解析.md     # 当前机器环境基线分析存档
└── reports\                            # 报告输出目录（自动归档并提供最新报告快照）
    ├── 用户目录点号文件夹全面解析报告_Administrator_20260827_140535.md
    └── 用户目录点号文件夹全面解析报告_最新.md
```

---

## 💾 怎样带到其他 Windows 机器上使用？

1. **U盘 / 局域网传输**：直接把 `C盘用户文件夹分析` 整个文件夹复制到另一台电脑（例如放在目标电脑的 `D:\MyTools` 或桌面）。
2. **直接双击**：在目标电脑上双击 `一键分析.bat`，即可立即获取该电脑专属的 C 盘点号文件夹分析与瘦身报告！
