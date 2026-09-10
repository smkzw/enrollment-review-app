"""Conservative source-position check, not a semantic equivalence proof."""


def example_ranges(text: str) -> list[tuple[int, int]]:
    stack = []
    ranges = []
    closing = {")": "(", "）": "（"}
    for index, char in enumerate(text):
        if char in {"(", "（"}:
            stack.append((index, char))
        elif char in closing:
            if not stack or stack[-1][1] != closing[char]:
                return []
            start, _ = stack.pop()
            content = text[start + 1:index].lstrip()
            if content.startswith(("包括但不限于", "包括", "例如")):
                ranges.append((start + 1, index))
    return [] if stack else ranges


def crosses_example_scope(text: str, frequency_clause: str, sibling_clause: str) -> bool:
    """Flag only unambiguous exact spans crossing an explicit example boundary."""
    if not frequency_clause or not sibling_clause:
        return False
    if text.count(frequency_clause) != 1 or text.count(sibling_clause) != 1:
        return False
    inner = text.index(frequency_clause)
    sibling = text.index(sibling_clause)
    for start, end in example_ranges(text):
        if start <= inner and inner + len(frequency_clause) <= end:
            if sibling + len(sibling_clause) <= start - 1 or sibling >= end + 1:
                return True
    return False
