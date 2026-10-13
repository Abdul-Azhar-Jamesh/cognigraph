"""End-to-end analysis of one program: evidence -> graph -> inference -> ranking.

:func:`analyze` is the only entry point of the inference path. Its inputs are
source code, tests, the oracle's expected behaviour and model parameters. It
has no parameter through which a fault location could be passed in.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, Sequence

import networkx as nx
import numpy as np

from . import baselines, config
from .config import ModelParams
from .dependence import Dependence, analyze_dependence
from .execution import SourceRun, Spectrum, build_spectrum, run_sources
from .fusion import FusionParams
from .graph import build_graph, fault_model_from_graph
from .mbfl import MutationEvidence
from .model import FaultModel, Posterior, infer
from .program import CompileDiagnostic, Program, compile_check
from .static_analysis import Finding, run_pylint

SCOPE_MODES = ("coverage", "slice")


def compute_scopes(spectrum: Spectrum, dependence: Dependence, mode: str) -> np.ndarray:
    """Which statements are parents of each test outcome.

    * ``coverage``: every statement the test executed.
    * ``slice``: executed statements in the backward dependence slice of the
      statement that ended the test. Falls back to coverage when the test was
      cut off by the step limit (its end point is then meaningless).
    """
    if mode not in SCOPE_MODES:
        raise ValueError(f"unknown scope mode {mode!r}; expected one of {SCOPE_MODES}")
    if mode == "coverage":
        return spectrum.coverage.copy()
    scopes = spectrum.coverage.copy()
    for j in range(spectrum.n_tests):
        exit_line = spectrum.exit_lines[j]
        if spectrum.exit_kinds[j] == "step_limit" or exit_line not in spectrum.statements:
            continue
        in_slice = dependence.backward_slice(exit_line)
        scopes[j] &= np.array([line in in_slice for line in spectrum.statements], dtype=bool)
    return scopes


@dataclass
class AnalysisResult:
    """Everything produced for one program version.

    When ``compile_error`` is set the program could not be run: there is no
    spectrum, no graph and no posterior, only the compiler's own diagnostic.
    """

    program: Optional[Program]
    compile_error: Optional[CompileDiagnostic] = None
    spectrum: Optional[Spectrum] = None
    dependence: Optional[Dependence] = None
    findings: Optional[list[Finding]] = None
    graph: Optional[nx.DiGraph] = None
    model: Optional[FaultModel] = None
    posterior: Optional[Posterior] = None
    baseline_scores: dict[str, np.ndarray] = field(default_factory=dict)
    scope_mode: str = "coverage"
    used_static: bool = False

    def ranking(self) -> list[tuple[int, float]]:
        """Statements with posterior fault probability, most suspicious first."""
        assert self.program is not None and self.posterior is not None
        rounded = np.round(self.posterior.marginals, config.RANK_DECIMALS)
        order = sorted(range(len(rounded)), key=lambda i: (-rounded[i], self.program.statements[i]))
        return [(self.program.statements[i], float(self.posterior.marginals[i])) for i in order]


def analyze_run(
    program: Program,
    run: SourceRun,
    expected: Sequence[str],
    params: ModelParams,
    *,
    scope: str = "coverage",
    findings: Optional[Sequence[Finding]] = None,
    use_static: bool = False,
    extra_likelihood_ratio: Optional[np.ndarray] = None,
    mutation: Optional[MutationEvidence] = None,
    fusion: Optional[FusionParams] = None,
    size_aware: bool = False,
    use_mutation: bool = False,
    use_context: bool = True,
) -> AnalysisResult:
    """Inference for a program whose tests have already been executed.

    The version-3 options (``mutation``, ``fusion``, ``size_aware``,
    ``use_mutation``, ``use_context``) default to the version-2 behaviour.
    """
    spectrum = build_spectrum(program, run, expected)
    dependence = analyze_dependence(program)
    scopes = compute_scopes(spectrum, dependence, scope)
    graph = build_graph(program, spectrum, dependence, scopes, findings, mutation)
    model = fault_model_from_graph(graph, params, use_static=use_static,
                                   extra_likelihood_ratio=extra_likelihood_ratio, fusion=fusion,
                                   size_aware=size_aware, use_mutation=use_mutation, use_context=use_context)
    posterior = infer(model)
    for i, line in enumerate(program.statements):
        graph.nodes[f"s:{line}"]["prior"] = float(model.prior[i])
        graph.nodes[f"s:{line}"]["posterior"] = float(posterior.marginals[i])
    return AnalysisResult(
        program=program,
        spectrum=spectrum,
        dependence=dependence,
        findings=list(findings) if findings is not None else None,
        graph=graph,
        model=model,
        posterior=posterior,
        baseline_scores={name: fn(spectrum.coverage, spectrum.failed) for name, fn in baselines.BASELINES.items()},
        scope_mode=scope,
        used_static=use_static,
    )


def analyze(
    source: str,
    func_name: str,
    tests: Sequence[Sequence],
    expected: Sequence[str],
    params: ModelParams,
    *,
    scope: str = "coverage",
    use_static: bool = False,
    extra_likelihood_ratio: Optional[np.ndarray] = None,
) -> AnalysisResult:
    """Analyse ``source``: compile, run tests with coverage, build graph, infer.

    Args:
        source: Python source containing the function.
        func_name: function the tests call.
        tests: argument lists, one per test (JSON-serialisable values).
        expected: oracle behaviour signature for each test.
        params: model parameters (estimated elsewhere).
        scope: ``"coverage"`` or ``"slice"``.
        use_static: run pylint and include its flags as evidence.
        extra_likelihood_ratio: optional per-statement likelihood ratio from an
            additional evidence source, in canonical statement order.
    """
    diagnostic = compile_check(source)
    if diagnostic is not None:
        return AnalysisResult(program=None, compile_error=diagnostic)
    program = Program.from_source(source, func_name)
    (run,) = run_sources([program.source], func_name, tests)
    if run is None:
        raise RuntimeError("the test run failed; no results were produced")
    if run.compile_error is not None:
        return AnalysisResult(program=program, compile_error=run.compile_error)
    findings = run_pylint([program.source])[0] if use_static else None
    return analyze_run(program, run, expected, params, scope=scope, findings=findings,
                       use_static=use_static, extra_likelihood_ratio=extra_likelihood_ratio)
