"""The optional LLM path, exercised with a stand-in client (no network, no cost).

These tests cover what decides whether model output is trusted. They do not
show that the live API call works; that has not been run in this project.
"""

import json
from types import SimpleNamespace

import pytest

from pcg import llm
from pcg.benchmark_programs import BY_NAME
from pcg.execution import oracle_signatures
from pcg.mutation import generate_mutants
from pcg.program import Program
from pcg.repair import repair_with_generator


class FakeClient:
    """Returns queued payloads and records the requests it was sent."""

    def __init__(self, payloads, stop_reason="end_turn"):
        self.payloads, self.stop_reason, self.requests = list(payloads), stop_reason, []
        self.beta = SimpleNamespace(messages=SimpleNamespace(create=self._create))

    def _create(self, **request):
        self.requests.append(request)
        text = self.payloads.pop(0)
        text = text if isinstance(text, str) else json.dumps(text)
        return SimpleNamespace(stop_reason=self.stop_reason, content=[SimpleNamespace(type="text", text=text)])


def faulty_grade():
    bench = BY_NAME["grade"]
    reference = Program.from_source(bench.source, "grade")
    expected = oracle_signatures(reference.source, "grade", bench.tests)
    mutant = next(m for m in generate_mutants(reference) if m.mutant_id == "4:ROR-flip:0")
    return bench, reference, expected, Program.from_source(mutant.source, "grade")


def test_generation_returns_code_and_clamped_confidence():
    client = FakeClient([{"code": "def f(x):\n    return x\n",
                          "line_confidence": [{"line": 1, "confidence": 0.9}, {"line": 2, "confidence": 1.7}]}])
    code, confidence = llm.generate_function("def f(x): ...", client=client)
    assert code.startswith("def f") and confidence == {1: 0.9, 2: 1.0}
    request = client.requests[0]
    assert request["model"] == llm.DEFAULT_MODEL
    assert request["output_config"]["format"]["schema"] is llm.GENERATION_SCHEMA


def test_repair_prompt_carries_code_tests_and_uncertainty():
    _, _, _, program = faulty_grade()
    prompt = llm.repair_prompt(program, [4, 2], {4: 0.81, 2: 0.07},
                               [{"args": [95], "expected": "return:'A'", "observed": "return:'B'"}])
    assert "if score <= 90:" in prompt and "grade(95)" in prompt
    assert "line 4: estimated fault probability 0.81" in prompt and "[2, 4]" in prompt


def test_replacements_outside_the_region_are_refused():
    _, _, _, program = faulty_grade()
    assert llm.apply_replacements(program, [4], [{"line": 6, "new_text": "    if score >= 70:"}]) is None
    assert llm.apply_replacements(program, [4], []) is None
    assert llm.apply_replacements(program, [4], [{"line": 4, "new_text": "    if x:\n        return 1"}]) is None
    patched = llm.apply_replacements(program, [4], [{"line": 4, "new_text": "    if score >= 90:"}])
    assert patched.splitlines()[3] == "    if score >= 90:" and len(patched.splitlines()) == len(program.source.splitlines())


def test_llm_patch_is_accepted_only_after_passing_the_real_tests():
    bench, reference, expected, program = faulty_grade()
    client = FakeClient([
        {"replacements": [{"line": 4, "new_text": "    if score >= 95:"}]},   # plausible-looking, still wrong
        "this is not json",                                                    # unusable reply
        {"replacements": [{"line": 4, "new_text": "    if score >= 90:"}]},   # the real fix
    ])
    generate = llm.make_patch_generator({4: 0.8}, [], client=client)
    report = repair_with_generator(program, bench.tests, expected, [4], generate, top_k=1, max_attempts=3)
    assert [a.accepted for a in report.attempts] == [False, False, True]
    assert "fails test" in report.attempts[0].reason and report.attempts[1].reason == "no candidate"
    assert report.repaired and report.accepted_source == reference.source and report.tests_failed_after == 0


def test_refusals_and_truncation_raise_instead_of_returning_garbage():
    for reason in ("refusal", "max_tokens"):
        with pytest.raises(llm.LLMError):
            llm.generate_function("spec", client=FakeClient([{"code": "", "line_confidence": []}], stop_reason=reason))
