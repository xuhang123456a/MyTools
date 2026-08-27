# 全局 AI 技术栈自适应总线 (Universal AI Tech-Stack Router)

> 本文件是所有 AI 编程助手的**全局技术栈自适应路由器**。
> **⚡ Token 极致能效原则**：本总线不常驻任何具体语言经验。AI 必须根据当前工作区自主识别技术栈，并**按需动态调取**对应的专属规则与技能，严禁在无关项目中加载非对应规则。

---

## 🎯 动态技术栈路由分流 (On-Demand Routing)

### 🎮 1. Unity 游戏开发领域
- **触发条件**：当前工作区存在 `Assets/`、`ProjectSettings/`、`*.csproj` 或正在编写/修改 Unity C# 源码。
- **必须按需调取的专属规范 (Rules)**：
  - [rules/unity/unity-standards.md](./rules/unity/unity-standards.md) *(涵盖 Unity 专属 Fail-Fast 原则、架构审查与 HybridCLR 热更安全红线)*
- **必须按需调取的专属技能 (Skill)**：
  - [skills/unity-engineering/SKILL.md](./skills/unity-engineering/SKILL.md) *(免 Editor 极速 Roslyn 编译校验与状态一致性诊断)*

---

### 🌐 2. 其他技术栈 (Python / Web / 后端 等)
- **触发条件**：非 Unity 的其他项目。
- **处理规则**：未声明专属经验库的技术栈**直接采用原生精简模式**，严禁加载任何 Unity 规则，实现 0 干扰与 0 冗余 Token 消耗。未来新增经验库将在 `rules/<stack-name>/` 下按需扩展。