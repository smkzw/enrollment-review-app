"""Semantic counterexamples survive the 0.2.0 pre-review publication policy."""
from app.protocols.deconstruction_gate import publication_issue_level, ProtocolDeconstructionGate


def assert_diagnostic_requires_review(result):
    issues = [issue for check in result.checks for issue in check.issues]
    assert any(issue.level in {"阻止发布", "需要核对"} for issue in issues)
    # Permission to enter review is not a reviewed RuleSet. The publication
    # consumer separately requires every current source/content-bound review.
    blocked = any(publication_issue_level(issue) in {"阻止发布", "需要核对"} for issue in issues)
    assert result.publishable is (not blocked)


class HistoricalSemanticGate(ProtocolDeconstructionGate):
    """Explicit historical fixture for the preserved, non-default recovery loop."""
    def evaluate(self, *args, **kwargs):
        result = super().evaluate(*args, **kwargs)
        return result.model_copy(update={"publishable": not any(issue.level in {"阻止发布", "需要核对"}
            for check in result.checks for issue in check.issues)})
