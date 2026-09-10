"""Architecture and compatibility checks for the legacy Markdown reviewer."""
from __future__ import annotations

import ast
from pathlib import Path

from app.pipeline import reviewer


ROOT = Path(__file__).resolve().parents[2]


LEGACY_IMPORT = "app.pipeline.reviewer"
V2_SOURCE_ROOTS = (
    ROOT / "app" / "api" / "v2",
    ROOT / "app" / "domain",
    ROOT / "app" / "protocols",
    ROOT / "app" / "agents",
    ROOT / "app" / "services",
)


def _imports_legacy_reviewer(path: Path) -> list[int]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    lines: list[int] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            if any(alias.name == LEGACY_IMPORT for alias in node.names):
                lines.append(node.lineno)
        elif isinstance(node, ast.ImportFrom):
            if node.module == LEGACY_IMPORT:
                lines.append(node.lineno)
    return lines


def test_legacy_reviewer_declares_explicit_one_way_boundary() -> None:
    assert reviewer.LEGACY_REVIEWER_BOUNDARY == "legacy_only"
    assert reviewer.LEGACY_REVIEWER_CONTRACT_VERSION == "legacy/reviewer-markdown/v1"
    assert reviewer.LEGACY_REVIEWER_V2_IMPORTS_ALLOWED is False
    assert {
        "free_text_trigger_semantics",
        "project_specific_rule_text",
        "disease_indicator_text",
        "historical_source_text",
    } <= reviewer._LEGACY_REVIEWER_HEURISTICS


def test_structured_v2_modules_never_import_legacy_reviewer() -> None:
    violations: list[str] = []
    for root in V2_SOURCE_ROOTS:
        for path in root.rglob("*.py"):
            lines = _imports_legacy_reviewer(path)
            violations.extend(f"{path.relative_to(ROOT)}:{line}" for line in lines)
    assert violations == []


def test_structured_protocol_chain_imports_typed_control_contracts() -> None:
    structured_modules = (
        ROOT / "app" / "agents" / "protocol_control_deconstructor.py",
        ROOT / "app" / "protocols" / "protocol_control_planning.py",
        ROOT / "app" / "protocols" / "protocol_control_gate.py",
    )
    for path in structured_modules:
        source = path.read_text(encoding="utf-8")
        assert "app.domain.contracts.protocol_controls" in source
        assert LEGACY_IMPORT not in source


def test_legacy_markdown_parser_remains_compatible() -> None:
    raw = """### 逐条审核结果
| 规则ID | 规则名称 | 类型 | 判定结果 | 推理依据 |
|--------|----------|------|----------|----------|
| EX-01 | 合成兼容性规则 | 排除 | ❌不通过 | 触发判断：已触发。来源记录明确满足本条方案条件。 |

### 总结论
判定结果：fail
"""

    parsed = reviewer.parse_review_response(raw)

    assert parsed["overall_verdict"] == "fail"
    assert parsed["rule_results"][0].rule_id == "EX-01"
    assert parsed["rule_results"][0].verdict == "fail"
