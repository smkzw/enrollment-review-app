# Phase 0.5 依赖增补

**jsonschema 4.26.0**

- 许可证：MIT。
- 来源：PyPI 元数据与官方仓库 `python-jsonschema/jsonschema`。
- 用途：独立验证 Pydantic 生成的 JSON Schema 和 `fixture/v1`，仅属于开发测试组。
- 替代方案：只用 Pydantic 回读会让“生成的 Schema 本身是否可被独立实现消费”缺少第二验证器，因此不采纳。
- 数据边界：仅验证本地合成 fixture，不发送任何临床资料。
- 移除：删除开发依赖和独立 Schema 验证测试，不影响产品运行时；但 Phase 0.5 Schema 门槛将失去独立证据。
