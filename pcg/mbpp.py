"""Loader for MBPP (external, fresh programs for the version 5 confirmatory study).

MBPP (Austin et al., 2021, CC BY 4.0) has 974 short Python solutions with three asserts each. The rules below are
those of ``research/RESEARCH_PROTOCOL_V5.md`` section 4; the asserted inputs are too few to localise a fault, so they
are *amplified* by perturbing one argument (the expected behaviour of a test is the behaviour of the solution itself,
as for every other benchmark here). The file is read from ``config.MBPP_FILE`` (JSON lines, see
``data/external/README.md``).
"""

from __future__ import annotations

import ast
import json
import warnings
from collections import Counter
from pathlib import Path
from typing import Optional, Sequence

import numpy as np

from . import config
from .execution import run_sources
from .humanevalfix import extract_test_inputs
from .program import Program, ProgramError
from .quixbugs import ExternalProgram

MIN_TESTS = 6
MIN_ORIGINAL_INPUTS = 2
NEW_INPUTS = 12
PER_ORIGINAL = 4
ATTEMPTS = 20


def tested_function(code: str, tests: Sequence[str]) -> Optional[str]:
    """The top-level function of ``code`` that the asserts call most often (None if no assert calls one)."""
    defined = {n.name for n in ast.parse(code).body if isinstance(n, ast.FunctionDef)}
    counts: Counter = Counter()
    for test in tests:
        try:
            tree = ast.parse(test)
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in defined:
                counts[node.func.id] += 1
    return counts.most_common(1)[0][0] if counts else None


def perturb(value, rng: np.random.Generator):
    """A slightly different value of the same kind (protocol section 4, rule 4)."""
    if isinstance(value, bool):
        return not value
    if isinstance(value, int):
        return [value + 1, value - 1, value * 2][int(rng.integers(3))]
    if isinstance(value, float):
        return value * 1.5
    if isinstance(value, str):
        if len(value) > 1 and rng.random() < 0.5:
            i = int(rng.integers(len(value)))
            return value[:i] + value[i + 1:]
        return value + "a"
    if isinstance(value, list):
        if not value:
            return value
        i, kind = int(rng.integers(len(value))), int(rng.integers(3))
        if kind == 0:
            return value[:i] + value[i + 1:]
        if kind == 1:
            return value[:i + 1] + [value[i]] + value[i + 1:]
        out = list(value)
        out[i] = perturb(value[i], rng)
        return out
    return value


def amplify(inputs: Sequence[tuple], rng: np.random.Generator) -> list[tuple]:
    """Up to ``NEW_INPUTS`` new distinct inputs, at most ``PER_ORIGINAL`` from each original one."""
    seen = {json.dumps(list(a), sort_keys=True) for a in inputs}
    new: list[tuple] = []
    for args in inputs:
        if not args:
            continue
        made = 0
        for _ in range(ATTEMPTS):
            if made >= PER_ORIGINAL or len(new) >= NEW_INPUTS:
                break
            changed = list(args)
            j = int(rng.integers(len(args)))
            changed[j] = perturb(args[j], rng)
            key = json.dumps(changed, sort_keys=True)
            if key not in seen:
                seen.add(key)
                new.append(tuple(changed))
                made += 1
    return new


def load_mbpp(path: Optional[Path] = None, reserved_names: Sequence[str] = (),
              min_statements: int = config.MBPP_MIN_STATEMENTS) -> tuple[list[ExternalProgram], list[dict]]:
    """Load every usable problem. Returns ``(programs, report)`` with one report entry per problem.

    ``fault_lines`` of the returned programs is empty: MBPP has no bugs, faults are injected by the experiments.
    """
    path = Path(path) if path is not None else config.MBPP_FILE
    if not path.is_file():
        raise FileNotFoundError(f"MBPP was not found at {path}. See data/external/README.md.")
    records = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    limits = dict(step_limit=config.EXTERNAL_STEP_LIMIT, timeout=config.MBPP_TIMEOUT_S)
    programs, report = [], []
    warnings.simplefilter("ignore", SyntaxWarning)  # some solutions contain regular expressions in plain strings
    for record in records:
        task = int(record["task_id"])
        entry = {"task_id": task, "status": "used"}
        report.append(entry)
        tests = list(record["test_list"]) + list(record["challenge_test_list"] or [])
        if (record["test_setup_code"] or "").strip():
            entry.update(status="excluded", reason="test setup code")
            continue
        try:
            function = tested_function(record["code"], tests)
        except SyntaxError:
            function = None
        if function is None:
            entry.update(status="excluded", reason="no tested top-level function")
            continue
        entry["function"] = function
        if function in reserved_names:
            entry.update(status="excluded", reason="same function name as a development program")
            continue
        try:
            program = Program.from_source(record["code"], function)
        except (ProgramError, SyntaxError) as exc:
            entry.update(status="excluded", reason=f"cannot be loaded: {exc}")
            continue
        entry["statements"] = len(program.statements)
        if len(program.statements) < min_statements:
            entry.update(status="excluded", reason=f"fewer than {min_statements} statements")
            continue
        if len(program.statements) > config.MBPP_MAX_STATEMENTS:
            entry.update(status="excluded", reason=f"more than {config.MBPP_MAX_STATEMENTS} statements")
            continue
        originals = extract_test_inputs("\n".join(tests), (function,))
        entry["original_inputs"] = len(originals)
        if len(originals) < MIN_ORIGINAL_INPUTS:
            entry.update(status="excluded", reason="fewer than 2 literal test inputs")
            continue
        rng = np.random.default_rng([config.SEED, 77, task])
        candidates = originals + amplify(originals, rng)
        first, second = (run_sources([program.source], function, candidates, **limits)[0] for _ in range(2))
        if first is None or second is None or first.compile_error is not None:
            entry.update(status="excluded", reason="the solution could not be executed")
            continue
        kept = [(args, a.signature) for args, a, b in zip(candidates, first.tests, second.tests)
                if a.exit_kind == "return" and a.signature == b.signature]
        entry["tests_kept"] = len(kept)
        if len(kept) < MIN_TESTS:
            entry.update(status="excluded", reason=f"fewer than {MIN_TESTS} usable tests")
            continue
        programs.append(ExternalProgram(f"{function}_{task}", program, program, tuple(a for a, _ in kept),
                                        tuple(s for _, s in kept), (), "none"))
    return programs, report
