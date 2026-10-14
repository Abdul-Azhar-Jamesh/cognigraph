"""Loader for HumanEvalFix (external, hand-inserted bugs).

HumanEvalFix is the bug-fixing task of HumanEvalPack (Muennighoff et al.,
"OctoPack", ICLR 2024): the 164 HumanEval problems, each with one bug inserted
by hand into the canonical solution. It is not shipped with this project. The
Python split (MIT licence) is expected as JSON lines at
``config.HUMANEVALPACK_FILE``; ``docs/REPRODUCIBILITY.md`` says how to obtain it.

Taken from the benchmark: the declaration, the canonical and the buggy
solution, and the test inputs found in its ``check`` function. Derived here,
by the rules fixed in ``research/RESEARCH_PROTOCOL.md`` section 4:

* test inputs: calls of the function whose arguments are JSON-like literals;
* the oracle of a test: the behaviour of the canonical solution on that input;
* ground-truth lines: diff of the canonical texts, as for QuixBugs.
"""

from __future__ import annotations

import ast
import json
import math
from pathlib import Path
from typing import Optional, Sequence

from . import config
from .execution import run_sources
from .program import Program, ProgramError
from .quixbugs import ExternalProgram, fault_lines_from_diff

MIN_TESTS = 3


def _json_like(value) -> bool:
    if value is None or isinstance(value, (bool, int, str)):
        return True
    if isinstance(value, float):
        return math.isfinite(value)
    if isinstance(value, list):
        return all(_json_like(v) for v in value)
    if isinstance(value, dict):
        return all(isinstance(k, str) and _json_like(v) for k, v in value.items())
    return False


def extract_test_inputs(test_source: str, names: Sequence[str]) -> list[tuple]:
    """Argument tuples of every literal call of one of ``names`` in ``test_source``, without duplicates."""
    inputs, seen = [], set()
    for node in ast.walk(ast.parse(test_source)):
        if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in names):
            continue
        if node.keywords:
            continue
        try:
            args = [ast.literal_eval(arg) for arg in node.args]
        except (ValueError, SyntaxError):
            continue
        if not all(_json_like(a) for a in args):
            continue
        key = json.dumps(args, sort_keys=True)
        if key not in seen:
            seen.add(key)
            inputs.append(tuple(args))
    return inputs


def load_humanevalfix(path: Optional[Path] = None, reserved_names: Sequence[str] = ()) -> tuple[list[ExternalProgram], list[dict]]:
    """Load every usable problem. Returns ``(programs, report)``.

    ``reserved_names`` are function names that must not be used (programs of
    the development benchmark). ``report`` has one entry per problem.
    """
    path = Path(path) if path is not None else config.HUMANEVALPACK_FILE
    if not path.is_file():
        raise FileNotFoundError(
            f"HumanEvalPack (Python split) was not found at {path}. See docs/REPRODUCIBILITY.md.")
    records = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    limits = dict(step_limit=config.EXTERNAL_STEP_LIMIT, timeout=config.EXTERNAL_TIMEOUT_S)
    programs, report = [], []
    occurrences: dict[str, int] = {}
    for record in records:
        occurrences[record["entry_point"]] = occurrences.get(record["entry_point"], 0) + 1
    for record in records:
        name = record["entry_point"]
        # Six function names occur in two problems each; the program identifier must be unique.
        number = record["task_id"].split("/")[-1]
        identifier = name if occurrences[name] == 1 else f"{name}_{number}"
        entry = {"task_id": record["task_id"], "program": identifier, "function": name,
                 "bug_type": record["bug_type"], "status": "used"}
        report.append(entry)
        if name in reserved_names:
            entry.update(status="excluded", reason="same function name as a development program")
            continue
        header = (record.get("import") or "") + "\n" + record["declaration"]
        try:
            correct = Program.from_source(header + record["canonical_solution"], name)
            buggy = Program.from_source(header + record["buggy_solution"], name)
        except (ProgramError, SyntaxError) as exc:
            entry.update(status="excluded", reason=f"cannot be loaded: {exc}")
            continue
        inputs = extract_test_inputs(record["test"], (name, "candidate"))
        entry["literal_test_inputs"] = len(inputs)
        if len(inputs) < MIN_TESTS:
            entry.update(status="excluded", reason=f"fewer than {MIN_TESTS} literal test inputs")
            continue
        first, second = (run_sources([correct.source], name, inputs, **limits)[0] for _ in range(2))
        if first is None or second is None or first.compile_error is not None:
            entry.update(status="excluded", reason="the canonical solution could not be executed")
            continue
        if any(run.exit_kind != "return" for run in first.tests):
            entry.update(status="excluded", reason="the canonical solution raises or exceeds the step limit on a test input")
            continue
        # A behaviour that differs between two processes (e.g. the printed order of a set of strings) is no oracle.
        stable = [a.signature == b.signature for a, b in zip(first.tests, second.tests)]
        tests = tuple(args for args, ok in zip(inputs, stable) if ok)
        expected = tuple(run.signature for run, ok in zip(first.tests, stable) if ok)
        entry["tests_kept"] = len(tests)
        if len(tests) < MIN_TESTS:
            entry.update(status="excluded", reason=f"fewer than {MIN_TESTS} tests with a reproducible oracle")
            continue
        fault_lines, kind = fault_lines_from_diff(buggy, correct)
        entry.update(fault_lines=list(fault_lines), fault_kind=kind, statements=len(buggy.statements))
        if not fault_lines:
            entry.update(status="excluded", reason="buggy and canonical versions do not differ inside the function")
            continue
        programs.append(ExternalProgram(identifier, buggy, correct, tests, expected, fault_lines, kind))
    return programs, report
