# 后端目录结构

## 旧系统现状

- `app/router/`：FastAPI接口；现有项目、受试者、流水线和报告接口。
- `app/pipeline/`：分类、OCR、证据包和自由文本审核器。
- `app/models.py`：旧dataclass和单一overall_verdict。
- `app/llm/`：模型/OCR调用适配。
- `app/shared.py`：旧文件系统状态读写。

这些路径是回归锚点，不是V2新功能的默认归宿。

## V2目标结构

```text
app/
  api/v2/             # 仅HTTP/序列化，调用应用服务
  domain/             # 实体、值对象、状态与纯函数
  workflow/           # Job状态机、步骤、恢复、影响范围
  storage/            # SQLAlchemy模型、仓储、迁移适配
  agents/             # 节点输入输出、PromptVersion、模型适配
  projections/        # 看板、Patient Profile、差异和报告投影
  services/           # 跨实体用例编排，不含HTTP细节
  legacy/             # 逐步封装的只读旧系统适配（需要时）
tests/v2/
  contracts/
  domain/
  workflow/
  agents/
  api/
  clinical_regression/
```

## 依赖方向

`api -> services/workflow -> domain`；`storage`、`agents`实现由上层注入的接口；`projections`只读取已验证结构化状态。`domain`不得导入FastAPI、SQLAlchemy、模型SDK或文件路径。

## 命名

- Python模块和数据库字段使用英文 `snake_case`；领域名称与设计书一致。
- 用户可见中文集中在投影/前端词汇表，不散落在状态机内部。
- 不创建 `utils.py` 大杂烩；工具放在拥有该概念的模块旁。

## 示例

- 旧接口薄入口：`app/router/health.py`。
- 需要被V2替代的反例：`app/router/pipeline.py` 让SSE请求拥有任务生命期；`app/pipeline/reviewer.py` 用正则修复模型结论。
