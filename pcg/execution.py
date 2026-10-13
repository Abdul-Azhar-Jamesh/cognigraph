"""Test execution and per-test statement coverage (the execution evidence).

Analysed code is run in a separate Python process (``pcg/_runner.py``) under a
line tracer. For every test we obtain the set of executed lines, how the call
ended, and a behaviour signature that is compared with the oracle's signature
to decide pass or fail.
"""

from __future__ import annotations

import json
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Sequence

import numpy as np

from . import config
from .program import CompileDiagnostic, Program

_RUNNER = Path(__file__).with_name("_runner.py")


class ExecutionError(RuntimeError):
    """The runner process failed (crash, timeout, unreadable reply)."""


@dataclass(frozen=True)
class TestRun:
    """What one test did: executed lines, how it ended, observable behaviour."""

    __test__ = False  # not a pytest test class

    lines: frozenset[int]
    exit_kind: str  # "return" | "raise" | "step_limit"
    exit_line: Optional[int]
    signature: str
    value_json: Optional[str] = None


@dataclass(frozen=True)
class SourceRun:
    """Result of running the whole test suite against one source text."""

    compile_error: Optional[CompileDiagnostic]
    tests: tuple[TestRun, ...]


def _call_runner(job: dict, timeout: float) -> dict:
    try:
        proc = subprocess.run(
            [sys.executable, "-I", str(_RUNNER)],
            input=json.dumps(job),
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise ExecutionError(f"runner exceeded the {timeout:.0f}s wall-clock limit") from exc
    if proc.returncode != 0:
        raise ExecutionError(f"runner exited with code {proc.returncode}: {proc.stderr.strip()[-500:]}")
    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        raise ExecutionError("runner produced an unreadable reply") from exc


def _decode(run: dict) -> SourceRun:
    error = run["compile_error"]
    diagnostic = CompileDiagnostic(**error) if error else None
    tests = tuple(
        TestRun(frozenset(t["lines"]), t["exit"], t["exit_line"], t["signature"], t.get("value_json"))
        for t in run["tests"]
    )
    return SourceRun(diagnostic, tests)


def run_sources(
    sources: Sequence[str],
    func_name: str,
    tests: Sequence[Sequence],
    *,
    expected: Optional[Sequence[str]] = None,
    stop_on_failure: bool = False,
    step_limit: int = config.STEP_LIMIT,
    timeout: float = config.SUBPROCESS_TIMEOUT_S,
) -> list[Optional[SourceRun]]:
    """Run the test suite against each source text in child processes.

    Sources are sent to the runner in small batches, and batches run in
    parallel threads; results are returned in input order, so the outcome does
    not depend on scheduling. If a batch's process crashes or exceeds the
    wall-clock limit, each of its sources is retried alone, so one misbehaving
    program cannot spoil its neighbours. A source that still fails alone is
    reported as ``None``. It is never replaced by older data, and callers must
    treat it as "no result".

    The step limit bounds the number of executed lines, not the cost of one
    line; the wall-clock limit exists for the rare program whose single
    statement is astronomically expensive (e.g. runaway big-integer growth).
    """
    job = {
        "func": func_name,
        "tests": [list(args) for args in tests],
        "step_limit": step_limit,
        "expected": list(expected) if expected is not None else None,
        "stop_on_failure": stop_on_failure,
    }

    def run_batch(batch: Sequence[str]) -> list[Optional[SourceRun]]:
        try:
            reply = _call_runner({**job, "sources": list(batch)}, timeout)
            return [_decode(run) for run in reply["runs"]]
        except ExecutionError:
            if len(batch) == 1:
                return [None]
        return [run_batch([source])[0] for source in batch]

    size = config.RUNNER_BATCH_SIZE
    batches = [sources[i:i + size] for i in range(0, len(sources), size)]
    if len(batches) <= 1:
        return [run for batch in batches for run in run_batch(batch)]
    with ThreadPoolExecutor(max_workers=config.MAX_WORKERS) as pool:
        return [run for result in pool.map(run_batch, batches) for run in result]


def oracle_signatures(reference_source: str, func_name: str, tests: Sequence[Sequence]) -> list[str]:
    """Expected behaviour of every test, taken from a reference implementation."""
    (run,) = run_sources([reference_source], func_name, tests)
    if run is None or run.compile_error is not None:
        raise ExecutionError("the reference implementation could not be executed")
    for index, test in enumerate(run.tests):
        if test.exit_kind == "step_limit":
            raise ExecutionError(f"reference implementation hit the step limit on test {index}")
    return [test.signature for test in run.tests]


@dataclass(frozen=True)
class Spectrum:
    """Execution evidence for one program version.

    Attributes:
        statements: component line numbers (columns of ``coverage``).
        coverage: boolean matrix, ``coverage[j, i]`` is True when test ``j``
            executed statement ``statements[i]``.
        failed: boolean vector, True when test ``j`` failed.
        exit_lines: line of the last statement each test executed in the
            function's own frame (None if the function body never started).
        exit_kinds: how each test ended.
    """

    statements: tuple[int, ...]
    coverage: np.ndarray
    failed: np.ndarray
    exit_lines: tuple[Optional[int], ...]
    exit_kinds: tuple[str, ...]

    @property
    def n_tests(self) -> int:
        return int(self.coverage.shape[0])

    @property
    def n_failed(self) -> int:
        return int(self.failed.sum())


def build_spectrum(program: Program, run: SourceRun, expected: Sequence[str]) -> Spectrum:
    """Turn raw test runs into the coverage matrix and the pass/fail vector."""
    if run.compile_error is not None:
        raise ExecutionError("cannot build a spectrum for code that does not compile")
    if len(run.tests) != len(expected):
        raise ExecutionError("number of executed tests differs from the number of oracle outcomes")
    index = {line: col for col, line in enumerate(program.statements)}
    coverage = np.zeros((len(run.tests), len(program.statements)), dtype=bool)
    failed = np.zeros(len(run.tests), dtype=bool)
    for j, (test, want) in enumerate(zip(run.tests, expected)):
        for line in test.lines:
            if line in index:
                coverage[j, index[line]] = True
        failed[j] = test.signature != want
    return Spectrum(
        program.statements,
        coverage,
        failed,
        tuple(t.exit_line for t in run.tests),
        tuple(t.exit_kind for t in run.tests),
    )
