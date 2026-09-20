"""Phase 5 acceptance ledger and case-level structural verifier (Slice 5.8).

Machine-readable P5-AC01..P5-AC13 ledger that separates:

- ``deterministic`` — automated / structural checks
- ``clinical_manual`` — human clinical reconciliation against source
- ``browser_tester`` — independent real-browser tester evidence
- ``conference_advisory`` — architecture/clinical-logic challenge only

Overall ``pass`` is rejected when any required ``clinical_manual`` or
``browser_tester`` class is absent, even if every deterministic check is green.
Conference advisory never substitutes for tester or clinical evidence.
This module never fabricates real-case clinical entries and never emits an
enrollment conclusion.
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

__all__ = [
    "ACCEPTANCE_CRITERIA",
    "CRITERION_IDS",
    "EVIDENCE_CLASSES",
    "PASSING_DISPOSITIONS_BY_CLASS",
    "SCHEMA_VERSION",
    "CaseIdentity",
    "CaseStructuralObservation",
    "CaseStructuralVerifier",
    "EvidenceItem",
    "LedgerEvaluationError",
    "LedgerValidationError",
    "build_empty_ledger",
    "evaluate_ledger",
    "ledger_schema_path",
    "load_ledger",
    "record_evidence",
    "validate_ledger_document",
]

SCHEMA_VERSION = "phase5_acceptance_ledger/v1"

EVIDENCE_CLASSES: tuple[str, ...] = (
    "deterministic",
    "clinical_manual",
    "browser_tester",
    "conference_advisory",
)

DISPOSITIONS: tuple[str, ...] = (
    "pass",
    "fail",
    "blocked",
    "not_run",
    "observed_only",
    "advisory",
)

# Dispositions that satisfy a required evidence class for that class only.
PASSING_DISPOSITIONS_BY_CLASS: dict[str, frozenset[str]] = {
    "deterministic": frozenset({"pass"}),
    "clinical_manual": frozenset({"pass"}),
    "browser_tester": frozenset({"pass"}),
    # Advisory may only satisfy conference_advisory; never clinical/tester.
    "conference_advisory": frozenset({"pass", "advisory"}),
}

CRITERION_IDS: tuple[str, ...] = tuple(f"P5-AC{i:02d}" for i in range(1, 14))

# Required evidence classes per PRD acceptance criterion.
# clinical_manual / browser_tester where the criterion demands human or
# independent tester proof; conference_advisory only on P5-AC13.
ACCEPTANCE_CRITERIA: dict[str, dict[str, Any]] = {
    "P5-AC01": {
        "title": "权威链",
        "required_evidence_classes": ("deterministic", "clinical_manual"),
    },
    "P5-AC02": {
        "title": "来源回放",
        "required_evidence_classes": ("browser_tester", "clinical_manual"),
    },
    "P5-AC03": {
        "title": "沉默与否定",
        "required_evidence_classes": ("deterministic", "clinical_manual"),
    },
    "P5-AC04": {
        "title": "来源强度",
        "required_evidence_classes": ("deterministic", "clinical_manual"),
    },
    "P5-AC05": {
        "title": "日期范围",
        "required_evidence_classes": ("deterministic",),
    },
    "P5-AC06": {
        "title": "重复与冲突",
        "required_evidence_classes": ("deterministic",),
    },
    "P5-AC07": {
        "title": "期望覆盖",
        "required_evidence_classes": ("deterministic",),
    },
    "P5-AC08": {
        "title": "增量与历史",
        "required_evidence_classes": ("deterministic", "browser_tester"),
    },
    "P5-AC09": {
        "title": "Profile 内容",
        "required_evidence_classes": ("deterministic", "browser_tester"),
    },
    "P5-AC10": {
        "title": "真实运行",
        "required_evidence_classes": ("deterministic", "browser_tester"),
    },
    "P5-AC11": {
        "title": "恢复与幂等",
        "required_evidence_classes": ("deterministic",),
    },
    "P5-AC12": {
        "title": "代表性核对",
        "required_evidence_classes": ("clinical_manual",),
    },
    "P5-AC13": {
        "title": "独立审查与试用",
        "required_evidence_classes": ("conference_advisory", "browser_tester"),
    },
}


class LedgerValidationError(ValueError):
    """Ledger document is structurally invalid or violates ledger rules."""


class LedgerEvaluationError(ValueError):
    """Ledger cannot be evaluated (incomplete identity or fabricated flag)."""


@dataclass(frozen=True)
class CaseIdentity:
    case_id: str
    project_label: str = ""
    subject_label: str = ""
    isolation_root: str = ""
    database_path: str | None = None
    project_id: str | None = None
    subject_id: str | None = None
    review_episode_id: str | None = None
    fabricated: bool = False

    def to_dict(self) -> dict[str, Any]:
        if self.fabricated:
            raise LedgerValidationError(
                "fabricated case identities are forbidden; do not invent real-case entries"
            )
        return {
            "case_id": self.case_id,
            "project_label": self.project_label,
            "subject_label": self.subject_label,
            "isolation_root": self.isolation_root,
            "database_path": self.database_path,
            "project_id": self.project_id,
            "subject_id": self.subject_id,
            "review_episode_id": self.review_episode_id,
            "fabricated": False,
        }


@dataclass(frozen=True)
class EvidenceItem:
    evidence_class: str
    source_locator: str
    artifact: str
    observed_result: str
    verifier: str
    timestamp: str
    disposition: str
    notes: str = ""

    def __post_init__(self) -> None:
        if self.evidence_class not in EVIDENCE_CLASSES:
            raise LedgerValidationError(
                f"unknown evidence_class={self.evidence_class!r}; "
                f"expected one of {EVIDENCE_CLASSES}"
            )
        if self.disposition not in DISPOSITIONS:
            raise LedgerValidationError(
                f"unknown disposition={self.disposition!r}; expected one of {DISPOSITIONS}"
            )
        for field_name in (
            "source_locator",
            "artifact",
            "observed_result",
            "verifier",
            "timestamp",
        ):
            if not str(getattr(self, field_name)).strip():
                raise LedgerValidationError(f"{field_name} must be non-empty")
        if self.disposition == "advisory" and self.evidence_class != "conference_advisory":
            raise LedgerValidationError(
                "disposition=advisory is only valid for conference_advisory evidence"
            )

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "evidence_class": self.evidence_class,
            "source_locator": self.source_locator,
            "artifact": self.artifact,
            "observed_result": self.observed_result,
            "verifier": self.verifier,
            "timestamp": self.timestamp,
            "disposition": self.disposition,
        }
        if self.notes:
            payload["notes"] = self.notes
        return payload


@dataclass(frozen=True)
class CaseStructuralObservation:
    """Structural DB/file/locator observation — never a clinical judgment."""

    check_id: str
    source_locator: str
    artifact: str
    observed_result: str
    disposition: str
    notes: str = ""

    def as_evidence(
        self,
        *,
        verifier: str,
        timestamp: str | None = None,
    ) -> EvidenceItem:
        return EvidenceItem(
            evidence_class="deterministic",
            source_locator=self.source_locator,
            artifact=self.artifact,
            observed_result=self.observed_result,
            verifier=verifier,
            timestamp=timestamp or _utc_now(),
            disposition=self.disposition,
            notes=(
                f"{self.notes} "
                "[structural only; does not claim clinical correctness]"
            ).strip(),
        )


def ledger_schema_path() -> Path:
    return Path(__file__).with_name("ledger.schema.json")


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def build_empty_ledger(
    case: CaseIdentity,
    *,
    evaluated_at: str | None = None,
) -> dict[str, Any]:
    """Build a ledger skeleton with all 13 criteria and empty evidence.

    Does not invent clinical observations. Criterion dispositions start as
    ``not_run``. Overall disposition is ``not_run``.
    """
    if case.fabricated:
        raise LedgerValidationError("refusing to build ledger for fabricated=True case")
    stamp = evaluated_at or _utc_now()
    criteria: list[dict[str, Any]] = []
    for criterion_id in CRITERION_IDS:
        meta = ACCEPTANCE_CRITERIA[criterion_id]
        criteria.append(
            {
                "criterion_id": criterion_id,
                "title": meta["title"],
                "required_evidence_classes": list(meta["required_evidence_classes"]),
                "evidence": [],
                "criterion_disposition": "not_run",
                "blocking_reasons": [
                    f"missing required evidence_class={cls}"
                    for cls in meta["required_evidence_classes"]
                ],
            }
        )
    ledger = {
        "schema_version": SCHEMA_VERSION,
        "case": case.to_dict(),
        "criteria": criteria,
        "overall": {
            "disposition": "not_run",
            "deterministic_all_green": False,
            "clinical_manual_complete": False,
            "browser_tester_complete": False,
            "conference_advisory_present": False,
            "blocking_reasons": [
                "ledger has no recorded evidence yet; overall pass is forbidden"
            ],
            "evaluated_at": stamp,
        },
    }
    return evaluate_ledger(ledger, evaluated_at=stamp)


def record_evidence(
    ledger: Mapping[str, Any],
    criterion_id: str,
    item: EvidenceItem | Mapping[str, Any],
    *,
    evaluated_at: str | None = None,
) -> dict[str, Any]:
    """Append one evidence item and re-evaluate dispositions."""
    if criterion_id not in ACCEPTANCE_CRITERIA:
        raise LedgerValidationError(f"unknown criterion_id={criterion_id!r}")
    evidence = item if isinstance(item, EvidenceItem) else EvidenceItem(**dict(item))
    document = json.loads(json.dumps(ledger))  # deep copy via JSON
    for criterion in document["criteria"]:
        if criterion["criterion_id"] == criterion_id:
            criterion["evidence"].append(evidence.to_dict())
            break
    else:
        raise LedgerValidationError(f"criterion {criterion_id} missing from ledger")
    return evaluate_ledger(document, evaluated_at=evaluated_at)


def load_ledger(path: str | Path) -> dict[str, Any]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    return evaluate_ledger(payload)


def validate_ledger_document(document: Mapping[str, Any]) -> list[str]:
    """Return structural validation errors (empty list means OK)."""
    errors: list[str] = []
    if document.get("schema_version") != SCHEMA_VERSION:
        errors.append(
            f"schema_version must be {SCHEMA_VERSION!r}, got {document.get('schema_version')!r}"
        )
    case = document.get("case")
    if not isinstance(case, Mapping):
        errors.append("case must be an object")
    else:
        if case.get("fabricated") is not False:
            errors.append("case.fabricated must be false; real-case fabrication is forbidden")
        if not str(case.get("case_id") or "").strip():
            errors.append("case.case_id must be non-empty")
    criteria = document.get("criteria")
    if not isinstance(criteria, list):
        errors.append("criteria must be an array")
        return errors
    seen: list[str] = []
    for row in criteria:
        if not isinstance(row, Mapping):
            errors.append("each criterion must be an object")
            continue
        cid = row.get("criterion_id")
        if cid not in ACCEPTANCE_CRITERIA:
            errors.append(f"unknown criterion_id={cid!r}")
            continue
        seen.append(str(cid))
        expected = list(ACCEPTANCE_CRITERIA[str(cid)]["required_evidence_classes"])
        actual = list(row.get("required_evidence_classes") or [])
        if actual != expected:
            errors.append(
                f"{cid} required_evidence_classes must be {expected}, got {actual}"
            )
        evidence = row.get("evidence")
        if not isinstance(evidence, list):
            errors.append(f"{cid} evidence must be an array")
            continue
        for idx, item in enumerate(evidence):
            if not isinstance(item, Mapping):
                errors.append(f"{cid} evidence[{idx}] must be an object")
                continue
            try:
                EvidenceItem(
                    evidence_class=str(item.get("evidence_class", "")),
                    source_locator=str(item.get("source_locator", "")),
                    artifact=str(item.get("artifact", "")),
                    observed_result=str(item.get("observed_result", "")),
                    verifier=str(item.get("verifier", "")),
                    timestamp=str(item.get("timestamp", "")),
                    disposition=str(item.get("disposition", "")),
                    notes=str(item.get("notes") or ""),
                )
            except LedgerValidationError as exc:
                errors.append(f"{cid} evidence[{idx}]: {exc}")
    missing = [cid for cid in CRITERION_IDS if cid not in seen]
    if missing:
        errors.append(f"missing criteria: {missing}")
    if len(seen) != len(set(seen)):
        errors.append("duplicate criterion_id entries are forbidden")
    extra = [cid for cid in seen if cid not in CRITERION_IDS]
    if extra:
        errors.append(f"unexpected criteria: {extra}")
    if len(seen) != 13:
        errors.append(f"criteria must enumerate all 13 acceptance ids, found {len(seen)}")
    return errors


def _class_satisfied(evidence_rows: Sequence[Mapping[str, Any]], evidence_class: str) -> bool:
    allowed = PASSING_DISPOSITIONS_BY_CLASS[evidence_class]
    for row in evidence_rows:
        if row.get("evidence_class") != evidence_class:
            continue
        if row.get("disposition") in allowed:
            return True
    return False


def _class_has_fail(evidence_rows: Sequence[Mapping[str, Any]], evidence_class: str) -> bool:
    return any(
        row.get("evidence_class") == evidence_class and row.get("disposition") == "fail"
        for row in evidence_rows
    )


def _evaluate_criterion(row: Mapping[str, Any]) -> tuple[str, list[str]]:
    criterion_id = str(row["criterion_id"])
    required = list(ACCEPTANCE_CRITERIA[criterion_id]["required_evidence_classes"])
    evidence = list(row.get("evidence") or [])
    reasons: list[str] = []

    for cls in required:
        if _class_has_fail(evidence, cls):
            reasons.append(f"{cls} evidence disposition=fail")
        elif not _class_satisfied(evidence, cls):
            reasons.append(f"missing required evidence_class={cls}")

    if any("disposition=fail" in reason for reason in reasons):
        return "fail", reasons
    if reasons:
        if any(
            item.get("disposition") == "blocked"
            for item in evidence
            if item.get("evidence_class") in required
        ):
            return "blocked", reasons
        if evidence:
            return "blocked", reasons
        return "not_run", reasons
    return "pass", []


def evaluate_ledger(
    document: Mapping[str, Any],
    *,
    evaluated_at: str | None = None,
) -> dict[str, Any]:
    """Recompute criterion and overall dispositions.

    Hard rule: overall ``pass`` requires every criterion to pass, including all
    required ``clinical_manual`` and ``browser_tester`` classes. Deterministic
    all-green alone never yields overall pass when those classes are required
    anywhere in the ledger.
    """
    errors = validate_ledger_document(document)
    if errors:
        raise LedgerValidationError("; ".join(errors))

    stamp = evaluated_at or _utc_now()
    out = json.loads(json.dumps(document))
    criteria_out: list[dict[str, Any]] = []
    by_id = {row["criterion_id"]: row for row in out["criteria"]}
    for criterion_id in CRITERION_IDS:
        row = dict(by_id[criterion_id])
        row["title"] = ACCEPTANCE_CRITERIA[criterion_id]["title"]
        row["required_evidence_classes"] = list(
            ACCEPTANCE_CRITERIA[criterion_id]["required_evidence_classes"]
        )
        disposition, reasons = _evaluate_criterion(row)
        row["criterion_disposition"] = disposition
        row["blocking_reasons"] = reasons
        criteria_out.append(row)
    out["criteria"] = criteria_out

    required_clinical = _required_classes_complete(criteria_out, "clinical_manual")
    required_tester = _required_classes_complete(criteria_out, "browser_tester")
    required_deterministic = _required_classes_complete(criteria_out, "deterministic")
    advisory_present = _required_classes_complete(criteria_out, "conference_advisory")

    blocking: list[str] = []
    for row in criteria_out:
        for reason in row["blocking_reasons"]:
            blocking.append(f"{row['criterion_id']}: {reason}")

    if any(row["criterion_disposition"] == "fail" for row in criteria_out):
        overall_disposition = "fail"
    elif blocking:
        if required_deterministic and (not required_clinical or not required_tester):
            if not required_clinical:
                blocking.append(
                    "overall pass rejected: required clinical_manual evidence absent "
                    "even though deterministic checks may be green"
                )
            if not required_tester:
                blocking.append(
                    "overall pass rejected: required browser_tester evidence absent "
                    "even though deterministic checks may be green"
                )
        overall_disposition = (
            "blocked"
            if any(row["criterion_disposition"] == "blocked" for row in criteria_out)
            else "not_run"
        )
        seen_block: set[str] = set()
        deduped: list[str] = []
        for reason in blocking:
            if reason not in seen_block:
                seen_block.add(reason)
                deduped.append(reason)
        blocking = deduped
    else:
        overall_disposition = "pass"

    # Final hard gate — never allow pass if clinical/tester incomplete.
    if overall_disposition == "pass" and (not required_clinical or not required_tester):
        overall_disposition = "blocked"
        if not required_clinical:
            blocking.append("overall pass rejected: clinical_manual incomplete")
        if not required_tester:
            blocking.append("overall pass rejected: browser_tester incomplete")

    out["overall"] = {
        "disposition": overall_disposition,
        "deterministic_all_green": required_deterministic,
        "clinical_manual_complete": required_clinical,
        "browser_tester_complete": required_tester,
        "conference_advisory_present": advisory_present,
        "blocking_reasons": blocking,
        "evaluated_at": stamp,
    }
    out["case"]["fabricated"] = False
    return out


def _required_classes_complete(
    criteria: Sequence[Mapping[str, Any]],
    evidence_class: str,
) -> bool:
    """True when every criterion that requires ``evidence_class`` is satisfied."""
    for row in criteria:
        required = row.get("required_evidence_classes") or []
        if evidence_class not in required:
            continue
        if not _class_satisfied(list(row.get("evidence") or []), evidence_class):
            return False
        if _class_has_fail(list(row.get("evidence") or []), evidence_class):
            return False
    return True


def overall_pass_allowed(ledger: Mapping[str, Any]) -> bool:
    evaluated = evaluate_ledger(ledger)
    return evaluated["overall"]["disposition"] == "pass"


def evidence_classes_required_for(criterion_id: str) -> tuple[str, ...]:
    if criterion_id not in ACCEPTANCE_CRITERIA:
        raise LedgerValidationError(f"unknown criterion_id={criterion_id!r}")
    return tuple(ACCEPTANCE_CRITERIA[criterion_id]["required_evidence_classes"])


def iter_required_manual_or_tester_gaps(
    ledger: Mapping[str, Any],
) -> Iterable[tuple[str, str]]:
    """Yield (criterion_id, evidence_class) gaps for clinical_manual/browser_tester."""
    evaluated = evaluate_ledger(ledger)
    for row in evaluated["criteria"]:
        for cls in row["required_evidence_classes"]:
            if cls not in {"clinical_manual", "browser_tester"}:
                continue
            if not _class_satisfied(row["evidence"], cls):
                yield row["criterion_id"], cls


# ---------------------------------------------------------------------------
# Case-level DB / file / locator structural verifier
# ---------------------------------------------------------------------------


class CaseStructuralVerifier:
    """Read-only structural checks for an isolated case database and files.

    Observations use ``evidence_class=deterministic`` only. A structural pass
    must never be treated as clinical correctness (P5-AC12 remains
    ``clinical_manual``).
    """

    def __init__(
        self,
        *,
        database_path: str | Path,
        file_root: str | Path | None = None,
        project_id: str | None = None,
        subject_id: str | None = None,
        review_episode_id: str | None = None,
    ) -> None:
        self.database_path = Path(database_path)
        self.file_root = Path(file_root) if file_root else None
        self.project_id = project_id
        self.subject_id = subject_id
        self.review_episode_id = review_episode_id

    def verify(self) -> list[CaseStructuralObservation]:
        observations: list[CaseStructuralObservation] = []
        if not self.database_path.is_file():
            observations.append(
                CaseStructuralObservation(
                    check_id="db_present",
                    source_locator=str(self.database_path),
                    artifact=str(self.database_path),
                    observed_result="database file not found",
                    disposition="blocked",
                    notes=(
                        "Provide an isolated SQLite path; do not point at "
                        "external clinical originals."
                    ),
                )
            )
            return observations

        observations.append(
            CaseStructuralObservation(
                check_id="db_present",
                source_locator=str(self.database_path),
                artifact=str(self.database_path),
                observed_result="database file exists",
                disposition="pass",
            )
        )

        try:
            conn = sqlite3.connect(f"file:{self.database_path}?mode=ro", uri=True)
        except sqlite3.Error as exc:
            observations.append(
                CaseStructuralObservation(
                    check_id="db_open",
                    source_locator=str(self.database_path),
                    artifact=str(self.database_path),
                    observed_result=f"cannot open database read-only: {exc}",
                    disposition="blocked",
                )
            )
            return observations

        try:
            conn.row_factory = sqlite3.Row
            observations.extend(self._check_authority_tables(conn))
            observations.extend(self._check_fact_authority_bindings(conn))
            observations.extend(self._check_locator_links(conn))
            if self.file_root is not None:
                observations.extend(self._check_source_files(conn))
        finally:
            conn.close()
        return observations

    def attach_to_ledger(
        self,
        ledger: Mapping[str, Any],
        *,
        criterion_id: str = "P5-AC01",
        verifier: str = "CaseStructuralVerifier",
        timestamp: str | None = None,
    ) -> dict[str, Any]:
        """Record structural observations under a criterion (default P5-AC01).

        Never upgrades clinical_manual. Callers must still add manual evidence.
        """
        stamp = timestamp or _utc_now()
        updated = json.loads(json.dumps(ledger))
        for obs in self.verify():
            updated = record_evidence(
                updated,
                criterion_id,
                obs.as_evidence(verifier=verifier, timestamp=stamp),
                evaluated_at=stamp,
            )
        return updated

    def _table_exists(self, conn: sqlite3.Connection, name: str) -> bool:
        row = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
            (name,),
        ).fetchone()
        return row is not None

    def _check_authority_tables(
        self, conn: sqlite3.Connection
    ) -> list[CaseStructuralObservation]:
        required = (
            "clinical_facts_v2",
            "fact_evidence_locator_links",
            "evidence_locator_artifacts",
            "evidence_snapshots_v2",
            "evidence_processing_revisions",
        )
        observations: list[CaseStructuralObservation] = []
        for table in required:
            exists = self._table_exists(conn, table)
            observations.append(
                CaseStructuralObservation(
                    check_id=f"table:{table}",
                    source_locator=f"sqlite:{table}",
                    artifact=str(self.database_path),
                    observed_result=("present" if exists else "missing"),
                    disposition="pass" if exists else "fail",
                    notes="Phase 5 v2 write tables required for authority-chain audit",
                )
            )
        if self._table_exists(conn, "clinical_facts"):
            observations.append(
                CaseStructuralObservation(
                    check_id="legacy_clinical_facts_present",
                    source_locator="sqlite:clinical_facts",
                    artifact=str(self.database_path),
                    observed_result=(
                        "legacy clinical_facts table exists; structural verifier "
                        "does not read it as Phase 5 authority"
                    ),
                    disposition="observed_only",
                    notes="Legacy rows must not enter Profile; clinical_manual still required",
                )
            )
        return observations

    def _subject_filter_sql(self) -> tuple[str, list[Any]]:
        clauses: list[str] = []
        params: list[Any] = []
        if self.project_id:
            clauses.append("project_id = ?")
            params.append(self.project_id)
        if self.subject_id:
            clauses.append("subject_id = ?")
            params.append(self.subject_id)
        if self.review_episode_id:
            clauses.append("review_episode_id = ?")
            params.append(self.review_episode_id)
        if not clauses:
            return "", []
        return " WHERE " + " AND ".join(clauses), params

    def _check_fact_authority_bindings(
        self, conn: sqlite3.Connection
    ) -> list[CaseStructuralObservation]:
        if not self._table_exists(conn, "clinical_facts_v2"):
            return []
        where, params = self._subject_filter_sql()
        # ponytail: ceiling = schema drift if column renamed; upgrade via migration-aware mapper.
        sql = f"""
            SELECT fact_id,
                   project_id,
                   subject_id,
                   review_episode_id,
                   evidence_snapshot_v2_id,
                   complete_processing_revision_id
            FROM clinical_facts_v2
            {where}
        """
        try:
            rows = conn.execute(sql, params).fetchall()
        except sqlite3.Error as exc:
            return [
                CaseStructuralObservation(
                    check_id="fact_authority_query",
                    source_locator="sqlite:clinical_facts_v2",
                    artifact=str(self.database_path),
                    observed_result=f"query failed: {exc}",
                    disposition="blocked",
                )
            ]

        if not rows:
            return [
                CaseStructuralObservation(
                    check_id="fact_authority_rows",
                    source_locator="sqlite:clinical_facts_v2",
                    artifact=str(self.database_path),
                    observed_result=(
                        "no clinical_facts_v2 rows for the supplied scope; "
                        "not fabricating case entries"
                    ),
                    disposition=(
                        "blocked"
                        if (self.subject_id or self.project_id)
                        else "observed_only"
                    ),
                    notes="Empty scope is not a clinical pass",
                )
            ]

        missing_authority = [
            str(row["fact_id"])
            for row in rows
            if not row["evidence_snapshot_v2_id"]
            or not row["complete_processing_revision_id"]
        ]
        if missing_authority:
            sample = ", ".join(missing_authority[:5])
            return [
                CaseStructuralObservation(
                    check_id="fact_authority_complete",
                    source_locator="sqlite:clinical_facts_v2",
                    artifact=str(self.database_path),
                    observed_result=(
                        f"{len(missing_authority)} fact(s) missing snapshot or "
                        f"complete processing revision (sample: {sample})"
                    ),
                    disposition="fail",
                )
            ]
        return [
            CaseStructuralObservation(
                check_id="fact_authority_complete",
                source_locator="sqlite:clinical_facts_v2",
                artifact=str(self.database_path),
                observed_result=(
                    f"{len(rows)} fact row(s) carry snapshot + complete processing "
                    "revision ids (structural only)"
                ),
                disposition="pass",
                notes="Does not prove clinical correctness of fact values",
            )
        ]

    def _check_locator_links(
        self, conn: sqlite3.Connection
    ) -> list[CaseStructuralObservation]:
        needed = ("fact_evidence_locator_links", "evidence_locator_artifacts")
        if not all(self._table_exists(conn, name) for name in needed):
            return []
        try:
            dangling = conn.execute(
                """
                SELECT l.entity_id, l.locator_id
                FROM fact_evidence_locator_links AS l
                LEFT JOIN evidence_locator_artifacts AS a
                  ON a.locator_id = l.locator_id
                WHERE a.locator_id IS NULL
                LIMIT 20
                """
            ).fetchall()
            total_links = conn.execute(
                "SELECT COUNT(*) AS n FROM fact_evidence_locator_links"
            ).fetchone()["n"]
        except sqlite3.Error as exc:
            return [
                CaseStructuralObservation(
                    check_id="locator_link_query",
                    source_locator="sqlite:fact_evidence_locator_links",
                    artifact=str(self.database_path),
                    observed_result=f"query failed: {exc}",
                    disposition="blocked",
                )
            ]

        if dangling:
            sample = ", ".join(
                f"{row['entity_id']}->{row['locator_id']}" for row in dangling[:5]
            )
            return [
                CaseStructuralObservation(
                    check_id="locator_link_closure",
                    source_locator="sqlite:fact_evidence_locator_links",
                    artifact=str(self.database_path),
                    observed_result=f"dangling locator links present (sample: {sample})",
                    disposition="fail",
                )
            ]
        return [
            CaseStructuralObservation(
                check_id="locator_link_closure",
                source_locator="sqlite:fact_evidence_locator_links",
                artifact=str(self.database_path),
                observed_result=(
                    f"{total_links} locator link(s) resolve to evidence_locator_artifacts"
                ),
                disposition="pass",
                notes="Structural FK closure only; browser replay remains browser_tester",
            )
        ]

    def _check_source_files(
        self, conn: sqlite3.Connection
    ) -> list[CaseStructuralObservation]:
        assert self.file_root is not None
        if not self.file_root.is_dir():
            return [
                CaseStructuralObservation(
                    check_id="file_root",
                    source_locator=str(self.file_root),
                    artifact=str(self.file_root),
                    observed_result="file_root is not a directory",
                    disposition="blocked",
                )
            ]
        if not self._table_exists(conn, "evidence_locator_artifacts"):
            return []

        columns = {
            row["name"]
            for row in conn.execute("PRAGMA table_info(evidence_locator_artifacts)")
        }
        path_column = None
        for candidate in (
            "source_relative_path",
            "relative_path",
            "file_relative_path",
            "storage_path",
        ):
            if candidate in columns:
                path_column = candidate
                break
        if path_column is None:
            return [
                CaseStructuralObservation(
                    check_id="source_file_paths",
                    source_locator="sqlite:evidence_locator_artifacts",
                    artifact=str(self.file_root),
                    observed_result=(
                        "no relative path column on evidence_locator_artifacts; "
                        "file existence check skipped"
                    ),
                    disposition="observed_only",
                )
            ]

        rows = conn.execute(
            f"SELECT locator_id, {path_column} AS rel_path FROM evidence_locator_artifacts"
        ).fetchall()
        missing: list[str] = []
        checked = 0
        for row in rows:
            rel = row["rel_path"]
            if not rel:
                continue
            checked += 1
            candidate = self.file_root / str(rel)
            if not candidate.is_file():
                missing.append(f"{row['locator_id']}:{rel}")
        if checked == 0:
            return [
                CaseStructuralObservation(
                    check_id="source_file_paths",
                    source_locator=str(self.file_root),
                    artifact=str(self.file_root),
                    observed_result="no non-empty relative paths to check",
                    disposition="observed_only",
                )
            ]
        if missing:
            sample = ", ".join(missing[:5])
            return [
                CaseStructuralObservation(
                    check_id="source_file_paths",
                    source_locator=str(self.file_root),
                    artifact=str(self.file_root),
                    observed_result=(
                        f"{len(missing)}/{checked} locator file path(s) missing on disk "
                        f"(sample: {sample})"
                    ),
                    disposition="fail",
                )
            ]
        return [
            CaseStructuralObservation(
                check_id="source_file_paths",
                source_locator=str(self.file_root),
                artifact=str(self.file_root),
                observed_result=f"{checked} locator file path(s) exist under file_root",
                disposition="pass",
                notes="File presence only; does not validate clinical excerpt match",
            )
        ]
