"""Batch source discovery helpers for local eligibility review test runs.

The project phase is an explicit project setting. Do not infer subject inclusion
or study stage from attachment filenames once a project has a fixed stage.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence


SUBJECT_ID_RE = re.compile(r"SA\d{5}", re.IGNORECASE)
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff", ".webp", ".heic", ".gif"}
ARCHIVE_EXTENSIONS = {".zip", ".rar", ".7z", ".tar", ".gz", ".bz2"}
SUPPORTED_REVIEW_EXTENSIONS = {".pdf", ".docx", ".doc"}
PHOTO_KEYWORDS = ("照片", "图片", "皮损照", "皮损照片", "photo", "image")


@dataclass(frozen=True)
class BatchSubjectFolder:
    subject_id: str
    folder: Path
    study_stage: str
    folders: tuple[Path, ...] = ()


@dataclass(frozen=True)
class BatchSourceFile:
    path: Path
    subject_id: str
    category: str
    relative_path: str


def extract_subject_id(text: str) -> str:
    """Return a normalized SAxxxxx subject id from a string, if present."""
    match = SUBJECT_ID_RE.search(text or "")
    return match.group(0).upper() if match else ""


def discover_subject_folders(
    source_root: Path,
    *,
    folder_keyword: str | None = "筛败",
    study_stage: str,
) -> list[BatchSubjectFolder]:
    """Discover subject folders by folder name and attach the fixed project stage.

    This intentionally does not inspect filenames for II/III hints. For a
    phase-scoped project, the user-selected project stage is authoritative.
    """
    source_root = Path(source_root)
    roots_by_subject: dict[str, list[Path]] = {}
    candidates: list[tuple[str, Path]] = []
    for folder in sorted(source_root.rglob("*"), key=lambda p: (len(p.parts), p.as_posix())):
        if not folder.is_dir() or folder.name.startswith("."):
            continue
        if folder_keyword and folder_keyword not in folder.name:
            continue
        subject_id = extract_subject_id(folder.name)
        if not subject_id:
            continue
        if _photoish_path(folder):
            continue
        candidates.append((subject_id, folder))

    for subject_id, folder in candidates:
        roots = roots_by_subject.setdefault(subject_id, [])
        keep: list[Path] = []
        skip_candidate = False
        for existing in roots:
            if _is_relative_to(folder, existing):
                skip_candidate = True
                break
            if _is_relative_to(existing, folder):
                continue
            keep.append(existing)
        if skip_candidate:
            continue
        keep.append(folder)
        roots_by_subject[subject_id] = keep

    folders: list[BatchSubjectFolder] = []
    for subject_id, roots in roots_by_subject.items():
        ordered = tuple(sorted(roots, key=lambda p: (len(p.parts), p.as_posix())))
        if not ordered:
            continue
        folders.append(
            BatchSubjectFolder(
                subject_id=subject_id,
                folder=ordered[0],
                study_stage=study_stage,
                folders=ordered,
            )
        )
    return sorted(folders, key=lambda item: item.subject_id)


def _is_relative_to(path: Path, parent: Path) -> bool:
    try:
        Path(path).relative_to(parent)
        return True
    except ValueError:
        return False


def _photoish_path(path: Path) -> bool:
    lower_parts = [part.lower() for part in Path(path).parts]
    return any(
        keyword in part or keyword.lower() in part
        for part in lower_parts
        for keyword in PHOTO_KEYWORDS
    )


def skip_reason(path: Path) -> str:
    """Return a reason to skip the file, or an empty string when uploadable."""
    path = Path(path)
    name = path.name
    suffix = path.suffix.lower()
    lower_name = name.lower()
    if name.startswith(".") or any(part.startswith(".") for part in path.parts):
        return "hidden/system"
    if _photoish_path(path):
        return "photo/image"
    if suffix in ARCHIVE_EXTENSIONS:
        return "archive"
    if suffix in IMAGE_EXTENSIONS:
        return "photo/image"
    if any(keyword in name or keyword in lower_name for keyword in PHOTO_KEYWORDS):
        return "photo/image"
    if suffix not in SUPPORTED_REVIEW_EXTENSIONS:
        return "unsupported"
    return ""


def category_for_source_file(path: Path) -> str:
    """Classify a retained source file into the app's evidence categories."""
    name = path.name
    rel_text = path.as_posix()
    lower = name.lower()
    if any(kw in name for kw in ("邮件", "沟通", "审核", "合格性", "讨论表")) or "q&a" in lower or "qa" in lower:
        return "enrollment_comm"
    if any(kw in name for kw in ("既往", "病史", "外院", "专科就诊", "处方", "购药")):
        if any(kw in name for kw in ("检验", "检查", "报告", "化验", "CT", "心电", "超声")):
            return "prior_lab"
        return "prior_record"
    if any(kw in name for kw in ("检验", "检查", "报告", "化验", "结核", "T-SPOT", "Tspot", "HBV", "DNA", "CT", "心电", "超声")):
        return "screening_lab"
    if any(kw in name for kw in ("量表", "评分", "PASI", "PGA", "BSA", "体格检查", "生命体征", "身高", "体重")):
        return "screening_record"
    if "筛选" in rel_text or "入组" in rel_text or "知情" in rel_text or "病历" in name:
        return "screening_record"
    return "unknown"


def collect_review_files(folder: Path, subject_id: str) -> tuple[list[BatchSourceFile], list[dict]]:
    """Collect uploadable files from one subject folder with skip diagnostics."""
    return collect_review_files_from_folders([Path(folder)], subject_id)


def collect_review_files_from_folders(
    folders: Sequence[Path],
    subject_id: str,
) -> tuple[list[BatchSourceFile], list[dict]]:
    """Collect uploadable files from one or more subject roots with skip diagnostics."""
    roots = [Path(folder) for folder in folders]
    retained: list[BatchSourceFile] = []
    skipped: list[dict] = []
    seen_hashes: dict[str, str] = {}
    use_root_prefix = len(roots) > 1
    for folder in roots:
        for path in sorted(folder.rglob("*")):
            if not path.is_file():
                continue
            rel = path.relative_to(folder).as_posix()
            display_rel = f"{folder.name}/{rel}" if use_root_prefix else rel
            reason = skip_reason(Path(display_rel))
            if not reason:
                reason = skip_reason(path)
            if reason:
                skipped.append({"path": display_rel, "reason": reason})
                continue
            digest = file_sha256(path)
            if digest in seen_hashes:
                skipped.append({"path": display_rel, "reason": f"duplicate-of:{seen_hashes[digest]}"})
                continue
            seen_hashes[digest] = display_rel
            retained.append(
                BatchSourceFile(
                    path=path,
                    subject_id=subject_id,
                    category=category_for_source_file(path),
                    relative_path=display_rel,
                )
            )
    return retained, skipped


def file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def safe_staged_filename(source_file: BatchSourceFile) -> str:
    """Create a unique flat filename for upload while preserving source context."""
    rel = source_file.relative_path.replace("/", "__")
    rel = re.sub(r"[^\w.\-（）()【】\u4e00-\u9fff]+", "_", rel)
    return rel.strip("._") or source_file.path.name
