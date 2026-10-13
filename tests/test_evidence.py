"""Evidence collection: execution/coverage, compiler, static analysis, dependence."""

import numpy as np
import pytest

from pcg.analysis import compute_scopes
from pcg.dependence import analyze_dependence
from pcg.execution import build_spectrum, oracle_signatures, run_sources
from pcg.program import Program, ProgramError, compile_check
from pcg.static_analysis import flagged_lines, run_pylint

LOOP = """
def f(xs):
    total = 0
    for x in xs:
        if x < 0:
            continue
        if x > 100:
            break
        if x == 7:
            pass
        total += x
    return total
"""


def run_one(source, name, tests, **kwargs):
    program = Program.from_source(source, name)
    (run,) = run_sources([program.source], name, tests, **kwargs)
    return program, run


def test_per_test_coverage_is_exact_including_pass_break_continue():
    program, run = run_one(LOOP, "f", [[[]], [[1]], [[-1]], [[200]], [[7]]])
    lines = [sorted(t.lines) for t in run.tests]
    assert program.statements == (2, 3, 4, 5, 6, 7, 8, 9, 10, 11)
    assert lines[0] == [2, 3, 11]                      # empty list: loop body never runs
    assert lines[1] == [2, 3, 4, 6, 8, 10, 11]         # ordinary element
    assert lines[2] == [2, 3, 4, 5, 11]                # continue
    assert lines[3] == [2, 3, 4, 6, 7, 11]             # break
    assert lines[4] == [2, 3, 4, 6, 8, 9, 10, 11]      # pass
    assert [t.signature for t in run.tests] == ["return:0", "return:1", "return:0", "return:0", "return:7"]
    assert all(t.exit_line == 11 for t in run.tests)


def test_exceptions_and_step_limit_are_outcomes_not_crashes():
    source = "def g(n):\n    while n != 0:\n        n -= 1\n    return 10 // n if n else 1 // n\n"
    _, run = run_one(source, "g", [[3], [-1]], step_limit=500)
    assert run.tests[0].signature == "raise:ZeroDivisionError" and run.tests[0].exit_line == 4
    assert run.tests[1].exit_kind == "step_limit"  # n = -1 never reaches 0


def test_a_test_that_fails_before_reaching_later_statements_does_not_cover_them():
    source = "def h(xs):\n    first = xs[0]\n    rest = xs[1:]\n    return first + len(rest)\n"
    program, run = run_one(source, "h", [[[]], [[5, 6]]])
    assert sorted(run.tests[0].lines) == [2] and run.tests[0].signature == "raise:IndexError"
    spectrum = build_spectrum(program, run, ["return:0", "return:6"])
    assert spectrum.failed.tolist() == [True, False]
    assert spectrum.coverage.tolist() == [[True, False, False], [True, True, True]]


def test_tests_cannot_contaminate_each_other_through_mutated_arguments():
    source = "def m(xs):\n    xs.append(1)\n    return len(xs)\n"
    _, run = run_one(source, "m", [[[0]], [[0]]])
    assert [t.signature for t in run.tests] == ["return:2", "return:2"]


def test_runaway_program_yields_no_result_instead_of_a_stale_one():
    source = "def boom(a):\n    while True:\n        a = a * a * 3\n"
    (run,) = run_sources([source], "boom", [[7]], timeout=3.0)
    assert run is None


def test_results_come_back_in_input_order_from_parallel_runs():
    sources = [f"def k(x):\n    return x + {i}\n" for i in range(12)]
    runs = run_sources(sources, "k", [[1]])
    assert [r.tests[0].signature for r in runs] == [f"return:{1 + i}" for i in range(12)]


def test_compiler_diagnostic_is_real_and_located():
    diagnostic = compile_check("def f(x):\n    if x > 0\n        return 1\n")
    assert diagnostic.kind == "SyntaxError" and diagnostic.line == 2
    assert compile_check("def f(x):\n    return x\n") is None


@pytest.mark.parametrize("source,name", [
    ("def f(:\n  pass\n", "f"),            # does not parse
    ("x = 1\n", "f"),                      # function missing
    ("", "f"),                             # empty input
    ("def f():\n    class G:\n        pass\n    return G()\n", "f"),  # nested classes are unsupported
])
def test_malformed_programs_raise_a_clear_error(source, name):
    with pytest.raises(ProgramError):
        Program.from_source(source, name)


