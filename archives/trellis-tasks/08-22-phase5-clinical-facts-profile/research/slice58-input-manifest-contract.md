# Slice 5.8 Input Manifest Contract

日期：2026-08-23

## 目的与边界

为本阶段代表病例验收提供**只读源目录盘点**与**隔离复制**合同。工具生成工作区内清单/副本，不写外部原始临床目录，不删除或改写源文件，不给出入排结论，不以 fixture 冒充真实运行。

实现路径：`tools/phase5_acceptance/input_manifest.py`  
确定性测试：`tests/tools/test_phase5_acceptance_input_manifest.py`（仅临时合成树，不读外部临床源）

## 运行时路径合同

| 参数 | 要求 |
|---|---|
| `--source` / `source_roots` | 运行时传入；可重复。本 worker 实现与测试不得硬编码外部临床路径。 |
| `--mode` | 默认 `manifest`（只生成清单）。复制必须显式 `copy`。 |
| `--destination` | 仅 `mode=copy` 允许；不得位于任一 source root 之内（含等于 source root）。 |
| `--output` | 清单 JSON 写入工作区（或调用方指定的非源路径）。 |
| `--execute-copy` | 在 `mode=copy` 下真正执行隔离复制；缺省只生成 `copy_plan`。 |
| `--exclude-kind` | 按本次资料合同显式排除 `photo` 或 `archive`，可重复。默认不排除临床文件类别。D001 本次排除两类；SAR 本次仅排除压缩包。 |
| `--include-path` | 只读取并记录源根目录内明确选中的相对路径；用于从方案目录选择唯一正式方案，不扫描无关文件。 |
| 源不变性 | 默认对清单中每个源文件再哈希核对；失败则中止。 |

## 清单字段

Schema：`phase5.input_manifest.v1`

每个 `entries[]` 项至少包含：

- `relative_path`：相对该 `source_root` 的 POSIX 相对路径（目录结构保留）
- `source_root`：解析后的源根绝对路径
- `sha256`：文件内容 SHA-256
- `size_bytes`：字节大小
- `file_type`：扩展名推导类型（如 `pdf`/`docx`/`photo`/`archive`/`unknown`）
- `decision`：`include` 或 `exclude`
- `reason`：纳入或排除理由（含后缀规则说明）

汇总：`summary.total_files` / `included_files` / `excluded_files` / `copy_plan_entries`。

## 文件选择规则

照片与压缩包是否排除由每次清单显式声明，不能把某项目的一次性要求固化为通用规则。排除决策只依赖路径后缀（大小写不敏感），被排除文件仍进入清单并记录哈希，便于审计“看见但未复制”：

- **照片**：`.jpg` `.jpeg` `.jpe` `.jfif` `.png` `.gif` `.bmp` `.tif` `.tiff` `.webp` `.heic` `.heif` `.raw` `.cr2` `.nef` `.arw` `.dng` `.orf` `.rw2`
- **压缩包**：`.zip` `.rar` `.7z` `.tar` `.tgz` `.gz` `.bz2` `.xz` `.cab` `.lz` `.lzma` `.zst`，以及复合后缀 `.tar.gz` `.tar.bz2` `.tar.xz` `.tar.zst`

系统元数据（`.DS_Store`、AppleDouble）与 Office 临时锁文件始终排除。未显式排除的临床文件默认 `include`。若传入 `--include-path`，仅读取该精确相对路径，不遍历或记录同目录其他文件。符号链接与非普通文件跳过，不进入清单。

## 隔离复制计划

`mode=copy` 时为每个 `include` 项生成 `copy_plan[]`：

- `source_path` → `destination_path`
- 目标相对路径：`{source_root.name}/{relative_path}`，保留相对目录结构，并按源根目录名隔离多根输入
- 执行复制后对目标再算 SHA-256，必须与清单一致
- 工具不得对源路径调用删除、截断或原地改写；复制使用读源 + 写目标

## 安全不变量

1. 默认不复制；无显式 copy mode 时拒绝 `--destination`。
2. destination 与任一 source root 发生任意方向的包含关系 → 拒绝；清单输出写入 source root → 拒绝。
3. 源根之间不得嵌套（避免相对路径歧义）。
4. 源不变性校验与复制哈希校验失败 → 非零退出 / 抛错。
5. 外部原始目录仅作只读输入；写操作限于清单输出与显式隔离目标。

## 验收用法（由 Codex 持有真实源路径）

```bash
# 清单 only（推荐先跑）
uv run python -m tools.phase5_acceptance.input_manifest \
  --source "<RUNTIME_SOURCE_ROOT>" \
  --exclude-kind archive \
  --output "projects/_phase5_acceptance/<label>/input_manifest.json"

# 显式隔离复制
uv run python -m tools.phase5_acceptance.input_manifest \
  --source "<RUNTIME_SOURCE_ROOT>" \
  --mode copy \
  --destination "projects/_phase5_acceptance/<label>/isolated_inputs" \
  --output "projects/_phase5_acceptance/<label>/input_manifest.json" \
  --execute-copy
```

真实 D001 II / MG-K10-SAR III 源路径由 Codex 在工具验收后只读注入；本切片 worker 不读取那些外部路径。

## 与 P5-AC 的关系

本工具只支撑 **P5-AC12/AC13** 所需的隔离输入可审计性，不替代病例级验收账本、浏览器端到端编排或临床核对结论。
