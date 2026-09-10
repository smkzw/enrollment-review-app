"""Remove redundant audit metadata from model input, never from stored evidence."""

from copy import deepcopy
from collections import Counter


def group_pending_observations(pending: list[dict]) -> list[dict]:
    """Factor repeated metadata without merging or dropping observations."""
    fields = ("page_review_id", "lane", "kind", "review_status", "review_message")
    groups = {}
    for position, item in enumerate(pending):
        shared = {field: item[field] for field in fields if field in item}
        key = tuple(shared.items())
        group = groups.setdefault(key, {"shared": shared, "observations": []})
        group["observations"].append({
            "position": position,
            "detail": {field: deepcopy(value) for field, value in item.items()
                       if field not in shared},
        })
    return list(groups.values())


def retained_pending_summary(payload: dict) -> dict:
    """Isolated model view; full observations must be retained by the caller."""
    result = deepcopy(payload)
    for page in result["accepted_pages"]:
        groups = page.pop("pending_observation_groups")
        counts = Counter()
        for group in groups:
            shared = group["shared"]
            counts[(shared.get("kind", "unknown"), shared.get("review_status", "unknown"))] += len(group["observations"])
        page["pending_retention"] = {
            "policy": "code-retained/v1",
            "observation_count": sum(counts.values()),
            "counts": [{"kind": kind, "review_status": status, "count": count}
                       for (kind, status), count in sorted(counts.items())],
        }
        # Both sides remain in the deterministic report; clause conflicts stay visible.
        page.pop("fact_conflicts", None)
        page.pop("handwriting_conflicts", None)
    return result


def compact_page_review_input(payload: dict) -> dict:
    result = deepcopy(payload)
    for page in result["accepted_pages"]:
        # Referencable observations carry these; NONE signals cannot support facts.
        for field in ("accepted_facts", "accepted_clause_signals", "accepted_handwriting"):
            page.pop(field, None)
        for item in page["accepted_observations"]:
            item["observation"].pop("normalization_key", None)
        pending = page["pending_observations"]
        for field in ("page_artifact_id", "source_document_version_id", "page_number", "use"):
            values = {item[field] for item in pending}
            if len(values) == 1:
                page["pending_" + field] = values.pop()
                for item in pending:
                    item.pop(field)
        for item in pending:
            # Pending reads explain gaps, never supply normalized candidate values.
            # Keep original wording/context; full geometry and derived values stay frozen.
            observation = item["observation"]
            item["observation"] = {
                key: observation[key]
                for key in ("observation_id", "field_name", "raw_text", "raw_value", "context", "kind")
                if key in observation
            }
            item["observation"]["region"] = {"excerpt": observation["region"]["excerpt"]}
            anchor = item.get("text_anchor")
            if anchor is not None:
                # Same frozen page text and same observation excerpt remain in input.
                anchor.pop("source_text_sha256", None)
                if anchor.get("excerpt") == item["observation"]["region"]["excerpt"]:
                    anchor.pop("excerpt")
        page["pending_observation_groups"] = group_pending_observations(
            page.pop("pending_observations")
        )
    return result
