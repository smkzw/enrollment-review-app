"""Slice 4.0 能力金标准与坐标 spike 运行器。

运行方式：
    uv run python -m tests.v2.evidence.spike_slice4 [--out <research-dir>] [--gold-root <dir>]

生成确定性合成金标准 -> 用 pdfplumber 提取原生 PDF 字符/词坐标 -> 诚实定位器
逐目标定位 -> 把定位 bbox 换算到渲染页图像素并对照真实绘制区域（IoU） ->
原生 PDF 文本回读一致率/目标定位成功率 -> 风险种子集漏检/误报 ->
把紧凑决策记录写入 ``--out``（默认任务 research 目录）。

扫描/照片/多页 TIFF 的布局候选评估只验证度量机制本身；没有真实布局解析器
坐标输入时不得据此声称 PaddleOCR-VL 已采用（采用与否见 oMLX 门禁探针记录）。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import tempfile
from pathlib import Path

import fitz

from app.domain.contracts.enums import ExtractionRoute, LocatorPrecision
from app.domain.contracts.ocr import LocatorResult
from app.evidence import (
    bbox_overlap_ratio,
    coordinates,
    evaluate_layout_candidates,
    evaluate_locators,
    evaluate_readback,
    evaluate_risk_seed,
    extract_native_page,
    locate_target,
    pdf_points_to_image_pixels,
    scan_ocr_risks,
    text,
)
from tests.v2.evidence.goldgen import A4_HEIGHT, A4_WIDTH, RENDER_DPI, build_gold_set

# 冻结验收门槛（PRD P4-AC06 / P4-AC07 / Slice 4.0）。
READBACK_THRESHOLD = 1.0
NATIVE_LOCATOR_THRESHOLD = 0.95
LAYOUT_LOCATOR_THRESHOLD = 0.90
RISK_MISS_THRESHOLD = 0
RISK_FP_RATE_THRESHOLD = 0.10
COORDINATE_IOU_THRESHOLD = 0.5

PIXELS_PER_POINT = RENDER_DPI / 72.0

DEFAULT_RESEARCH_DIR = (
    Path(__file__).resolve().parents[3]
    / ".trellis"
    / "tasks"
    / "08-19-phase4-evidence-ocr-v2"
    / "research"
)


def _native_coordinate_spike(gold_root: Path, gold_set, locator_results) -> dict:
    """pdfplumber 坐标 -> 渲染页图像素 spike，对照真实绘制区域。"""
    pdf_path = gold_root / "native-01.pdf"
    mapped = 0
    within_bounds = 0
    ious: list[float] = []
    entries: list[dict] = []
    for page in gold_set.pages:
        if page.route != ExtractionRoute.NATIVE_PDF_TEXT:
            continue
        doc = fitz.open(str(pdf_path))
        pix = doc[page.page_number - 1].get_pixmap(
            matrix=fitz.Matrix(PIXELS_PER_POINT, 0, 0, PIXELS_PER_POINT, 0, 0), alpha=False
        )
        image_w, image_h = pix.width, pix.height
        doc.close()
        for target in page.targets:
            result = locator_results.get((page.gold_page_id, target.text))
            if result is None or result.precision != LocatorPrecision.BBOX:
                continue
            mapped += 1
            frame = coordinates.CoordinateFrame(  # type: ignore[attr-defined]
                space=result.coordinate_frame.space,
                page_width=result.coordinate_frame.page_width,
                page_height=result.coordinate_frame.page_height,
                rotation=result.coordinate_frame.rotation,
                transform_version=result.coordinate_frame.transform_version,
            )
            pixel_bbox = pdf_points_to_image_pixels(
                result.bbox, frame, pixels_per_point=PIXELS_PER_POINT
            )
            in_bounds = (
                0 <= pixel_bbox.x0
                and 0 <= pixel_bbox.y0
                and pixel_bbox.x1 <= image_w
                and pixel_bbox.y1 <= image_h
            )
            if in_bounds:
                within_bounds += 1
            iou = None
            if target.expected_pixel_bbox is not None:
                iou = bbox_overlap_ratio(pixel_bbox, target.expected_pixel_bbox)
                ious.append(iou)
            entries.append(
                {
                    "page": page.gold_page_id,
                    "target": target.text,
                    "pdf_bbox": [
                        round(result.bbox.x0, 2),
                        round(result.bbox.y0, 2),
                        round(result.bbox.x1, 2),
                        round(result.bbox.y1, 2),
                    ],
                    "pixel_bbox": [
                        round(pixel_bbox.x0, 2),
                        round(pixel_bbox.y0, 2),
                        round(pixel_bbox.x1, 2),
                        round(pixel_bbox.y1, 2),
                    ],
                    "image_size": [image_w, image_h],
                    "within_bounds": in_bounds,
                    "gold_iou": None if iou is None else round(iou, 4),
                }
            )
    passed_iou = sum(1 for iou in ious if iou is not None and iou >= COORDINATE_IOU_THRESHOLD)
    return {
        "mapped": mapped,
        "within_bounds": within_bounds,
        "min_iou": round(min(ious), 4) if ious else None,
        "avg_iou": round(sum(ious) / len(ious), 4) if ious else None,
        "iou_ge_threshold": passed_iou,
        "iou_total": len(ious),
        "entries": entries,
        "page_size_pt": [A4_WIDTH, A4_HEIGHT],
    }


def _synthetic_layout_candidates(gold_set) -> dict[str, list]:
    """用已知绘制区域构造合成布局候选，验证布局度量机制（非真实解析器）。"""
    from app.evidence import LayoutCandidate

    by_page: dict[str, list] = {}
    for page in gold_set.pages:
        if page.route != ExtractionRoute.VISION_OCR:
            continue
        by_page[page.gold_page_id] = [
            LayoutCandidate(
                page_number=page.page_number,
                bbox=target.expected_pixel_bbox,
                text=target.text,
            )
            for target in page.targets
            if target.expected_pixel_bbox is not None
        ]
    return by_page


def run_spike(out_dir: Path, gold_root: Path | None = None) -> dict:
    gold_root = gold_root or Path(tempfile.mkdtemp()) / "gold"
    gold_set = build_gold_set(gold_root)

    # ---- 原生 PDF：提取 + 回读 + 定位 + 风险 + 坐标 spike ----
    pdf_path = gold_root / "native-01.pdf"
    extracted: dict[str, str] = {}
    locator_results: dict[tuple[str, str], LocatorResult] = {}
    risk_flags: dict[str, list] = {}
    scoped_risk_pages: list[str] = []

    for page in gold_set.pages:
        if page.route == ExtractionRoute.NATIVE_PDF_TEXT:
            native = extract_native_page(pdf_path, page.page_number - 1)
            extracted[page.gold_page_id] = native.text
            text_sha = hashlib.sha256(native.text.encode("utf-8")).hexdigest()
            for target in page.targets:
                locator_results[(page.gold_page_id, target.text)] = locate_target(
                    native,
                    target.text,
                    source_text_sha256=text_sha,
                    page_artifact_id=f"gold-{page.gold_page_id}",
                )
            risk_flags[page.gold_page_id] = scan_ocr_risks(native.text)
            scoped_risk_pages.append(page.gold_page_id)
        elif page.route is None and not page.expects_failure:  # TXT 解码路线
            payload = (gold_root / page.file_ref).read_bytes()
            decoded = text.decode_text_bytes(payload)
            extracted[page.gold_page_id] = decoded.text
            risk_flags[page.gold_page_id] = scan_ocr_risks(decoded.text)
            scoped_risk_pages.append(page.gold_page_id)
        elif not page.expects_failure and page.expected_text is not None:
            # The OCR/layout routes are not run in Slice 4.0 while the oMLX
            # server is unavailable.  Feed the independent gold transcription
            # only to the deterministic risk scanner baseline; this is not an
            # end-to-end OCR or layout capability claim.
            risk_flags[page.gold_page_id] = scan_ocr_risks(page.expected_text)
            scoped_risk_pages.append(page.gold_page_id)

    readback = evaluate_readback(gold_set, extracted)
    locators = evaluate_locators(gold_set, locator_results)
    coord = _native_coordinate_spike(gold_root, gold_set, locator_results)
    layout_candidates = _synthetic_layout_candidates(gold_set)
    layout = evaluate_layout_candidates(gold_set, layout_candidates)
    risk_eval = evaluate_risk_seed(gold_set, risk_flags, page_ids=scoped_risk_pages)

    summary = {
        "gold": {
            "name": gold_set.name,
            "pages": len(gold_set.pages),
            "files": len(gold_set.source_sha256_by_file),
            "file_sha256": dict(gold_set.source_sha256_by_file),
        },
        "readback": {
            "exact": readback.exact_count,
            "total": readback.total,
            "rate": round(readback.rate, 4),
            "pass": readback.rate >= READBACK_THRESHOLD,
            "failures": [p.gold_page_id for p in readback.failures],
        },
        "native_locator": {
            "success": locators.success_count,
            "total": locators.total,
            "rate": round(locators.rate, 4),
            "pass": locators.rate >= NATIVE_LOCATOR_THRESHOLD,
            "failures": [
                {
                    "page": f[0].gold_page_id,
                    "target": f[1].text,
                    "precision": f[2].precision.value if f[2] else None,
                }
                for f in locators.failures
            ],
        },
        "coordinate_spike": coord,
        "layout_candidates": {
            "source": "synthetic_gold_geometry_metric_demo",
            "success": layout.success_count,
            "total": layout.total,
            "rate": round(layout.rate, 4),
            "metric_pass": layout.rate >= LAYOUT_LOCATOR_THRESHOLD,
            "all_regions_valid": layout.all_regions_valid,
            "page_mismatches": layout.page_mismatches,
            "coverage_failures": layout.coverage_failures,
            "text_failures": layout.text_failures,
            "out_of_bounds": layout.out_of_bounds,
        },
        "risk_seed": {
            "miss": risk_eval.miss_count,
            "total_gold_kinds": risk_eval.total_gold_kinds,
            "miss_rate": round(risk_eval.miss_rate, 4),
            "pass_miss": risk_eval.miss_count <= RISK_MISS_THRESHOLD,
            "fp_pages": risk_eval.fp_pages,
            "clean_pages": risk_eval.clean_pages,
            "risk_pages": risk_eval.risk_pages,
            "processed_pages": risk_eval.processed_pages,
            "eligible_pages": risk_eval.eligible_pages,
            "unprocessed_page_ids": list(risk_eval.unprocessed_page_ids),
            "complete": risk_eval.complete,
            "fp_rate": round(risk_eval.fp_rate, 4),
            "pass_fp": risk_eval.fp_rate <= RISK_FP_RATE_THRESHOLD,
        },
        "gate": {
            "readback": readback.rate >= READBACK_THRESHOLD,
            "native_locator": locators.rate >= NATIVE_LOCATOR_THRESHOLD,
            "layout_metric_mechanism": (
                layout.rate >= LAYOUT_LOCATOR_THRESHOLD
                and layout.all_regions_valid
                and not layout.text_failures
            ),
            "layout_adoption": False,
            "risk_miss": risk_eval.miss_count <= RISK_MISS_THRESHOLD,
            "risk_fp": risk_eval.fp_rate <= RISK_FP_RATE_THRESHOLD,
            "risk_coverage": risk_eval.complete,
        },
    }
    return summary


def _write_decision_record(out_dir: Path, summary: dict) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    record = out_dir / "slice4-goldset-coordinate-spike.md"
    g = summary["gold"]
    rb = summary["readback"]
    nl = summary["native_locator"]
    cs = summary["coordinate_spike"]
    lc = summary["layout_candidates"]
    rs = summary["risk_seed"]
    lines = [
        "# Slice 4.0 能力金标准与坐标 spike 决策记录（实测）",
        "",
        "日期：2026-08-19  |  工作树：`phase4-evidence-ocr-v2`  |  只读合成样本，无 PHI",
        "",
        "## 1. 金标准",
        f"- 名称：`{g['name']}`；页面 {g['pages']} 页；文件 {g['files']} 个。",
        "- 覆盖：原生 PDF（唯一/跨行/表格/重复文本）、扫描 PDF、照片、TXT(UTF-8/GB18030)、多页 TIFF、DOCX、失败页（截断 PDF、无效 .doc、损坏图片）。",
        "- 确定性：PDF trailer `/ID` 的十六进制和 literal-string 两种序列化均规范化为固定值；跨进程重复生成由回归测试复核。",
        "- 文件内容 SHA-256：",
        "",
    ]
    for name, sha in sorted(g["file_sha256"].items()):
        lines.append(f"  - `{name}` = `{sha}`")
    lines += [
        "",
        "## 2. 原生 PDF 文本回读一致率",
        f"- 结果：{rb['exact']}/{rb['total']} = **{rb['rate']*100:.1f}%**（门槛 ≥100%）→ {'通过' if rb['pass'] else '未通过'}",
        f"- 失败页：{rb['failures'] or '无'}",
        "",
        "## 3. 目标定位成功率（pdfplumber 原生坐标）",
        f"- 结果：{nl['success']}/{nl['total']} = **{nl['rate']*100:.1f}%**（门槛 ≥95%）→ {'通过' if nl['pass'] else '未通过'}",
        f"- 失败：{nl['failures'] or '无'}",
        "",
        "## 4. pdfplumber 坐标 -> 渲染页图像素 spike",
        f"- 映射 bbox：{cs['mapped']} 个；页内边界通过 {cs['within_bounds']}/{cs['mapped']}。",
        f"- 与真实绘制区域 IoU：min={cs['min_iou']}, avg={cs['avg_iou']}；≥0.5 达标 {cs['iou_ge_threshold']}/{cs['iou_total']}。",
        "- 逐目标映射：",
        "",
    ]
    for e in cs["entries"]:
        lines.append(
            f"  - {e['page']} `{e['target']}` pdf_bbox={e['pdf_bbox']} -> "
            f"pixel_bbox={e['pixel_bbox']} img={e['image_size']} in_bounds={e['within_bounds']} iou={e['gold_iou']}"
        )
    lines += [
        "",
        "## 5. 扫描/照片布局候选度量机制",
        f"- 合成候选定位成功率（度量机制验证，非真实解析器）：{lc['success']}/{lc['total']} = **{lc['rate']*100:.1f}%**（门槛 ≥90%）。",
        f"- 候选来源：`{lc['source']}`；该结果只证明度量机制，不证明任何 OCR/布局解析器能力。",
        f"- 页错位：{lc['page_mismatches'] or '无'}；越界：{lc['out_of_bounds'] or '无'}；文本不匹配：{lc['text_failures'] or '无'}；覆盖失败：{lc['coverage_failures'] or '无'}。",
        "- 结论：布局候选 >=90% 且区域均在正确页并覆盖目标的度量**机制**成立；",
        "  本次门禁选择 GLM 的文字探针未返回机器坐标，因此不采用扫描/照片布局红框；不得以本合成度量冒充布局能力验收（见 `slice4-omlx-gate-probe.md`）。",
        "",
        "## 6. 风险种子集（Slice 4.0 冻结矩阵）",
        "- 原生 PDF/TXT 风险输入来自实际解码文本；扫描/照片/TIFF/DOCX 使用独立编写的合成期望文本，仅验证确定性风险规则，不代表 OCR 推理实测。",
        f"- 关键风险漏检：{rs['miss']} / {rs['total_gold_kinds']}（要求 0）→ {'通过' if rs['pass_miss'] else '未通过'}。",
        f"- 页面级误报：{rs['fp_pages']}/{rs['clean_pages']} 干净页 = **{rs['fp_rate']*100:.1f}%**（≤10%）→ {'通过' if rs['pass_fp'] else '未通过'}。",
        f"- 覆盖：已处理 {rs['processed_pages']}/{rs['eligible_pages']} 页，未处理页：{rs['unprocessed_page_ids'] or '无'}。",
        f"- 参与页：风险页 {rs['risk_pages']}，干净页 {rs['clean_pages']}。",
        "",
        "## 7. 采用/拒绝路径、许可证与诚实降级结论",
        "- 原生 PDF 正式坐标路径：`pdfplumber==0.11.10`（MIT，项目已固定）。本 spike 实测字符/词坐标可回读、可换算到渲染页图像素并对照真实绘制区域。",
        "- 扫描/照片/多页 TIFF：只建立布局候选度量与真实绘制区域对照机制；**未**断言任何 VLM 布局模型已采用。",
        "- 诚实降级：`bbox > text_range > page_excerpt > page_only`；重复文本未稳定消歧必须降级并说明原因，本金标准已包含重复文本降级反例。",
        "- 风险矩阵冻结：极性/数值/小数点/单位/日期 = 阻断（未核对阻止激活）；重复文本/低置信 = 提示（不阻断）。",
        "",
        "## 8. 总门禁",
        (
            f"- 回读 {'✔' if summary['gate']['readback'] else '✘'} | 原生定位 {'✔' if summary['gate']['native_locator'] else '✘'} | "
            f"布局度量机制 {'✔' if summary['gate']['layout_metric_mechanism'] else '✘'}（不等同采用） | "
            f"风险漏检 {'✔' if summary['gate']['risk_miss'] else '✘'} | 风险误报 {'✔' if summary['gate']['risk_fp'] else '✘'} | "
            f"风险覆盖 {'✔' if summary['gate']['risk_coverage'] else '✘'} | 布局采用 {'✔' if summary['gate']['layout_adoption'] else '✘（真实探针无坐标）'}。"
        ),
        "",
        "## 9. 下一步",
        "- Slice 4.1：本次复核不实施；门禁选择 GLM 的文字探针已完成，坐标路线拒绝采用。主控可在既有用户批准边界内另行开启 4.1，但当前树的 4.1 ORM 表尚未有迁移，不能据此记录放行。",
        "- 扫描/照片：门禁文字路线仅在本合成能力样本范围内采用；模型实际加载身份未由独立服务清单证明；布局坐标路线拒绝采用。",
        "",
    ]
    record.write_text("\n".join(lines), encoding="utf-8")

    # 同时写一份机器可读 JSON。
    (out_dir / "slice4-goldset-coordinate-spike.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8"
    )
    return record


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=DEFAULT_RESEARCH_DIR)
    parser.add_argument("--gold-root", type=Path, default=None)
    args = parser.parse_args()
    summary = run_spike(args.out, args.gold_root)
    record = _write_decision_record(args.out, summary)
    print(f"decision record: {record}")
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
