# Unity 代码修改与热更安全规范 (Unity & HybridCLR Hot-Update Standards)

> **优先级：必须严格执行 (Mandatory)**

## 1. 程序集归属判定与热更影响评估
在修改、重构或新增 Unity 项目代码时，必须主动检查修改内容是否会对后续线上热更新造成影响：
- **AOT vs 热更程序集划分**：
  - 检查修改的脚本属于 **AOT 母包程序集**（如主工程、基础底层 SDK、AOT 适配层）还是**热更程序集**（如 `HotUpdate.asmdef`、`Modules.asmdef`）。
  - 若修改涉及 AOT 程序集，必须明确评估并主动告知用户：**此修改需要重新打母包并提审，无法通过纯热更生效**。
- **热更边界隔离**：
  - 将稳定的 Unity 引擎适配层留在 AOT 程序集；
  - 将易变、迭代频繁的玩法与业务逻辑收敛在热更程序集中，通过接口或抽象契约与 AOT 层交互。

## 2. Prefab 序列化与反序列化兼容性
- **严禁随意修改/删除/重命名序列化字段**：
  - 禁止随意修改已被线上预制件 (Prefab) 或 ScriptableObject 序列化的字段（`[SerializeField]` 和 `public` 变量）。
  - 如需重命名，必须添加 `[UnityEngine.Serialization.FormerlySerializedAs("OldFieldName")]` 属性以保证兼容性。
  - 严禁擅自修改字段的数据类型，防止线上反序列化发生引用丢失或内存布局错乱。
- **类名与 GUID 稳定性**：
  - 已被 Prefab 引用的具体 MonoBehaviour / ScriptableObject 类名、文件名及其 `.meta` 文件的 GUID **严禁随意变更**，防止线上产生 Missing Script 致命异常。

## 3. AOT 泛型与元数据补全
- **避免运行时 AOT 泛型实例化异常**：
  - 检查热更代码中是否引入了未在 AOT 母包中实例化的复杂泛型类型/值类型泛型方法（如 `MyStruct<T>`, `Dictionary<Enum, CustomStruct>`）。
  - 确保必要的泛型元数据已在 HybridCLR 的 AOT 补充元数据列表中声明并加载（`LoadMetadataForAOTAssembly`），确保 HybridCLR 运行时平滑执行。

## 4. 主动告知与风险披露机制
- **必须在每次代码调整或重构后向用户提供热更兼容性分析**：
  - 明确指出需要重新编译打包热更的具体 DLL / AssetBundle 名称。
  - 明确指出潜在的风险项（如需重新打包母包、需热更 Prefab、需清理本地旧缓存等）与上线注意事项。