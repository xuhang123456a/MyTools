# 🤖 全局统一 AI 用户级规范中枢与自适应接入指南 (User Global SSOT)

> **To Any AI Assistant / Agent reading this file:**
> 本目录是当前用户在操作系统层面的**全局用户级单一事实来源 (User-Global Single Source of Truth, SSOT)**。
> 
> **⚠️ 核心准则与铁律：**
> 1. **核心边界声明**：本目录**仅整合用户系统级/全局级规则、全局技能与全局 MCP**，**不管理、不侵入任何具体项目的本地规则与目录**。项目级规则由各个项目自身独立维护。
> 2. **🧠 纯 AI 自主分析接入（严禁死板自动化脚本）**：本规范库**严禁编写或依赖任何一刀切的自动化脚本（如 `.bat`, `.ps1` 等）**。各类 AI 客户端演进迅速且配置形式各异，死板脚本无法适应未来。后续所有 AI 助手必须根据本指南自主识别环境与客户端类型，动态执行接入操作。
> 3. **🛡️ 接入前检查与规则增量融合红线（严禁暴力覆盖）**：在接入任何用户全局规则前，**必须先检查宿主机当前已存在的各 AI 用户级规则与配置**（如 `~/CLAUDE.md`, `~/.cursorrules`, `~/.windsurfrules`, `~/.clinerules` 等）。若存在既有规则，必须先行阅读并**以增量方式安全整合**，严禁直接覆盖导致遗失本机已有规则。
> 4. **🌐 跨设备便携设计**：本规范库采用 100% 相对路径与动态环境变量，无论本仓库克隆在哪个磁盘或路径下，均可无缝跨设备运行。
> 
> 当用户指示你“**接入 AI 规范**”或“**配置本机 AI 环境**”时，请仔细阅读本指南并**仅在你的全局用户配置层进行自主适配**。

---

## 一、 知识库架构：技术栈解耦与按需分流

```text
AI全局规范与配置中枢/ (位于你的 MyTools 仓库根目录下)
├── README.md                                 # 📖 本文件：全局用户级自适应接入规范
├── AGENTS.md                                 # 🌐 全局技术栈自适应路由总线 (极简分流器，0 冗余经验常驻)
│
├── rules/                                    # 📋 模块化技术栈专属规则库 (仅在对应技术栈激活)
│   └── unity/                                # 🎮 Unity 专属工程规范
│       └── unity-standards.md                # (Unity 专属 Fail-Fast / 架构设计 / HybridCLR 热更安全)
│   # 💡 未来可在此扩展 rules/python/, rules/web/ 等...
│
├── skills/                                   # 📦 全局通用工程技能库
│   └── unity-engineering/                    # Unity 专属极速免 Editor 编译验证与状态一致性技能
│       ├── SKILL.md                          # 技能标准声明 (YAML Frontmatter + Markdown)
│       ├── references/                       # 技能内嵌参考规范 (hybridclr.md, state-consistency.md)
│       └── scripts/                          # 技能执行脚本 (validate-unity-sources.ps1)
│
└── mcp/                                      # 🔌 全局统一 MCP 工具配置
    └── mcp-servers.json                      # 常用 MCP 服务配置 (如 Chrome DevTools 等)
```

---

## 二、 跨设备 Git 管理 (Cross-Device Git Sync)

本项目隶属于 `MyTools` Git 仓库，修改后通过常规 Git 操作跨设备同步：
```bash
git add AI全局规范与配置中枢/
git commit -m "feat(ai): update multi-stack rules and skills"
git push
```

---

## 三、 新 AI 工具全局自举接入协议 (User Global Onboarding)

当用户指示你接入环境时，**AI 必须自主执行以下 3 步标准化接入流程**：

### 1. 检查既有规则并接入全局路由总线 (Inspect & Integrate User Instructions)
- **第一步：前置基线检查（必须执行）**：
  检查宿主机用户目录下的规则文件（如 `~/CLAUDE.md`, `~/.cursorrules`, `~/.windsurfrules`, `~/.clinerules`, `~/.gemini/config/AGENTS.md` 等）是否已存在内容。
  - 若已有用户个人自定义规则：**严禁直接覆盖**！必须先读取既有内容，将用户的个性化规则与本中枢的 `AGENTS.md` 进行增量整合；
  - 若不存在既有规则或仅为旧版本总线：可直接建立符号链接/软链接或引用当前目录下的 `AGENTS.md`。
- **第二步：对齐全局指令源**：
  - **支持全局指令文件的工具**：在 Windows 下使用符号链接或硬链接绑定到当前目录的 `AGENTS.md`：
    ```cmd
    cmd /c mklink "<用户全局规则路径>" "<本中枢目录>\AGENTS.md"
    ```
  - **通过客户端设置/System Prompt 输入的工具**：读取当前目录下的 `AGENTS.md` 内容并合并写入全局 System Prompt / Custom Instructions。

---

### 2. 挂载全局通用技能库 (Mount Global Skills)
- **技能挂载方式**：
  在目标 AI 客户端的全局技能/插件发现目录下，通过 **目录联接 (Directory Junction)** 挂载，保持源头单点维护且不产生文件副本：
  ```cmd
  cmd /c mklink /J "<你的AI全局技能目录>\unity-engineering" "<本中枢目录>\skills\unity-engineering"
  ```
- **免 Editor 编译校验脚本调用规范**：
  遇到 Unity C# 源码诊断与编译检查时，直接调用：
  ```powershell
  powershell -ExecutionPolicy Bypass -File <本中枢目录>/skills/unity-engineering/scripts/validate-unity-sources.ps1 -ProjectRoot <项目路径> -AssemblyProject <目标csproj> -SourceRoot <源码路径>
  ```

---

### 3. 增量合并全局 MCP 服务 (Incrementally Merge Global MCP)
- 读取当前目录下的 `mcp/mcp-servers.json`；
- 检查目标 AI 客户端现有的全局 MCP 配置文件（如 `~/.gemini/config/mcp_config.json`、`~/.claude.json` 等）；
- **以增量字典合并（Key-level Merge）方式**将本中枢的服务注册进 `mcpServers` 对象中，**严禁覆盖或删除用户已配置的其他 MCP 工具**。