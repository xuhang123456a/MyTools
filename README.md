# 🧰 MyTools - 个人实用工具库

个人常用脚本、效率工具与插件库。按中文类别清晰归档，开箱即用。

---

## 📂 目录结构与工具总览

```text
MyTools/
│
├── 🚀 工作流与效率工具/
│   ├── AI会话历史一键导出.bat    # 双击一键启动 AI 会话历史导出工具 (GUI/CLI)
│   ├── AI会话历史一键导出工具/   # 核心源码包 (支持 Antigravity/Kiro/Workbuddy/VSCode/Cline 等)
│   ├── 项目自动拉取.py          # Git 多项目/子模块安全拉取更新 GUI
│   └── 打开常用文件夹.py        # Win32 智能多窗口阵列与常用路径展开
│
├── 🌐 网络与文本处理/
│   └── 死链检测与自动注释/
│       ├── 多线程死链检测与自动注释脚本.py  # 批量链接/网盘深度检测与注释
│       └── Unity项目实战教程.txt           # 测试用例文件
│
├── 🎵 MusicFree插件/
│   ├── qq.js                   # QQ 音乐音源解析插件
│   ├── xuhang.json             # GitHub 订阅源
│   ├── xuhang-本地极速版.json   # jsDelivr CDN 加速订阅源
│   └── 原作者.json             # 上游参考源
│
├── 🤖 AI全局规范与配置中枢/
│   ├── README.md               # AI 自适应接入指南 (面向未来新 AI 工具的自举协议)
│   ├── AGENTS.md               # 全局统一用户规则总线 (三大核心红线准则)
│   ├── rules/                  # 模块化领域全局准则 (Unity热更安全/Fail-Fast/架构审查)
│   ├── skills/                 # 全局通用工程技能库 (如 unity-engineering 极速编译验证)
│   └── mcp/                    # 全局统一 MCP 工具配置 (如 Chrome DevTools 等)
│
├── .gitignore                  # Git 忽略规则配置
└── README.md                   # 本说明文档
```

---

## 🛠️ 工具详细说明与使用方法

### 1. 🚀 工作流与效率工具 (`工作流与效率工具/`)

- **AI会话历史一键导出工具 (支持 GUI 与 CLI)**
  - **路径**：`工作流与效率工具/AI会话历史一键导出.bat` 或 `工作流与效率工具/AI会话历史一键导出工具/`
  - **用途**：一键自动扫描本机各种 AI Agent、AI 编辑器及扩展插件的本地存储数据，并批量导出为精美的 **完整 Markdown (.md)**、独立离线 **HTML 网页 (.html)**、**✨ 精简优化版 Markdown (.clean.md)**、**📝 精简纯文本 (.clean.txt)**、标准结构化 **JSON** 数据集以及全局导航索引 (**INDEX.md** / **index.html**)。
  - **支持平台**：
    - 🪐 **Google Antigravity** (`~/.gemini/antigravity/brain`)
    - ⚡ **Kiro AI Agent** (`%APPDATA%/Kiro/.../workspace-sessions`)
    - 💼 **腾讯 Workbuddy** (`~/.workbuddy/projects`)
    - 🐙 **VS Code & GitHub Copilot Chat** (`%APPDATA%/Code/User/workspaceStorage`)
    - 🤖 **Cline / Claude Dev / Roo Code** (`%APPDATA%/Code/.../tasks`)
    - 🧠 **Claude Code / CLI** (`~/.claude/projects`)
    - ✨ **Cursor / Windsurf / Trae** (`state.vscdb`)
    - 💬 **Chatbox / Continue / 其他**
  - **特性**：
    - **零依赖开箱即用**：纯 Python 标准库开发，只读扫描安全无损；
    - **✨ 精简优化导出模式**：专供人眼快速阅读与 AI 二次分析（RAG、知识库、Prompt 注入），智能剥离思维链、中间工具调用与系统冗余标记，只保留高信噪比的核心问答；
    - **双模对话实时预览**：GUI 内置「💬 完整原始对话」与「✨ 精简优化文本」双标签页，支持一键将精简文本复制到剪贴板直接投喂给其他大模型；
    - **双模交互**：提供带搜索/过滤/拖拽滚动条的 Tkinter 图形化界面与支持全自动化脚本的 CLI 命令行。
  - **使用方法**：
    - 直接双击 `工作流与效率工具/AI会话历史一键导出.bat` 启动 GUI 界面；
    - 或在终端执行 CLI 命令：
      ```bash
      # 全量导出为 Markdown、HTML 以及精简优化版
      python "工作流与效率工具/AI会话历史一键导出工具/main.py" --all
      # 指定导出工具、精简格式与自定义目录
      python "工作流与效率工具/AI会话历史一键导出工具/main.py" -t claude_code -f md,clean_md,clean_txt -o "D:\MyAIHistory"
      ```

