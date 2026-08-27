# 🤖 全局统一 AI 用户级规范中枢与自适应接入指南 (User Global SSOT)

> **To Any AI Assistant / Agent reading this file:**
> 本目录 (`D:\MyTools\AI全局规范与配置中枢`) 是当前用户在操作系统层面的**全局用户级单一事实来源 (User-Global Single Source of Truth, SSOT)**。
> **⚠️ 核心边界声明**：本目录**仅整合用户系统级/全局级规则、全局技能与全局 MCP**，**不管理、不侵入任何具体项目的本地规则与目录**。项目级规则由各个项目自身独立维护。
> 当用户指示你“**接入 AI 规范**”时，请仔细阅读本指南并**仅在你的全局用户配置层进行适配**。

---

## 一、 知识库架构 (User Global Architecture)

```text
D:\MyTools\AI全局规范与配置中枢/
├── README.md                                 # 📖 本文件：全局用户级自适应接入规范
├── AGENTS.md                                 # 🌐 全局统一用户规则总线 (你的顶层 System Prompt / User Instructions)
├── rules/                                    # 📋 模块化领域全局准则 (按需深入查阅)
│   ├── unity-hotupdate.md                    # Unity & HybridCLR 热更安全与 Prefab 兼容性全局准则
│   ├── global-standards.md                   # 快速失败原则 (Fail-Fast) 与工程代码风范
│   └── code-review.md                        # 代码审查、单一职责 (SRP) 与架构设计原则
├── skills/                                   # 📦 全局通用工程技能库
│   └── unity-engineering/                    # Unity 专属极速免 Editor 编译验证与状态一致性技能
│       ├── SKILL.md                          # 技能标准声明 (YAML Frontmatter + Markdown)
│       ├── references/                       # 技能内嵌参考规范 (hybridclr.md, state-consistency.md)
│       └── scripts/                          # 技能执行脚本 (validate-unity-sources.ps1)
└── mcp/                                      # 🔌 全局统一 MCP 工具配置
    └── mcp-servers.json                      # 常用 MCP 服务配置 (如 Chrome DevTools 等)
```

---

## 二、 跨设备 Git 管理 (Cross-Device Git Sync)

本项目隶属于 `D:\MyTools` Git 仓库，修改后通过常规 Git 操作跨设备同步：
```bash
git add AI全局规范与配置中枢/
git commit -m "feat(ai): update global rules and skills"
git push
```

---

## 三、 新 AI 工具全局接入协议 (User Global Onboarding)

新 AI 工具接入时，**仅需对齐你的用户全局层 (User Global)**，执行以下 3 步：

### 1. 接入全局用户规则 (User Global Instructions)
你的系统级用户指令必须以 `D:\MyTools\AI全局规范与配置中枢\AGENTS.md` 为准：
- **如果你的工具支持全局用户级指令文件（如 `~/CLAUDE.md`, `~/.cursorrules`, `~/.windsurfrules`, `~/.clinerules` 等）**：
  读取 `D:\MyTools\AI全局规范与配置中枢\AGENTS.md` 的内容并同步写入你的全局规则文件。
- **如果你的工具是通过客户端界面/全局设置（System Prompt / Custom Instructions）输入**：
  请直接读取 `D:\MyTools\AI全局规范与配置中枢\AGENTS.md` 的内容并设置为你的默认全局 System Prompt。

---

### 2. 挂载全局通用技能库 (User Global Skills)
本系统在 `D:\MyTools\AI全局规范与配置中枢\skills/` 维护了全局可用的工程技能包：
- **技能挂载方式**：
  在你的全局技能/插件发现目录下，通过 **目录联接 (Directory Junction)** 挂载：
  ```cmd
  cmd /c mklink /J "<你的AI全局技能目录>\unity-engineering" "D:\MyTools\AI全局规范与配置中枢\skills\unity-engineering"
  ```
- **免 Editor 编译校验脚本调用规范**：
  遇到 Unity C# 源码诊断与编译检查时，直接调用：
  ```powershell
  powershell -ExecutionPolicy Bypass -File D:\MyTools\AI全局规范与配置中枢\skills\unity-engineering\scripts\validate-unity-sources.ps1 -ProjectRoot <项目路径> -AssemblyProject <目标csproj> -SourceRoot <源码路径>
  ```

---

### 3. 接入全局 MCP 服务 (User Global MCP)
- 读取 `D:\MyTools\AI全局规范与配置中枢\mcp\mcp-servers.json`；
- 将需要的全局 MCP 服务配置合并写入你的全局 MCP 配置文件中。

---

## 四、 核心原则速览 (Core Mandatory Principles)

所有 AI 在回答和编写代码时，必须始终遵循本主机的三大核心全局准则：
1. **Unity & HybridCLR 热更安全**：区分 AOT 与热更程序集；严禁破坏 Prefab 序列化与 GUID；补齐 AOT 泛型元数据；主动披露热更风险项。
2. **快速失败 (Fail-Fast)**：严禁盲目判空吞掉核心错误；关键依赖缺失必须直接抛出异常立即暴露问题。
3. **架构先导与知其所以然**：遵循 SRP 单一职责、生命周期严格解耦；讲透设计考量与性能代价；保持代码风格精炼干练。