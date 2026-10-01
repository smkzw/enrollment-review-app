"""Conservative source-position check, not a semantic equivalence proof."""

import re


def nested_example_definitions(text: str) -> list[tuple[str, str, str]]:
    """Return (head, member, definition) for explicit listed-member brackets.

    A closed inner definition remains locatable when the outer example bracket
    is missing; the caller must still verify what the definition means.
    """

    found: list[tuple[str, str, str]] = []
    for marker in re.finditer(r"例如(?:包括但不限于|包括)?|包括但不限于|包括", text):
        head = re.split(r"[。；;]", text[:marker.start()])[-1].rstrip("（( ")
        listed = re.split(r"[。；;]", text[marker.end():], maxsplit=1)[0]
        for match in re.finditer(
            r"(?P<member>[^，、；;（）()]{1,80})[（(]"
            r"(?P<definition>[^（）()]{1,100})[）)]",
            listed,
        ):
            member = re.sub(r"^(?:或|和|及|与|、)+", "", match.group("member").strip())
            if head and member:
                found.append((head, member, match.group("definition")))
    return found


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
