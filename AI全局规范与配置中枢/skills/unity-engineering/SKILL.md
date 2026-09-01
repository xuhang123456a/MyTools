---
name: unity-engineering
description: Efficient Unity C# diagnosis, implementation, and validation. Use for Unity Fail-Fast principles, architecture reviews, HybridCLR hot-update safety, deterministic gameplay RNG, state consistency, or targeted Roslyn compiler checks.
---

# Unity Engineering Skill

Use the narrowest verification that proves the changed layer.

## 1. 核心架构与准则 (Core Engineering Principles)

- **Fail-Fast 原则**：严禁在 Mono/Prefab 核心依赖上添加无意义的判空或手工抛异常；直接使用核心依赖，让 Unity 自然产生的 `NullReferenceException` / `MissingReferenceException` 暴露真实调用栈。
- **架构先导 (Architecture-First)**：单一职责 (SRP)、表现层与数据层解耦、视图黑盒自治（对外提供自闭环生命周期契约，禁止外部侵入操作内部节点与动效）、知其所以然 (讲透 Design Rationale)。
- **交互生命周期与事件链完整性**：表现接管与实例销毁严格分相，严禁在活跃事件派发中执行破坏性销毁；异步退出上下文感知分流，配合物理输入自愈异常状态机。
- **完整工程规范手册**：深入细节请直接查阅 `references/unity-standards.md`。

## 2. 编译校验工作流 (Compile Validation)

1. Read repository instructions and identify the Unity version and assembly containing the changed files.
2. Treat Unity-generated `.csproj` files as IDE metadata unless the repository explicitly supports `dotnet build`. Do not edit them.
3. If system `dotnet build` hits established third-party/framework errors, do not retry it. Separate that baseline from current-change errors.
4. For self-contained source roots, run `scripts/validate-unity-sources.ps1` with the owning generated project. It uses Unity's bundled host/compiler and a response file, avoiding system-SDK semantics and Windows command-length limits.
5. Lifecycle code, asmdef boundaries, Editor code, prefabs, scenes, and serialized bindings ultimately require Unity Editor validation, but **Assets Refresh and Editor compilation are performed by the user**. Do not control Windows or Unity, trigger Assets Refresh, clear/read the Console, or spend tokens automating the Editor. Complete the narrow source validation available to Codex, report its exact scope, and leave Editor validation explicitly pending for the user.

### 命令行调用示例：

```powershell
powershell -ExecutionPolicy Bypass -File <本技能目录>/scripts/validate-unity-sources.ps1 `
  -ProjectRoot <项目根路径> `
  -AssemblyProject <程序集项目名称.csproj> `
  -SourceRoot 'Assets/Scripts/Game/Domain;Assets/Scripts/Game/Config'
```

## 3. 专项参考手册路由 (Specialized References)

- **对于 RNG 确定性、快照、Undo/Redo 撤销机制、计分/进度、技能动作、UI 可用性锁**：查阅 `references/state-consistency.md`。
- **对于 HybridCLR、热更新、AOT 程序集归属、热重载**：查阅 `references/hybridclr.md`。
- **对于 Unity 专属 Fail-Fast 与架构准则**：查阅 `references/unity-standards.md`。

Keep fixes semantic: model the domain action and its transaction boundary instead of keying logic to a button, animation, or incidental field mutation.
