# Verbatim class/function extracts from smkzw/enrollment-review-app.
# Baseline: 60f5bb8fe67ac14d44af9ceab0801a9b2a42120b
# Original: app/llm/predicate_binding_candidates.py; source blob:
# 30028ff1b23d9335406ee3e1641fb0869d8b3622
# This is NOT an importable copy of the complete repository module.

class PredicateCandidateReadError(ValueError):
    def __init__(self, message: str, completions=(), budgets=()):
        super().__init__(message)
        self.completions = tuple(completions)
        self.budgets = tuple(budgets)


async def read_candidate_payload(
    route: PageReaderRoute, messages: list[dict], *,
    validate: Callable[[str], _CandidatePayload],
    completion: Completion = direct_completion,
) -> tuple[_CandidatePayload, tuple[PageCompletion, ...], tuple[int, ...]]:
    """Shared direct transport policy; caller retains admission and persistence."""
    if not 65536 <= route.max_tokens <= 131072:
        raise PredicateCandidateReadError("对应任务输出额度须在65536至131072之间")
    responses: list[PageCompletion] = []
    budgets: list[int] = []
    budget = route.max_tokens
    waits = 0
    while True:
        try:
            response = await completion(route, messages, budget)
        except Exception as exc:
            if _status_code(exc) == 429 and waits < 12:
                waits += 1
                await asyncio.sleep(60)
                continue
            raise PredicateCandidateReadError("对应任务调用失败，不能当作无对应事实", responses, budgets) from exc
        responses.append(response)
        budgets.append(budget)
        if response.finish_reason == "length" and len(responses) == 1 and budget < MAX_SEMANTIC_OUTPUT_TOKENS:
            budget = min(2 * budget, MAX_SEMANTIC_OUTPUT_TOKENS)
            continue
        if response.finish_reason != "stop":
            raise PredicateCandidateReadError(
                f"对应任务输出不完整（finish_reason={response.finish_reason}，"
                f"model={response.response_model}），保留原回答待处理",
                responses, budgets)
        try:
            payload = validate(response.text)
        except ValueError as exc:
            raise PredicateCandidateReadError(str(exc), responses, budgets) from exc
        return payload, tuple(responses), tuple(budgets)
