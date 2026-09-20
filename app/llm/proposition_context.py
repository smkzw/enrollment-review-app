"""Explicit, source-bound propositions shared by official and control readers."""


def proposition_context(pair):
    if pair.candidate_family == "control":
        atom = pair.condition.get("atom")
        spec = atom.get("evaluation") if isinstance(atom, dict) else None
        if not isinstance(spec, dict):
            raise ValueError("本条件未声明需要核实的原文命题")
        return spec, atom
    if pair.candidate_family != "predicate":
        raise ValueError("未知的方案条件来源")
    predicate = pair.condition.get("predicate")
    if not isinstance(predicate, dict):
        raise ValueError("缺少正式条件的原文命题")
    proposition = predicate.get("semantic_proposition")
    excerpts = predicate.get("exact_source_clauses")
    if (not isinstance(proposition, str) or not proposition.strip()
            or not isinstance(excerpts, list) or not excerpts
            or any(not isinstance(text, str) or not text.strip() for text in excerpts)
            or pair.condition.get("source_status") != "verbatim"
            or predicate.get("comparator") != "exists"
            or predicate.get("value") is not None or predicate.get("unit") is not None
            or predicate.get("requires_professional_judgment")
            or predicate.get("occurrence_window") is not None):
        raise ValueError("正式命题缺少明确原文，或混入需要另行核实的数值、频次、研究者判断")
    spec = {
        "version": "official-proposition/v1",
        "determination_mode": "semantic", "proposition": proposition,
        "source_excerpts": excerpts, "source_span_ids": [],
        "observation_policy": predicate.get("observation_policy"),
        "time_purpose": None,
    }
    return spec, {**predicate, "time_constraint": pair.condition.get("time_constraint")}


def prospective_requirement(pair):
    _, condition = proposition_context(pair)
    return {key: condition.get(key) for key in ("prospective_period", "prospective_window")
            if condition.get(key) is not None}


def prospective_sources(pair):
    spec, condition = proposition_context(pair)
    if not prospective_requirement(pair):
        return []
    if pair.candidate_family == "predicate":
        return [{"excerpt": text} for text in spec["source_excerpts"]]
    spans, excerpts = condition.get("source_span_ids"), condition.get("source_excerpts")
    if (not isinstance(spans, list) or not isinstance(excerpts, list)
            or not spans or len(spans) != len(excerpts)
            or any(not isinstance(value, str) or not value.strip() for value in (*spans, *excerpts))):
        raise ValueError("未来期间要求缺少本条件的完整方案原文")
    return [{"source_span_id": span, "excerpt": excerpt}
            for span, excerpt in zip(spans, excerpts, strict=True)]
