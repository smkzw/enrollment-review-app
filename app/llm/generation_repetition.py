"""Conservative detection of a repetitive reasoning tail, never clinical content."""

from collections import Counter
import re


def repetitive_reasoning_tail(text: str) -> bool:
    """Require sustained, long exact sentence repetition before rejecting a run."""
    if len(text) < 8192:
        return False
    tail = text[-8192:]
    # Discard both partial boundary sentences; punctuation alone is not evidence.
    sentences = [part.strip() for part in re.split(r"[\n。.!?！？]", tail)[1:-1]]
    counts = Counter(part for part in sentences if len(part) >= 32)
    repeated_characters = sum(len(sentence) * (count - 1)
                              for sentence, count in counts.items() if count >= 12)
    return repeated_characters >= len(tail) * 0.6


def repetitive_closing_tag_tail(text: str) -> bool:
    """Reject sustained protocol-tag output, not repeated clinical values."""
    if len(text) < 8192:
        return False
    lines = text[-8192:].splitlines()[1:-1]
    tags = [line.strip() for line in lines
            if re.fullmatch(r"</[A-Za-z_][A-Za-z_0-9-]*>", line.strip())]
    return (len(tags) >= 128 and len(set(tags)) <= 4
            and sum(map(len, tags)) >= 8192 * 0.9)
