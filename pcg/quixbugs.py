"""Loader for the QuixBugs benchmark (external, human-written bugs).

QuixBugs (Lin, Koppel, Chen, Solar-Lezama, SPLASH Companion 2017) contains 40
small Python programs, each with one bug on a single line, plus a correct
version and test cases. Its python programs and JSON tests are kept in data/external/QuixBugs (MIT licence; source and
commit in data/external/README.md).

Only the 31 programs with JSON test cases are used; the other nine take
object graphs as input, which the runner cannot receive as JSON.

What is taken from QuixBugs: the buggy source, the correct source, the test
inputs and the expected outputs. What is derived here:

* the oracle of a test is the behaviour of the correct program on that input.
  A test is kept only if that behaviour also equals the benchmark's expected
  output, so the oracle is checked against the benchmark itself;
* the ground-truth fault lines, by comparing the canonical texts of the buggy
  and the correct program. For a missing line (a fault of omission) the
  location is the statement that follows the insertion point, following the
  convention of Pearson et al. (ICSE 2017).
"""

from __future__ import annotations

import ast
import difflib
import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from . import config
from .execution import run_sources
from .program import Program, ProgramError


@dataclass(frozen=True)
class ExternalProgram:
    """One QuixBugs program, ready for analysis.

    ``fault_lines`` is evaluation-only ground truth (lines of the canonical
    buggy source). The inference code never receives it.
    """

    name: str
    buggy: Program
    correct: Program
    tests: tuple[tuple, ...]
    expected: tuple[str, ...]
    fault_lines: tuple[int, ...]
    fault_kind: str  # "modified line" or "missing line"


def _strip_module_strings(source: str) -> str:
    """Remove module-level string statements (the files end with a comment block in a string)."""
    tree = ast.parse(source)
    tree.body = [node for node in tree.body
                 if not (isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant)
                         and isinstance(node.value.value, str))]
    return ast.unparse(tree) + "\n"


def _json_equal(a, b, tolerance: float = 1e-6) -> bool:
    """Structural equality of JSON values; numbers compared with a tolerance."""
    if isinstance(a, bool) or isinstance(b, bool):
        return a is b
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        if isinstance(a, float) or isinstance(b, float):
            return math.isclose(a, b, rel_tol=tolerance, abs_tol=tolerance)
        return a == b
    if isinstance(a, list) and isinstance(b, list):
        return len(a) == len(b) and all(_json_equal(x, y, tolerance) for x, y in zip(a, b))
    if isinstance(a, dict) and isinstance(b, dict):
        return a.keys() == b.keys() and all(_json_equal(a[k], b[k], tolerance) for k in a)
    return type(a) is type(b) and a == b


def fault_lines_from_diff(buggy: Program, correct: Program) -> tuple[tuple[int, ...], str]:
    """Ground-truth lines of the buggy program, from a line diff of the canonical texts."""
    buggy_lines, correct_lines = buggy.source.splitlines(), correct.source.splitlines()
    statements = buggy.statements
    lines: set[int] = set()
    kinds: set[str] = set()
    for tag, i1, i2, _j1, _j2 in difflib.SequenceMatcher(None, buggy_lines, correct_lines, autojunk=False).get_opcodes():
        if tag == "equal":
            continue
        if tag in ("replace", "delete"):
            changed = [line for line in range(i1 + 1, i2 + 1) if line in statements]
            lines.update(changed)
            kinds.add("modified line")
        if tag == "insert" or (tag == "replace" and not lines):
            # Something is missing at this point: blame the statement that follows it.
            following = [line for line in statements if line > i1]
            lines.add(following[0] if following else statements[-1])
            kinds.add("missing line")
    return tuple(sorted(lines)), " and ".join(sorted(kinds)) if kinds else "none"


def load_quixbugs(root: Optional[Path] = None) -> tuple[list[ExternalProgram], list[dict]]:
    """Load every usable QuixBugs program. Returns ``(programs, report)``.

    ``report`` has one entry per program with JSON tests: how many tests were
    kept or dropped and why, and whether and why the program was excluded.
    """
    root = Path(root) if root is not None else config.QUIXBUGS_DIR
    if not (root / "json_testcases").is_dir():
        raise FileNotFoundError(
            f"QuixBugs was not found at {root}. Clone https://github.com/jkoppel/QuixBugs there "
            "or pass its location explicitly.")
    programs: list[ExternalProgram] = []
    report: list[dict] = []
    for test_file in sorted((root / "json_testcases").glob("*.json")):
        name = test_file.stem
        entry: dict = {"program": name, "status": "used"}
        report.append(entry)
        try:
            buggy = Program.from_source(_strip_module_strings((root / "python_programs" / f"{name}.py").read_text(encoding="utf-8")), name)
            correct = Program.from_source(_strip_module_strings((root / "correct_python_programs" / f"{name}.py").read_text(encoding="utf-8")), name)
        except (ProgramError, OSError, SyntaxError) as exc:
            entry.update(status="excluded", reason=f"cannot be loaded: {exc}")
            continue

        raw_tests = [json.loads(line) for line in test_file.read_text(encoding="utf-8").splitlines() if line.strip()]
        inputs = [case[0] if isinstance(case[0], list) else [case[0]] for case in raw_tests]
        outputs = [case[1] for case in raw_tests]
        (reference,) = run_sources([correct.source], name, inputs, step_limit=config.EXTERNAL_STEP_LIMIT,
                                   timeout=config.EXTERNAL_TIMEOUT_S)
        entry["tests_in_benchmark"] = len(raw_tests)
        if reference is None or reference.compile_error is not None:
            entry.update(status="excluded", reason="the correct program could not be executed")
            continue
        kept_inputs, kept_expected = [], []
        dropped = {"reference_exceeded_step_limit": 0, "reference_raised": 0, "reference_disagrees_with_expected_output": 0,
                   "duplicate_input": 0}
        seen_inputs = set()
        for args, want, run in zip(inputs, outputs, reference.tests):
            key = json.dumps(args, sort_keys=True)
            if key in seen_inputs:
                dropped["duplicate_input"] += 1
            elif run.exit_kind == "step_limit":
                dropped["reference_exceeded_step_limit"] += 1
            elif run.exit_kind != "return" or run.value_json is None:
                dropped["reference_raised"] += 1
            elif not _json_equal(json.loads(run.value_json), want):
                dropped["reference_disagrees_with_expected_output"] += 1
            else:
                seen_inputs.add(key)
                kept_inputs.append(tuple(args))
                kept_expected.append(run.signature)
        entry["tests_kept"] = len(kept_inputs)
        entry["tests_dropped"] = dropped
        if not kept_inputs:
            entry.update(status="excluded", reason="no usable test remains")
            continue
        if buggy.statements != correct.statements and len(buggy.source.splitlines()) == len(correct.source.splitlines()):
            entry["note"] = "statement layout differs between the buggy and the correct version"
        fault_lines, kind = fault_lines_from_diff(buggy, correct)
        entry["fault_lines"] = list(fault_lines)
        entry["fault_kind"] = kind
        entry["statements"] = len(buggy.statements)
        if not fault_lines:
            entry.update(status="excluded", reason="buggy and correct versions do not differ inside the function")
            continue
        programs.append(ExternalProgram(name, buggy, correct, tuple(kept_inputs), tuple(kept_expected), fault_lines, kind))
    return programs, report
