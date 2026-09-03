# 全局 AI 技术栈自适应总线 (Universal AI Tech-Stack Router)

> 本文件是所有 AI 编程助手的**全局技术栈自适应路由器**。
> **⚡ Token 极致能效原则**：本总线不常驻任何具体语言经验。AI 必须根据当前工作区自主识别技术栈，并**按需动态调取**对应的专属规范与技能，严禁在无关项目中加载非对应规则。

---

## 🎯 动态技术栈路由分流 (On-Demand Routing)

### 🎮 1. Unity 游戏开发领域
- **触发条件**：当前工作区存在 `Assets/`、`ProjectSettings/`、`*.csproj` 或正在编写/修改 Unity C# 源码。
- **必须按需调取的专属规范与技能**：
  - **规范**：[rules/unity/unity-standards.md](./rules/unity/unity-standards.md) *(涵盖 Unity 专属 Fail-Fast 原则、架构审查与 HybridCLR 热更安全红线)*
  - **技能**：**`unity-engineering`** *(已全局安装，包含免 Editor 极速编译校验与状态一致性诊断)*

---

### 🪟 2. Windows 脚本开发 (Batch / PowerShell)
- **触发条件**：当前工作区涉及编写、调试或修改 `.bat`、`.cmd`、`.ps1` 脚本。
- **必须按需调取的专属规范 (Rules)**：
  - [rules/windows-scripts/windows-script-standards.md](./rules/windows-scripts/windows-script-standards.md) *(涵盖 CMD 纯 ASCII 双击引导、PowerShell UTF-8 BOM 强制规范、UAC 提权模板与防闪退标准)*

---

### 🌐 3. 其他技术栈 (Python / Web / 后端 等)
- **触发条件**：非上述声明的其他项目。
- **处理规则**：未声明专属经验库的技术栈**直接采用原生精简模式**，严禁加载任何无关规则，实现 0 干扰与 0 冗余 Token 消耗。未来新增经验库将在 `rules/<stack-name>/` 下按需扩展。