# 全局 AI 技术栈自适应总线 (Universal AI Tech-Stack Router)

> 本文件是所有 AI 编程助手的**全局技术栈自适应路由器**。
> **⚡ Token 极致能效原则**：本总线不常驻任何具体语言经验。AI 必须根据当前工作区自主识别技术栈，并**按需动态调取**对应的专属技能，严禁在无关项目中加载非对应规则。

---

## 🎯 动态技术栈路由分流 (On-Demand Routing)

### 🎮 1. Unity 游戏开发领域
- **触发条件**：当前工作区存在 `Assets/`、`ProjectSettings/`、`*.csproj` 或正在编写/修改 Unity C# 源码。
- **必须调用的专属技能 (Skill)**：
  - **`unity-engineering`** *(已全局安装，包含 Unity Fail-Fast 规范、架构审查、HybridCLR 热更安全红线、状态一致性与免 Editor 极速编译校验)*。
  - 直接激活并遵循全局安装的 `unity-engineering` 技能及其内部手册。

---

### 🌐 2. 其他技术栈 (Python / Web / 后端 等)
- **触发条件**：非 Unity 的其他项目。
- **处理规则**：未声明专属经验库的技术栈**直接采用原生精简模式**，严禁加载任何 Unity 规则，实现 0 干扰与 0 冗余 Token 消耗。未来新增经验库将以对应专属 Skill 形式按需扩展。