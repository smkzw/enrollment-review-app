"""Synthetic tests of the documentation checker only; no product/clinical tests."""
import copy
import unittest
from check_handoff import validate


def fixture():
    return {
        "schema_version": "review-index/0929v1/v1", "document_kind": "handoff",
        "round_id": "SYNTHETIC-TEST", "recorded_at": "2026-09-29T12:00:00+08:00",
        "task_path": "synthetic/task", "execution_variant": "synthetic",
        "base_review_commit": "1" * 40, "delivered_snapshot_id": "CODE-1",
        "product_claims_complete": False,
        "code_snapshots": [{"id": "CODE-1", "kind": "commit", "base_commit": "1" * 40,
                            "access": "reviewer_accessible"}],
        "artifacts": [{"id": "E-1", "path": "synthetic/log.txt", "sha256": "a" * 64,
                       "access": "reviewer_accessible", "sensitivity": "public_technical"}],
        "tests": [{"id": "T-1", "snapshot_id": "CODE-1", "command": "synthetic-command",
                   "status": "passed", "exit_code": 0, "counts": {"passed": 1, "failed": 0, "skipped": 0},
                   "evidence_ids": ["E-1"]}],
        "claims": [{"id": "CL-1", "statement": "Synthetic checker fixture only",
                    "status": "verified", "snapshot_id": "CODE-1", "evidence_ids": ["E-1"],
                    "test_ids": ["T-1"], "limitations": "No product execution."}],
        "changes": [], "hypotheses": [], "recommendations": [], "next_actions": [],
    }


class CheckHandoffTests(unittest.TestCase):
    def test_valid_index(self):
        self.assertEqual(validate(fixture())[0], [])

    def test_template_not_handoff(self):
        data = fixture(); data["document_kind"] = "template"
        self.assertTrue(validate(data)[0])

    def test_allow_template_explicitly(self):
        data = fixture(); data["document_kind"] = "template"
        errors, warnings = validate(data, allow_template=True)
        self.assertFalse(errors); self.assertTrue(warnings)

    def test_missing_executed_snapshot(self):
        data = fixture(); data["tests"][0]["snapshot_id"] = "MISSING"
        self.assertTrue(validate(data)[0])

    def test_passing_status_with_failures_rejected(self):
        data = fixture(); data["tests"][0]["counts"]["failed"] = 2
        self.assertTrue(validate(data)[0])

    def test_dangling_evidence(self):
        data = fixture(); data["tests"][0]["evidence_ids"] = ["MISSING"]
        self.assertTrue(validate(data)[0])

    def test_unexecuted_cannot_support_verified(self):
        data = fixture(); data["tests"][0].update(status="not_run", exit_code=None)
        self.assertTrue(validate(data)[0])

    def test_claim_cannot_borrow_another_snapshot(self):
        data = fixture()
        data["code_snapshots"].append({"id": "CODE-2", "kind": "commit", "base_commit": "2" * 40,
                                        "access": "reviewer_accessible"})
        data["claims"][0]["snapshot_id"] = "CODE-2"
        self.assertTrue(validate(data)[0])

    def test_worktree_needs_manifest(self):
        data = fixture(); data["code_snapshots"][0]["kind"] = "working_tree"
        self.assertTrue(validate(data)[0])

    def test_worktree_with_indexed_manifest(self):
        data = fixture()
        data["code_snapshots"][0].update(kind="working_tree", manifest_artifact_id="E-2")
        data["artifacts"].append({"id": "E-2", "path": "synthetic/manifest.json", "sha256": None,
                                  "access": "reviewer_accessible", "sensitivity": "public_technical"})
        self.assertFalse(validate(data)[0])

    def test_restricted_source_not_ordinary_shareable(self):
        data = fixture(); data["artifacts"][0]["sensitivity"] = "restricted_source"
        self.assertTrue(validate(data)[0])

    def test_local_evidence_honestly_warned_not_rejected(self):
        data = fixture(); data["artifacts"][0]["access"] = "local_only"
        errors, warnings = validate(data)
        self.assertFalse(errors); self.assertTrue(warnings)

    def test_hypothesis_requires_alternative_and_disconfirmation(self):
        data = fixture(); data["hypotheses"] = [{"id": "H-1", "statement": "synthetic hypothesis"}]
        self.assertTrue(validate(data)[0])

    def test_product_entry_has_actual_result_not_fake_exit(self):
        data = fixture()
        data["tests"][0].update(execution_kind="product_entry", exit_code=None,
                                expected_result="Synthetic expected response", actual_result="Synthetic observed response")
        self.assertFalse(validate(data)[0])

    def test_product_entry_without_actual_result_rejected(self):
        data = fixture()
        data["tests"][0].update(execution_kind="product_entry", exit_code=None)
        self.assertTrue(validate(data)[0])

    def test_timestamp_timezone_required(self):
        data = fixture(); data["recorded_at"] = "2026-09-29T12:00:00"
        self.assertTrue(validate(data)[0])

    def test_duplicate_identifier(self):
        data = fixture(); data["artifacts"].append(copy.deepcopy(data["artifacts"][0]))
        self.assertTrue(validate(data)[0])

    def test_malformed_values_are_errors_not_crashes(self):
        data = fixture()
        data["tests"][0]["status"] = []
        data["claims"][0]["status"] = []
        data["delivered_snapshot_id"] = []
        data["code_snapshots"][0]["kind"] = []
        self.assertTrue(validate(data)[0])


if __name__ == "__main__":
    unittest.main(verbosity=2)
