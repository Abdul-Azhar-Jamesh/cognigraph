"""The review demonstration: ``python -m pcg demo``.

Six cases are executed live (nothing is read from a saved answer):

1. ``original_example``  the original project's example, a flipped comparison in
   ``has_close_elements``.
2. ``clear_success``     among benchmark mutants of other programs whose
   fault the model ranks alone in first place, the one with the highest
   posterior on the faulty line (first in file order among equals).
3. ``worst_case``        the benchmark mutant with the lowest reciprocal rank
   under PCG (first in file order among equals).
4. ``human_bug``         a human-written bug from QuixBugs: the one on which
   mutation evidence changes the fault's reciprocal rank the most (first in
   file order among equals). Needs the research results and data/external/QuixBugs.
5. ``fault_free``        the correct program: what the model says when every
   test passes.
6. ``compile_error``     a syntactically broken program: compiler evidence.

Cases 2 to 4 are selected by the stated rules from stored results, not by
hand. Model parameters for a benchmark program are always the estimates that
exclude that program's own mutants; for the QuixBugs program they come from
the project's benchmark only.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Callable, Optional, Sequence

import numpy as np

from . import config, experiments as ex, pipeline, visualize
from .analysis import AnalysisResult, analyze, analyze_run
from .benchmark_programs import BY_NAME
from .config import ModelParams
from .execution import build_spectrum, oracle_signatures, run_sources
from .fusion import FusionParams
from .graph import fault_model_from_graph, graph_to_json
from .mbfl import CONTEXT_NAMES, LEVEL_NAMES, MutationEvidence, mutation_evidence
from .model import infer
from .mutation import generate_mutants
from .program import Program
from .repair import targeted_repair
from .static_analysis import run_pylint

DEMO_DIR = config.RESULTS_DIR / "demo"
RESEARCH_DIR = config.RESULTS_DIR / "research"
ORIGINAL_EXAMPLE = ("has_close_elements", "4:ROR-flip:0")


def _mutant_source(program_name: str, mutant_id: str) -> tuple[str, str]:
    """Rebuild a benchmark mutant from scratch by applying its mutation again."""
    bench = BY_NAME[program_name]
    program = Program.from_source(bench.source, bench.name)
    for mutant in generate_mutants(program):
        if mutant.mutant_id == mutant_id:
            return mutant.source, mutant.description
    raise KeyError(f"{program_name} has no mutant {mutant_id}")


def _select_cases(benchmark_dir: Path) -> dict[str, tuple[str, str]]:
    with open(benchmark_dir / "first_order_per_case.csv", newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    success = max((r for r in rows if r["program"] != ORIGINAL_EXAMPLE[0] and float(r["pcg.top1"]) == 1.0
                   and int(r["pcg.tie_size"]) == 1), key=lambda r: float(r["pcg.posterior_of_fault"]))
    worst = min(rows, key=lambda r: float(r["pcg.reciprocal_rank"]))  # min keeps the first of equals

    def split(case_id: str) -> tuple[str, str]:
        name, mutant_id = case_id.split(":", 1)
        return name, mutant_id

    return {
        "original_example": ORIGINAL_EXAMPLE,
        "clear_success": split(success["case_id"]),
        "worst_case": split(worst["case_id"]),
    }


def _research_available(research_dir: Path) -> bool:
    return (research_dir / "MANIFEST.json").exists()


def _mutation_analysis(program: Program, run, tests, expected, step_limit: int, timeout: float) -> MutationEvidence:
    """Run every single-edit variant of the program and summarise the outcomes."""
    variants = generate_mutants(program)
    runs = run_sources([v.source for v in variants], program.func_name, tests, step_limit=step_limit, timeout=timeout)
    outcomes = []
    for variant, variant_run in zip(variants, runs):
        usable = variant_run is not None and variant_run.compile_error is None and len(variant_run.tests) == len(tests)
        outcomes.append((variant.line, [t.signature for t in variant_run.tests] if usable else None))
    spectrum = build_spectrum(program, run, list(expected))
    return mutation_evidence(program.statements, spectrum.coverage, spectrum.failed,
                             [t.signature for t in run.tests], list(expected), outcomes)


def _coverage_table(result: AnalysisResult, tests) -> list[str]:
    spectrum = result.spectrum
    header = "| Test | Arguments | Outcome | " + " | ".join(f"L{line}" for line in spectrum.statements) + " |"
    lines = [header, "|---|---|---|" + "---|" * len(spectrum.statements)]
    for j in range(spectrum.n_tests):
        marks = " | ".join("x" if spectrum.coverage[j, i] else "." for i in range(len(spectrum.statements)))
        outcome = "**FAIL**" if spectrum.failed[j] else "pass"
        lines.append(f"| {j} | `{json.dumps(list(tests[j]))[:60]}` | {outcome} | {marks} |")
    return lines


def _ranking_table(result: AnalysisResult, with_static: Optional[np.ndarray], fused: Optional[np.ndarray],
                   evidence: Optional[MutationEvidence]) -> list[str]:
    program = result.program
    ochiai = result.baseline_scores["ochiai"]
    index = {line: i for i, line in enumerate(program.statements)}
    lines = ["| Rank | Line | Statement | P(faulty) tests only | + static | Mutation evidence | P(faulty) fused | Ochiai |",
             "|---|---|---|---|---|---|---|---|"]
    for rank, (line, probability) in enumerate(result.ranking(), 1):
        i = index[line]
        static_text = f"{with_static[i]:.3f}" if with_static is not None else "n/a"
        fused_text = f"{fused[i]:.3f}" if fused is not None else "n/a"
        level_text = (f"{LEVEL_NAMES[int(evidence.levels[i])]} ({CONTEXT_NAMES[int(evidence.contexts[i])]})"
                      if evidence is not None else "n/a")
        lines.append(f"| {rank} | {line} | `{program.line_text(line).strip()[:48]}` | {probability:.3f} | {static_text} | "
                     f"{level_text} | {fused_text} | {ochiai[i]:.3f} |")
    return lines


def _order(scores: np.ndarray, statements: Sequence[int]) -> list[int]:
    rounded = np.round(scores, config.RANK_DECIMALS)
    return [statements[i] for i in sorted(range(len(statements)), key=lambda i: (-rounded[i], statements[i]))]


def _run_faulty_case(key: str, title: str, source: str, func_name: str, tests, expected, params: ModelParams,
                     fusion: Optional[FusionParams], truth_lines: Sequence[int], truth_description: str,
                     reference_source: Optional[str], out: ex.OutputDir, say: Callable[[str], None],
                     step_limit: int = config.STEP_LIMIT, timeout: float = config.SUBPROCESS_TIMEOUT_S) -> None:
    """Analyse one faulty program. ``truth_*`` is only printed at the very end."""
    program = Program.from_source(source, func_name)
    (run,) = run_sources([program.source], func_name, tests, step_limit=step_limit, timeout=timeout)
    findings = run_pylint([program.source])[0]
    evidence = _mutation_analysis(program, run, tests, expected, step_limit, timeout) if fusion is not None else None
    result = analyze_run(program, run, expected, params, findings=findings, mutation=evidence, fusion=fusion)
    with_static = infer(fault_model_from_graph(result.graph, params, use_static=True)).marginals
    fused = (infer(fault_model_from_graph(result.graph, params, fusion=fusion, size_aware=True, use_mutation=True)).marginals
             if fusion is not None else None)
    for i, line in enumerate(program.statements):
        node = result.graph.nodes[f"s:{line}"]
        node["posterior_with_static"] = float(with_static[i])
        if fused is not None:
            node["posterior_fused"] = float(fused[i])

    case_dir = out.path / key
    case_dir.mkdir()
    (case_dir / "faulty_program.py").write_text(program.source, encoding="utf-8")
    graph_to_json(result.graph, case_dir / "graph.json")
    visualize.draw_graph(result.graph, case_dir / "graph.png", f"{title}: constraint graph (colour: tests-only posterior)")

    say(f"\n## Case `{key}`: {title}\n")
    say("Faulty program as analysed (the fault location is not given to the analysis):\n")
    say("```python\n" + program.listing() + "\n```\n")
    say(f"**Compiler:** compiles without diagnostics. **Tests:** {result.spectrum.n_failed} of "
        f"{result.spectrum.n_tests} fail.\n")
    say("Per-test statement coverage (x = executed):\n")
    for line in _coverage_table(result, tests):
        say(line)
    say(f"\n**Static analysis (pylint):** {len(findings)} message(s), "
        f"{sum(f.relevant for f in findings)} treated as correctness-relevant.")
    for f in findings:
        say(f"- line {f.line}: `{f.symbol}` ({f.type}) {'USED as evidence' if f.relevant else 'style only, not used'}")
    if evidence is not None:
        say(f"\n**Mutation analysis:** {evidence.n_variants} single-edit variants of this program were run against "
            f"all tests ({evidence.n_usable} gave a result).")
    say(f"\n**Parameters** ({params.provenance}): prior {params.prior_fault:.3f}, leak {params.leak:.5f}, "
        f"pooled theta {params.theta:.3f}." + (f" Fused model: {fusion.provenance}." if fusion is not None else "") + "\n")
    graph = result.graph
    kinds = {k: sum(1 for *_, d in graph.edges(data=True) if d["kind"] == k)
             for k in ("in_scope", "data", "control", "def", "use", "flags", "mutation")}
    say(f"**Graph:** {sum(1 for _, d in graph.nodes(data=True) if d['kind'] == 'statement')} statement nodes, "
        f"{sum(1 for _, d in graph.nodes(data=True) if d['kind'] == 'variable')} variable nodes, "
        f"{result.spectrum.n_tests} test nodes; edges: {kinds}. Files: `{key}/graph.json`, `{key}/graph.png`.\n")
    tests_only = result.posterior
    say(f"**Inference (tests only):** {tests_only.method}; P(no fault | evidence) = {tests_only.p_no_fault:.2e}; "
        f"expected number of faulty statements = {tests_only.expected_faults:.2f}; "
        f"most probable exposure rate = {params.exposure_prior()[0][int(np.argmax(tests_only.theta_posterior))]:.2f}.\n")
    for line in _ranking_table(result, with_static, fused, evidence):
        say(line)

    ranked_lines = [line for line, _ in result.ranking()]
    say(f"\n**Order, tests only:** {ranked_lines}. **Ochiai:** {_order(result.baseline_scores['ochiai'], program.statements)}."
        + (f" **Fused:** {_order(fused, program.statements)}." if fused is not None else "") + "\n")

    report = targeted_repair(program, tests, expected, ranked_lines, step_limit=step_limit, timeout=timeout)
    (case_dir / "repair_report.json").write_text(json.dumps(report.to_dict(), indent=2), encoding="utf-8")
    say(f"**Targeted repair** (guided by the tests-only ranking; only lines {report.region_lines} may be edited): "
        f"{len(report.attempts)} candidate patch(es) validated.\n")
    say("| # | Line | Edit | Verdict |\n|---|---|---|---|")
    for attempt in report.attempts:
        say(f"| {attempt.number} | {attempt.line} | {attempt.description} | "
            f"{'ACCEPTED' if attempt.accepted else 'rejected'}: {attempt.reason} |")
    if report.repaired:
        (case_dir / "repaired_program.py").write_text(report.accepted_source, encoding="utf-8")
        say(f"\nAccepted patch:\n\n```diff\n{report.attempts[-1].diff}```\n")
        say(f"**Before:** {report.tests_failed_before} failing tests. **After (independent re-run of all "
            f"{result.spectrum.n_tests} tests):** {report.tests_failed_after} failing.")
        if reference_source is not None:
            say("The patched program is " + ("textually identical to the reference implementation."
                if report.accepted_source == reference_source else
                "**not** identical to the reference implementation: it is plausible (passes every test) "
                "but may still be wrong on inputs the tests do not cover."))
    else:
        say(f"\n**No patch accepted.** {report.tests_failed_before} tests still fail. "
            "No single edit of the allowed statements makes all tests pass.")

    # The ground truth is revealed only now, after all inference and repair output.
    best = min(truth_lines, key=ranked_lines.index)
    text = (f"\n**Ground truth (revealed after the analysis):** {truth_description}. Tests-only model: position "
            f"{ranked_lines.index(best) + 1} of {len(ranked_lines)}, posterior {dict(result.ranking())[best]:.3f}.")
    if fused is not None:
        fused_order = _order(fused, program.statements)
        best_fused = min(truth_lines, key=fused_order.index)
        text += (f" Fused model: position {fused_order.index(best_fused) + 1}, posterior "
                 f"{fused[program.statements.index(best_fused)]:.3f}.")
    say(text + "\n")


def _run_fault_free(out: ex.OutputDir, benchmark_dir: Path, say: Callable[[str], None]) -> None:
    bench = BY_NAME[ORIGINAL_EXAMPLE[0]]
    reference = Program.from_source(bench.source, bench.name)
    expected = oracle_signatures(reference.source, bench.name, bench.tests)
    params = pipeline.load_params(bench.name, path=benchmark_dir)
    result = analyze(bench.source, bench.name, bench.tests, expected, params)
    n = len(result.program.statements)
    say(f"\n## Case `fault_free`: {bench.name}, reference implementation\n")
    say(f"All {result.spectrum.n_tests} tests pass. P(no fault) moves from the prior "
        f"{(1 - params.prior_fault) ** n:.3f} to the posterior {result.posterior.p_no_fault:.3f}.\n")
    for line in _ranking_table(result, None, None, None):
        say(line)
    say("\nPassing tests lower every executed statement's fault probability but never to zero: "
        "tests cannot prove correctness.\n")
    case_dir = out.path / "fault_free"
    case_dir.mkdir()
    graph_to_json(result.graph, case_dir / "graph.json")


def _run_compile_error(benchmark_dir: Path, say: Callable[[str], None]) -> None:
    bench = BY_NAME[ORIGINAL_EXAMPLE[0]]
    broken = bench.source.replace("for i in range(len(numbers)):", "for i in range(len(numbers))")
    result = analyze(broken, bench.name, bench.tests, [], pipeline.load_params(bench.name, path=benchmark_dir))
    say(f"\n## Case `compile_error`: {bench.name} with a colon removed by hand\n")
    say("```python\n" + broken + "```\n")
    d = result.compile_error
    say(f"**Compiler diagnostic:** `{d.kind}` at line {d.line}, column {d.column}: {d.message}.\n")
    say("The program cannot run, so there is no coverage, no graph and no posterior. A compile failure is "
        "certain evidence that the program is faulty; the reported position is where the parser stopped, "
        "which is a hint and not a probability.\n")


def _run_human_bug(out: ex.OutputDir, research_dir: Path, say: Callable[[str], None]) -> Optional[str]:
    """The QuixBugs case on which mutation evidence changes the fault's rank the most."""
    from .quixbugs import load_quixbugs

    if not (config.QUIXBUGS_DIR / "json_testcases").is_dir():
        say("\n## Case `human_bug`: skipped (QuixBugs data not found)\n")
        return None
    with open(research_dir / "d2_transfer_per_case.csv", newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    chosen = max(rows, key=lambda r: float(r["pcg_fused.reciprocal_rank"]) - float(r["pcg_size.reciprocal_rank"]))
    pooled = json.loads((research_dir / "fusion_params_pooled.json").read_text(encoding="utf-8"))
    programs, _ = load_quixbugs()
    program = next(p for p in programs if p.name == chosen["program"])
    _run_faulty_case(
        "human_bug", f"QuixBugs `{program.name}`, human-written bug", program.buggy.source, program.name,
        program.tests, program.expected, ModelParams.from_dict(pooled["model_params"]),
        FusionParams.from_dict(pooled["fusion_params"]), program.fault_lines,
        f"line {list(program.fault_lines)} ({program.fault_kind}), from comparing with the benchmark's correct version",
        program.correct.source, out, say, config.EXTERNAL_STEP_LIMIT, config.EXTERNAL_TIMEOUT_S)
    return chosen["case_id"]


def run_demo(benchmark_dir: Path = pipeline.BENCHMARK_DIR, out_path: Path = DEMO_DIR,
             research_dir: Path = RESEARCH_DIR, log: Callable[[str], None] = print) -> Path:
    """Run the demonstration and write ``results/demo`` (transcript: DEMO.md)."""
    ex.require_complete(benchmark_dir)
    with_research = _research_available(research_dir)
    out = ex.OutputDir(out_path)
    transcript: list[str] = []

    def say(text: str) -> None:
        transcript.append(text)
        log(text)

    say("# PCG demonstration transcript (generated by `python -m pcg demo`)")
    if not with_research:
        say("\nThe research results are missing, so the fused model and the QuixBugs case are not shown. "
            "Run `python -m pcg research` first to include them.")
    lopo_fusion = (json.loads((research_dir / "fusion_params_lopo.json").read_text(encoding="utf-8"))
                   if with_research else {})
    selection = _select_cases(benchmark_dir)
    for key, (program_name, mutant_id) in selection.items():
        bench = BY_NAME[program_name]
        reference = Program.from_source(bench.source, bench.name)
        expected = oracle_signatures(reference.source, bench.name, bench.tests)
        source, description = _mutant_source(program_name, mutant_id)
        fusion = FusionParams.from_dict(lopo_fusion[program_name]) if with_research else None
        _run_faulty_case(key, f"{bench.name}, mutant `{mutant_id}`", source, bench.name, bench.tests, expected,
                         pipeline.load_params(program_name, path=benchmark_dir), fusion,
                         [int(mutant_id.split(":")[0])], description, reference.source, out, say)
    cases = {k: f"{p}:{m}" for k, (p, m) in selection.items()}
    if with_research:
        cases["human_bug"] = _run_human_bug(out, research_dir, say)
    _run_fault_free(out, benchmark_dir, say)
    _run_compile_error(benchmark_dir, say)
    (out.path / "DEMO.md").write_text("\n".join(transcript) + "\n", encoding="utf-8")
    out.finish({"cases": cases})
    return out.path
