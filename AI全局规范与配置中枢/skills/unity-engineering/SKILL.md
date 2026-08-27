---
name: unity-engineering
description: Efficient Unity C# diagnosis, implementation, and validation. Use for Unity-generated csproj build failures, targeted Roslyn checks, deterministic gameplay RNG, snapshots and undo, progression semantics, UI interaction locks, or HybridCLR hot-update architecture.
---

# Unity Engineering Skill

Use the narrowest verification that proves the changed layer.

## 1. 编译验证 (Compile routing)

1. Read repository instructions and identify the Unity version and assembly containing the changed files.
2. Treat Unity-generated `.csproj` files as IDE metadata unless the repository explicitly supports `dotnet build`. Do not edit them.
3. If system `dotnet build` hits established third-party/framework errors, do not retry it. Separate that baseline from current-change errors.
4. For self-contained source roots, run `scripts/validate-unity-sources.ps1` with the owning generated project. It uses Unity's bundled host/compiler and a response file, avoiding system-SDK semantics and Windows command-length limits.
5. Use Unity Editor compilation for lifecycle code, asmdef boundaries, Editor code, `GameSimulator`-style cross-layer code, prefabs, scenes, or serialized bindings. Report the exact validated scope; never call a partial check a full project build.

### 命令行调用示例：

```powershell
powershell -ExecutionPolicy Bypass -File ~/.ai/skills/unity-engineering/scripts/validate-unity-sources.ps1 `
  -ProjectRoot <项目路径> `
  -AssemblyProject <程序集项目名称.csproj> `
  -SourceRoot 'Assets/Scripts/Game/Domain;Assets/Scripts/Game/Config' `
  -Exclude '*GameSimulator.cs'
```

## 2. 架构与规范路由 (Architecture routing)

- **对于 RNG 确定性、快照快照、Undo/Redo 撤销机制、计分/进度、技能动作、UI 可用性锁**：必须查阅并遵循 `references/state-consistency.md`。
- **对于 HybridCLR、热更新、AOT 程序集归属、热重载**：必须查阅并遵循 `references/hybridclr.md`。

Keep fixes semantic: model the domain action and its transaction boundary instead of keying logic to a button, animation, or incidental field mutation.