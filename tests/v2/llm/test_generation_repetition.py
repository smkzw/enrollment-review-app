from app.llm.generation_repetition import repetitive_reasoning_tail


def test_sustained_exact_reasoning_loop_is_detected():
    assert repetitive_reasoning_tail(("a" * 90 + ".") * 150)
    assert repetitive_reasoning_tail((("a" * 35 + ".") + ("b" * 35 + ".")) * 150)


def test_short_or_interspersed_repetition_is_not_enough():
    assert not repetitive_reasoning_tail(("a" * 90 + ".") * 10)
    assert not repetitive_reasoning_tail("Yes. " * 3000)
    assert not repetitive_reasoning_tail("".join(f"{n}:" + "a" * 90 + "." for n in range(150)))


def test_distinct_long_reasoning_is_not_a_loop():
    assert not repetitive_reasoning_tail("".join(str(n) * 40 + "." for n in range(150)))
