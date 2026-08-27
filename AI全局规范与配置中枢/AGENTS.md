# 全局统一 AI 系统级规范与工程标准 (Universal AI Agent Guidelines)

> 本文件是所有 AI 编程助手（Antigravity, OpenAI Codex, Claude Code, Cursor, Windsurf, GitHub Copilot, Cline 等）的**全局单一事实来源 (Single Source of Truth)**。

---

## 一、 核心执行准则 (Core Principles)

### 1. Unity 代码修改与热更安全规范（必须执行）
- **热更影响评估**：在修改、重构或新增 Unity 项目代码时，必须主动检查修改内容是否会对后续线上热更新造成影响。
  - **程序集归属判定**：检查修改的脚本属于 AOT 母包程序集还是热更程序集（如 `HotUpdate.asmdef` / `Modules.asmdef`），评估是否需要重新提审母包。
  - **Prefab 序列化兼容性**：禁止随意修改、删除或重命名已被线上预制件序列化的字段（`[SerializeField]` 和 `public` 变量），防止线上反序列化引用丢失。
  - **类名与 GUID 稳定性**：已被 Prefab 引用的具体 MonoBehaviour 类名、文件名及其 `.meta` 文件的 GUID 严禁随意变更，防止线上产生 Missing Script 致命异常。
  - **AOT 泛型与元数据膨胀**：检查是否引入了未被 AOT 泛型收集的复杂泛型实例，确保 HybridCLR 运行时能平滑加载。
- **主动告知风险项**：每次完成代码调整或重构后，必须主动向用户分析热更兼容性，指出需要打包热更的具体 DLL / AssetBundle 以及潜在的风险项与注意事项。

### 2. 代码审查与架构指导原则
- **深入架构设计层面**：在对用户代码进行 Review、重构或方案设计时，多从**架构设计、单一职责（SRP）、解耦与复用、生命周期管理、设计模式（如组合、观察者、策略等）**等宏观维度提供专业建议与指导。
- **知其然且知其所以然**：不仅指出问题或给出修改代码，更要清晰讲透背后的设计考量（Design Rationale）、性能代价与扩展性收益，积极帮助用户提升系统级架构视野与编程能力。
- **保持代码风格简洁干练**：深度贴合项目原有的编码习惯与规范，非必要不引入过多冗余的防御性代码（如层层嵌套的判空），保持代码结构的精简与高可读性。

### 3. 拒绝冗余防御性代码与贯彻快速失败原则 (Fail-Fast)
- **严禁无意义的防御性判空**：对于系统/玩法运行所必需的核心依赖（如预制件绑定的核心组件、已初始化的状态机/数据对象、核心 UI 节点等），若其为 `null` 意味着游戏配置或生命周期流程已被严重破坏，必须**直接抛出异常、立即暴露问题（Fail-Fast）**，严禁使用层层嵌套的 `if (obj != null)` 进行防御性包裹与静默兜底。
- **兜底掩盖的危害性**：盲目兜底只会让严重错误被静默吞掉，导致后续出现数据不一致、流程卡死等更隐蔽且极难排查的次生 Bug。
- **合理判空的边界**：仅在业务逻辑上确实存在“合法/预期内的空状态”（如弱引用生命周期、已触发异步取消的实例、可选配置/插件插槽等）时，才编写针对性的空状态处理。

---

## 二、 可用技能库 (Available Skills)

系统在 `D:/MyTools/AI全局规范与配置中枢/skills/` 目录下提供了标准化工程技能。在执行特定任务前，请主动查阅对应技能的 `SKILL.md`：

| 技能名称 | 路径 | 适用场景与触发条件 |
| :--- | :--- | :--- |
| **unity-engineering** | `D:/MyTools/AI全局规范与配置中枢/skills/unity-engineering/SKILL.md` | Unity C# 源码极速免 Editor 编译验证、HybridCLR 热更安全排查、确定性 RNG / Undo 撤销事务 / UI 可用性锁设计 |

### 技能调用示例 (Unity 免 Editor 编译验证):
```powershell
powershell -ExecutionPolicy Bypass -File D:/MyTools/AI全局规范与配置中枢/skills/unity-engineering/scripts/validate-unity-sources.ps1 `
  -ProjectRoot <项目根路径> `
  -AssemblyProject <目标csproj文件名> `
  -SourceRoot <修改的代码目录>
```

---

## 三、 模块化规则参考索引 (Detailed Rules)
- 详细架构与审查规范：`D:/MyTools/AI全局规范与配置中枢/rules/code-review.md`
- 详细 Unity 热更与 Prefab 兼容规范：`D:/MyTools/AI全局规范与配置中枢/rules/unity-hotupdate.md`
- 详细 Fail-Fast 与代码风格规范：`D:/MyTools/AI全局规范与配置中枢/rules/global-standards.md`