- **项目自动拉取.py**
  - **用途**：Git 多项目高性能安全拉取与子模块协同更新工具（Tkinter 现代化 GUI）。
  - **特性**：
    - **安全防护**：纯只读远端保护（严格拦截 push/config 指令），Safe 模式支持变基冲突自动回滚保护（`rebase --abort` 现场无损）；
    - **并发与加速**：支持多项目多线程并发更新，子模块支持 Git 原生 `--jobs <N>` 并行拉取，支持分支并发探测；
    - **网络韧性**：针对 GitHub/GitLab 偶发网络断流提供智能自动重试机制与超时分级；
    - **子模块深度定制**：支持记录版本 (pinned) / 远端最新 (remote) / 候选分支 (branch) 回退、子模块排除过滤及浅克隆 (`--depth 1`)；
    - **交互与控制**：支持实时进度条、任务中途随时中止、项目搜索过滤、右键快捷菜单（终端/资源管理器打开、单项目更新）与彩色高亮执行日志。
  - **使用方法**：
    ```bash
    python "工作流与效率工具/项目自动拉取.py"
    ```
    或在资源管理器中直接双击运行。

- **打开常用文件夹.py**
  - **用途**：Win32 智能桌面多窗口排列与常用目录展开。
  - **特性**：支持高 DPI 物理像素精确定位、已有 Explorer 窗口复用及多屏幕自适应。
  - **使用方法**：
    ```bash
    python "工作流与效率工具/打开常用文件夹.py"
    ```
  - **依赖**：需要安装 `pywin32`：
    ```bash
    pip install pywin32
    ```

---

### 2. 🌐 网络与文本处理 (`网络与文本处理/`)

- **死链检测与自动注释脚本.py**
  - **路径**：`网络与文本处理/死链检测与自动注释/`
  - **用途**：多线程并发检测 `.txt`、`.md`、`.html` 等文本中的网络链接。
  - **特性**：支持主流网盘（百度网盘、蓝奏云、夸克等）的“软失效”深度页面嗅探；检测到失效链接时自动在行首添加注释标记。
  - **使用方法**：
    ```bash
    cd "网络与文本处理/死链检测与自动注释"
    python "多线程死链检测与自动注释脚本.py"
    ```
  - **依赖**：需要安装 `requests`：
    ```bash
    pip install requests
    ```

---

### 3. 🎵 MusicFree 音源插件 (`MusicFree插件/`)

- **插件文件**：`qq.js`
- **订阅链接**（可在 MusicFree 设置 -> 插件设置 -> 从网络安装插件中直接导入）：
  - **GitHub 直连**：
    ```text
    https://raw.githubusercontent.com/xuhang123456a/MyTools/refs/heads/main/MusicFree%E6%8F%92%E4%BB%B6/qq.js
    ```
  - **国内 CDN 加速**：
    ```text
    https://cdn.jsdelivr.net/gh/xuhang123456a/MyTools@main/MusicFree%E6%8F%92%E4%BB%B6/qq.js
    ```

---

## 🧭 后续新增工具与维护指引

后续如有新的小工具加入，只需按以下步骤维护：

1. **归类存放**：
   - 工作流/AI/Git/系统效率 ➡️ 放入 `工作流与效率工具/`
   - 网络/文本/爬虫 ➡️ 放入 `网络与文本处理/`
   - 音乐/多媒体/特定软件插件 ➡️ 放入 `MusicFree插件/` 或新建对应 `*插件/` 文件夹
   - 其他全新领域 ➡️ 直接在根目录新建对应的**中文分类文件夹**
2. **更新文档**：
   - 在本 `README.md` 的对应分类板块中添加工具名称、用途与使用方法。
