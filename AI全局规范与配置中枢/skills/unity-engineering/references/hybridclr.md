# HybridCLR diagnosis

## Distinguish the mechanisms

- Unity Editor script recompilation/domain reload is an editor workflow.
- HybridCLR runtime hot update loads new managed assemblies against an AOT player.
- Neither mechanism automatically provides state-preserving live hot reload.

## Diagnose in this order

1. Identify the assembly that owns the changed type. If it is compiled into the AOT/player assembly, replacing a hot-update DLL cannot change it.
2. Verify the build pipeline produces the hot-update DLL, versions/delivers it, loads it before use, and invokes types from the loaded assembly.
3. Verify AOT generic metadata supplementation, stripping preservation, and platform restrictions.
4. Check Unity serialization and scene/prefab references. Changing serialized layouts or directly bound component types may require asset/application restart or migration even when method bodies can update.
5. Check existing objects and static state. Loading new code does not recreate old instances or migrate their state.

## Design guidance

- Keep stable Unity-facing adapters in AOT assemblies and move replaceable gameplay/application logic behind interfaces into hot-update assemblies.
- Keep protocol and snapshot formats versioned and backward compatible.
- Describe the result as hot update unless the system explicitly swaps code while preserving and migrating live state.

