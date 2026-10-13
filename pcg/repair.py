"""Targeted repair: edit only the suspicious statements, then re-verify.

The deterministic repairer needs no external model. Its patch space is the set
of single-node edits from ``pcg.mutation`` applied to one statement. A
candidate is accepted only if it (1) compiles and (2) passes the complete,
unchanged test suite in a fresh child process. Nothing is ever written to the
user's files: candidates exist as text and are executed from memory.

What an accepted patch means: it is *plausible*, i.e. consistent with every
available test. That is weaker than correct. Passing tests cannot prove
correctness, and a plausible patch can differ from the intended program.

An optional LLM patch generator can be plugged in through
:func:`repair_with_generator`; see ``pcg.llm``. It goes through exactly the
same validation and is never trusted on its own word.
"""

from __future__ import annotations

import difflib
from dataclasses import dataclass, field
from typing import Callable, Optional, Sequence

from . import config
from .execution import run_sources
from .mutation import Mutant, generate_mutants
from .program import Program, ProgramError, compile_check


def candidate_patches(program: Program) -> list[Mutant]:
    """All single-edit patches of ``program`` in a fixed order (each knows its line)."""
    return generate_mutants(program)


def validate_patch(
    sources: Sequence[str],
    func_name: str,
    tests: Sequence[Sequence],
    expected: Sequence[str],
    step_limit: int = config.STEP_LIMIT,
    timeout: float = config.SUBPROCESS_TIMEOUT_S,
) -> list[dict]:
    """Compile and test each candidate source. Returns one verdict per source.

    A verdict is ``{"compiles", "tests_run", "tests_failed", "accepted", "reason"}``.
    ``accepted`` is True only when every test ran and matched the oracle.
    Testing stops at a candidate's first failing test, so ``tests_failed`` is
    0 or 1 and ``tests_run`` says how far it got.
    """
    compiles = [compile_check(source) is None for source in sources]
    runnable = [source for source, ok in zip(sources, compiles) if ok]
    runs = iter(run_sources(runnable, func_name, tests, expected=expected, stop_on_failure=True,
                            step_limit=step_limit, timeout=timeout))
    verdicts = []
    for ok in compiles:
        if not ok:
            verdicts.append({"compiles": False, "tests_run": 0, "tests_failed": 0, "accepted": False,
                             "reason": "does not compile"})
            continue
        run = next(runs)
        if run is None or run.compile_error is not None:
            verdicts.append({"compiles": True, "tests_run": 0, "tests_failed": 0, "accepted": False,
                             "reason": "execution crashed or exceeded the time limit"})
            continue
        failed = sum(t.signature != want for t, want in zip(run.tests, expected))
        accepted = failed == 0 and len(run.tests) == len(expected)
        verdicts.append({
            "compiles": True, "tests_run": len(run.tests), "tests_failed": failed, "accepted": accepted,
            "reason": "passes all tests" if accepted else f"fails test {len(run.tests) - 1}",
        })
    return verdicts


def unified_diff(before: str, after: str) -> str:
    return "".join(difflib.unified_diff(before.splitlines(True), after.splitlines(True), "before", "after", n=1))


@dataclass
class RepairAttempt:
    """One candidate patch and what happened to it."""

    number: int
    line: Optional[int]
    description: str
    compiles: bool
    tests_run: int
    accepted: bool
    reason: str
    diff: str


@dataclass
class RepairReport:
    """Complete record of a repair run."""

    region_lines: list[int]
    attempts: list[RepairAttempt] = field(default_factory=list)
    accepted_source: Optional[str] = None
    tests_failed_before: int = 0
    tests_failed_after: Optional[int] = None

    @property
    def repaired(self) -> bool:
        return self.accepted_source is not None

    def to_dict(self) -> dict:
        return {
            "region_lines": self.region_lines,
            "repaired": self.repaired,
            "tests_failed_before": self.tests_failed_before,
            "tests_failed_after": self.tests_failed_after,
            "attempts": [vars(a) for a in self.attempts],
            "accepted_source": self.accepted_source,
        }