def test_oracle_rejects_a_reference_that_does_not_terminate():
    from pcg.execution import ExecutionError
    with pytest.raises(ExecutionError):
        oracle_signatures("def f(n):\n    while True:\n        n += 1\n", "f", [[1]])


def test_empty_test_suite_gives_an_empty_spectrum():
    program, run = run_one("def f(x):\n    return x\n", "f", [])
    spectrum = build_spectrum(program, run, [])
    assert spectrum.coverage.shape == (0, 1) and spectrum.n_failed == 0


def test_pylint_findings_are_parsed_and_only_behavioural_ones_count():
    source = "def f(x):\n    y = x + 1\n    return z\n"
    (findings,) = run_pylint([source])
    by_symbol = {f.symbol: f for f in findings}
    assert by_symbol["undefined-variable"].line == 3 and by_symbol["undefined-variable"].relevant
    assert by_symbol["unused-variable"].line == 2 and by_symbol["unused-variable"].relevant
    assert not by_symbol["missing-function-docstring"].relevant  # style advice is never evidence
    assert flagged_lines(findings) == frozenset({2, 3})


def test_pylint_never_flags_the_pass_written_by_the_deletion_operator():
    (findings,) = run_pylint(["def f(x):\n    pass\n    return x\n"])
    assert flagged_lines(findings) == frozenset()


def test_def_use_sets_and_dependence_edges():
    program = Program.from_source(LOOP, "f")
    dep = analyze_dependence(program)
    assert dep.defs[2] == {"total"} and dep.uses[2] == frozenset()
    assert dep.defs[3] == {"x"} and dep.uses[3] == {"xs"}
    assert dep.defs[10] == {"total"} and dep.uses[10] == {"total", "x"}
    assert (2, 11) in dep.data_edges and (10, 11) in dep.data_edges and (3, 10) in dep.data_edges
    assert (3, 4) in dep.control_edges and (4, 5) in dep.control_edges
    assert (4, 10) in dep.control_edges   # the `continue` under line 4 decides whether line 10 runs
    assert (6, 10) in dep.control_edges   # so does the `break` under line 6
    assert (8, 10) not in dep.control_edges  # `if x == 7: pass` decides nothing about line 10


def test_backward_slice_drops_statements_that_cannot_affect_the_result():
    source = "def f(a, b):\n    unused = a * 2\n    total = a + b\n    if b > 0:\n        return total\n    return 0\n"
    program = Program.from_source(source, "f")
    dep = analyze_dependence(program)
    assert dep.backward_slice(5) == {3, 4, 5}      # `unused` (line 2) is not in the slice
    assert dep.backward_slice(6) == {4, 6}          # the early return guards line 6


def test_mutation_through_a_method_call_and_an_alias_is_tracked():
    source = "def f(xs):\n    out = []\n    ref = out\n    for x in xs:\n        ref.append(x)\n    return out\n"
    dep = analyze_dependence(Program.from_source(source, "f"))
    assert 5 in dep.backward_slice(6)  # ref.append changes the object `out` refers to


def test_slice_scope_is_a_subset_of_coverage_and_falls_back_on_step_limit():
    source = "def f(a, b):\n    unused = a * 2\n    total = a + b\n    return total\n"
    program, run = run_one(source, "f", [[1, 2]])
    spectrum = build_spectrum(program, run, ["return:3"])
    dep = analyze_dependence(program)
    coverage = compute_scopes(spectrum, dep, "coverage")
    sliced = compute_scopes(spectrum, dep, "slice")
    assert coverage.tolist() == [[True, True, True]] and sliced.tolist() == [[False, True, True]]
    assert np.all(sliced <= coverage)
    with pytest.raises(ValueError):
        compute_scopes(spectrum, dep, "nonsense")


def test_known_blind_spot_a_deleted_statement_falls_out_of_the_slice():
    """Documented limitation (LIMITATIONS.md): slicing cannot see faults of omission."""
    source = "def f(xs):\n    total = 0\n    for x in xs:\n        pass\n    return total\n"
    dep = analyze_dependence(Program.from_source(source, "f"))
    assert 4 not in dep.backward_slice(5)
