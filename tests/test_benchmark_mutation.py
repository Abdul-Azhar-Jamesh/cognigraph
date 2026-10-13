"""The benchmark programs, their oracle, and the fault-injection operators."""

import ast

import pytest

from pcg.benchmark_programs import BY_NAME, PROGRAMS
from pcg.execution import oracle_signatures
from pcg.mutation import generate_mutants
from pcg.program import Program

# Hand-written expectations, independent of the reference implementations.
# If a reference were wrong, the oracle would be wrong; these pin it down.
LITERALS = {
    "has_close_elements": [(([1.0, 2.0, 3.0], 0.5), False), (([1.0, 2.8, 3.0, 4.0, 5.0, 2.0], 0.3), True)],
    "max_of_list": [(([2, 5, 1],), 5), (([],), None)],
    "count_positive": [(([-1, 0, 1, 2],), 2)],
    "sum_even": [(([1, 2, 3, 4],), 6)],
    "clamp": [((11, 0, 10), 10), ((-1, 0, 10), 0), ((5, 0, 10), 5)],
    "sign": [((5,), 1), ((-5,), -1), ((0,), 0)],
    "is_sorted": [(([1, 2, 2, 5],), True), (([1, 3, 2],), False)],
    "binary_search": [(([1, 3, 5, 7], 7), 3), (([1, 3, 5, 7], 4), -1)],
    "gcd": [((12, 18), 6), ((7, 13), 1)],
    "is_prime": [((29,), True), ((25,), False), ((1,), False)],
    "factorial": [((5,), 120), ((0,), 1)],
    "fib": [((10,), 55), ((0,), 0)],
    "classify_triangle": [((3, 3, 3), "equilateral"), ((3, 4, 5), "scalene"), ((1, 2, 3), "invalid"), ((3, 3, 4), "isosceles")],
    "grade": [((90,), "A"), ((75,), "B"), ((60,), "C"), ((59,), "F"), ((101,), "invalid")],
    "is_leap_year": [((2000,), True), ((1900,), False), ((2024,), True), ((2023,), False)],
    "first_negative_index": [(([1, 2, -3, -4],), 2), (([1],), -1)],
    "second_largest": [(([2, 9, 4, 7],), 7), (([1],), None)],
    "bubble_sort": [(([5, 1, 4, 2, 3],), [1, 2, 3, 4, 5])],
    "count_vowels": [(("banana",), 3)],
    "is_palindrome": [(("racecar",), True), (("abca",), False)],
    "running_max": [(([1, 3, 2, 5],), [1, 3, 3, 5])],
    "merge_sorted": [(([1, 5, 9], [2]), [1, 2, 5, 9])],
    "fizzbuzz": [((15,), "FizzBuzz"), ((9,), "Fizz"), ((10,), "Buzz"), ((7,), "7")],
    "median": [(([3, 1, 2],), 2), (([4, 1, 3, 2],), 2.5), (([],), None)],
    "ranges_overlap": [((1, 3, 4, 6), False), ((1, 4, 4, 6), True)],
    "collatz_steps": [((6,), 8), ((1,), 0)],
    "remove_duplicates": [(([3, 1, 3, 2, 1],), [3, 1, 2])],
    "days_in_month": [((2, True), 29), ((2, False), 28), ((4, False), 30), ((1, False), 31), ((13, False), 0)],
    "index_of_min": [(([7, 8, 0, 5],), 2), (([],), -1)],
    "average_above": [(([10, 0, 20], 5), 15.0), (([1], 1), 0)],
    "count_in_range": [(([1, 5, 9], 5, 9), 2)],
    "int_sqrt": [((15,), 3), ((16,), 4)],
    "absolute_difference": [((3, 5), 2), ((-3, -8), 5)],
    "shipping_cost": [((11, False), 7), ((11, True), 14), ((0, True), 0), ((1, False), 5)],
}


def test_every_benchmark_program_has_pinned_expectations():
    assert set(LITERALS) == set(BY_NAME)
    assert len({p.name for p in PROGRAMS}) == len(PROGRAMS)


@pytest.mark.parametrize("name", sorted(LITERALS))
def test_reference_implementations_are_correct_on_hand_written_cases(name):
    args = [list(a) for a, _ in LITERALS[name]]
    want = ["return:" + repr(value) for _, value in LITERALS[name]]
    assert oracle_signatures(BY_NAME[name].source, name, args) == want


def test_expected_errors_are_part_of_the_oracle():
    assert oracle_signatures(BY_NAME["factorial"].source, "factorial", [[-1]]) == ["raise:ValueError"]
    assert oracle_signatures(BY_NAME["int_sqrt"].source, "int_sqrt", [[-4]]) == ["raise:ValueError"]


@pytest.mark.parametrize("name", [p.name for p in PROGRAMS])
def test_each_mutant_is_a_valid_single_line_change(name):
    program = Program.from_source(BY_NAME[name].source, name)
    mutants = generate_mutants(program)
    original = program.source.splitlines()
    assert mutants, "every program must yield mutants"
    assert len({m.mutant_id for m in mutants}) == len(mutants)
    assert len({m.source for m in mutants}) == len(mutants)
    for m in mutants:
        ast.parse(m.source)
        changed = [i for i, (a, b) in enumerate(zip(original, m.source.splitlines()), 1) if a != b]
        assert changed == [m.line], m.mutant_id               # ground truth = the one differing line
        assert m.line in program.statements                    # which is a statement of the function
        assert len(m.source.splitlines()) == len(original)
        assert Program.from_source(m.source, name).statements == program.statements


def test_mutant_generation_is_deterministic():
    program = Program.from_source(BY_NAME["binary_search"].source, "binary_search")
    first, second = generate_mutants(program), generate_mutants(program)
    assert [(m.mutant_id, m.source) for m in first] == [(m.mutant_id, m.source) for m in second]


def test_operators_do_what_the_documentation_says():
    source = (
        "def f(a, b, xs):\n"
        "    total = 0\n"
        "    for x in xs:\n"
        "        if x < a and x in xs:\n"
        "            break\n"
        "        total += x * 2\n"
        "    return total == b\n"
    )
    program = Program.from_source(source, "f")
    by_op = {}
    for m in generate_mutants(program):
        by_op.setdefault(m.operator, []).append(m.source.splitlines()[m.line - 1].strip())
    assert "if x > a and x in xs:" in by_op["ROR-flip"]
    assert "if x <= a and x in xs:" in by_op["ROR-bound"]
    assert "if x < a or x in xs:" in by_op["LCR"]
    assert "if x < a and x not in xs:" in by_op["MEM"]
    assert "if not (x < a and x in xs):" in by_op["NEG"]
    assert "continue" in by_op["JMP"]
    assert "total -= x * 2" in by_op["AOR"] and "total += x + 2" in by_op["AOR"]
    assert {"total = 1", "total = -1", "total += x * 3", "total += x * 1"} <= set(by_op["CRP"])
    assert "return total != b" in by_op["ROR-flip"]
    assert by_op["SDL"].count("pass") == 2
    assert set(by_op) == {"ROR-flip", "ROR-bound", "LCR", "MEM", "NEG", "JMP", "AOR", "CRP", "SDL"}


def test_boolean_constant_flip_and_double_negation_removal():
    program = Program.from_source("def f(x):\n    if not x:\n        return True\n    return False\n", "f")
    lines = {m.source.splitlines()[m.line - 1].strip() for m in generate_mutants(program)}
    assert {"return False", "return True", "if x:"} <= lines
