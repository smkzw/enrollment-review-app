"""Names and ownership of the existing subject workflow, not a new scheduler."""
SUBJECT_GRAPH = {
    "S1": ("evidence_processing", "资料快照与识别"),
    "S2": ("fact_normalization", "节点需求清单"),
    "S3": ("fact_normalization", "按需求读取资料"),
    "S4": ("fact_normalization", "原文核对与采用"),
    "S5": ("work_draft_review", "calculate"),
    "S6": ("work_draft_review", "semantic"),
    "S7": ("work_draft_review", "compose"),
    "S8": ("work_draft_review", "save"),
}


def work_draft_steps(semantic_batch_count=1):
    previous = ()
    for owner, step in SUBJECT_GRAPH.values():
        if owner == "work_draft_review":
            for name in ([f"semantic:{index:04d}" for index in range(semantic_batch_count)]
                         if step == "semantic" and semantic_batch_count > 1 else [step]):
                yield name, previous
                previous = (name,)