def targeted_repair(
    program: Program,
    tests: Sequence[Sequence],
    expected: Sequence[str],
    ranked_lines: Sequence[int],
    top_k: int = config.REPAIR_TOP_K,
    step_limit: int = config.STEP_LIMIT,
    timeout: float = config.SUBPROCESS_TIMEOUT_S,
) -> RepairReport:
    """Deterministic repair: try single edits on the ``top_k`` most suspicious lines.

    Args:
        program: the faulty program (canonical form).
        tests / expected: the test suite and the oracle's behaviour.
        ranked_lines: statements from most to least suspicious, as produced by
            inference. This function has no other source of fault information.
        top_k: how many statements may be edited.
    """
    region = list(ranked_lines[:top_k])
    report = RepairReport(region_lines=region)
    limits = dict(step_limit=step_limit, timeout=timeout)
    (before,) = run_sources([program.source], program.func_name, tests, **limits)
    report.tests_failed_before = sum(t.signature != w for t, w in zip(before.tests, expected))

    by_line: dict[int, list[Mutant]] = {}
    for candidate in candidate_patches(program):
        by_line.setdefault(candidate.line, []).append(candidate)
    number = 0
    for line in region:
        for candidate in by_line.get(line, []):
            number += 1
            (verdict,) = validate_patch([candidate.source], program.func_name, tests, expected, **limits)
            report.attempts.append(RepairAttempt(
                number, line, candidate.description, verdict["compiles"], verdict["tests_run"],
                verdict["accepted"], verdict["reason"], unified_diff(program.source, candidate.source)))
            if verdict["accepted"]:
                return _confirm(report, candidate.source, program, tests, expected, **limits)
    return report


def repair_with_generator(
    program: Program,
    tests: Sequence[Sequence],
    expected: Sequence[str],
    ranked_lines: Sequence[int],
    generate: Callable[[Program, list[int], int], Optional[str]],
    top_k: int = config.REPAIR_TOP_K,
    max_attempts: int = 3,
) -> RepairReport:
    """Repair with an external patch generator (for example an LLM).

    ``generate(program, region_lines, attempt_number)`` must return a full
    candidate source or None. A candidate is rejected before testing if it does
    not parse, changes the statement layout, or touches a line outside the
    region: that is what keeps the repair *targeted*.
    """
    region = list(ranked_lines[:top_k])
    report = RepairReport(region_lines=region)
    (before,) = run_sources([program.source], program.func_name, tests)
    report.tests_failed_before = sum(t.signature != w for t, w in zip(before.tests, expected))
    for number in range(1, max_attempts + 1):
        proposal = generate(program, region, number)
        if proposal is None:
            report.attempts.append(RepairAttempt(number, None, "generator returned nothing", False, 0, False,
                                                 "no candidate", ""))
            continue
        try:
            candidate = Program.from_source(proposal, program.func_name)
        except ProgramError as exc:
            report.attempts.append(RepairAttempt(number, None, "generated patch", False, 0, False, str(exc), ""))
            continue
        diff = unified_diff(program.source, candidate.source)
        old, new = program.source.splitlines(), candidate.source.splitlines()
        if len(old) != len(new):
            report.attempts.append(RepairAttempt(number, None, "generated patch", True, 0, False,
                                                 "rejected: changes the number of lines", diff))
            continue
        changed = [i for i, (a, b) in enumerate(zip(old, new), 1) if a != b]
        if not changed or any(line not in region for line in changed):
            reason = "rejected: no change" if not changed else f"rejected: edits lines {changed} outside region {region}"
            report.attempts.append(RepairAttempt(number, None, "generated patch", True, 0, False, reason, diff))
            continue
        (verdict,) = validate_patch([candidate.source], program.func_name, tests, expected)
        report.attempts.append(RepairAttempt(number, changed[0], "generated patch", verdict["compiles"],
                                             verdict["tests_run"], verdict["accepted"], verdict["reason"], diff))
        if verdict["accepted"]:
            return _confirm(report, candidate.source, program, tests, expected)
    return report


def _confirm(report: RepairReport, source: str, program: Program, tests: Sequence[Sequence],
             expected: Sequence[str], step_limit: int = config.STEP_LIMIT,
             timeout: float = config.SUBPROCESS_TIMEOUT_S) -> RepairReport:
    """Independent re-run of the full suite on the accepted patch (no early stop)."""
    (after,) = run_sources([source], program.func_name, tests, step_limit=step_limit, timeout=timeout)
    if after is None or after.compile_error is not None:
        return report  # confirmation failed: the patch is not accepted
    failed_after = sum(t.signature != w for t, w in zip(after.tests, expected))
    report.tests_failed_after = failed_after
    if failed_after == 0 and len(after.tests) == len(expected):
        report.accepted_source = source
    return report
