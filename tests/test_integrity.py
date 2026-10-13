"""Acceptance tests: no hardcoding, no leakage, graph drives inference, real repair."""

import inspect
import json
from pathlib import Path

import numpy as np
import pytest

from pcg import analysis, config, experiments as ex, graph as graph_module, model as model_module, pipeline, reporting
from pcg.analysis import analyze
from pcg.benchmark_programs import BY_NAME
from pcg.config import ModelParams
from pcg.execution import oracle_signatures
from pcg.graph import fault_model_from_graph
from pcg.model import FaultModel, exact_posterior
from pcg.mutation import generate_mutants
from pcg.program import Program
from pcg.repair import repair_with_generator, targeted_repair, validate_patch

# Hand-set parameters used only to exercise the code paths in these tests.
PARAMS = ModelParams(prior_fault=0.1, theta=0.7, leak=0.01, static_tpr=0.2, static_fpr=0.05, provenance="test fixture")


def faulty_version(name: str, mutant_id: str):
    bench = BY_NAME[name]
    program = Program.from_source(bench.source, name)
    expected = oracle_signatures(program.source, name, bench.tests)
    mutant = next(m for m in generate_mutants(program) if m.mutant_id == mutant_id)
    return bench, expected, mutant


# --- A / E: the ranking follows the evidence, not a predetermined line -------

@pytest.mark.parametrize("mutant_id", ["4:ROR-flip:0", "6:ROR-flip:0", "8:ROR-flip:0"])
def test_most_suspicious_statement_moves_with_the_injected_fault(mutant_id):
    """Old project: line 4 was always blamed. Here the top statement tracks the real fault."""
    bench, expected, mutant = faulty_version("grade", mutant_id)
    result = analyze(mutant.source, "grade", bench.tests, expected, PARAMS)
    top_line, top_probability = result.ranking()[0]
    assert top_line == mutant.line
    assert top_probability > 0.5


def test_identical_code_with_different_test_outcomes_gives_different_posteriors():
    bench = BY_NAME["clamp"]
    program = Program.from_source(bench.source, "clamp")
    truth = oracle_signatures(program.source, "clamp", bench.tests)
    all_pass = analyze(bench.source, "clamp", bench.tests, truth, PARAMS)
    wrong_oracle = list(truth)
    wrong_oracle[1] = "return:999"  # pretend test 1 (x below lo) should return something else
    one_fail = analyze(bench.source, "clamp", bench.tests, wrong_oracle, PARAMS)
    assert all_pass.spectrum.n_failed == 0 and one_fail.spectrum.n_failed == 1
    assert not np.allclose(all_pass.posterior.marginals, one_fail.posterior.marginals)
    assert one_fail.ranking()[0][0] in (2, 3)  # the statements only that test's path singles out


def test_no_literal_line_numbers_or_probabilities_in_the_inference_path():
    for module in (analysis, model_module, graph_module):
        source = inspect.getsource(module)
        for forbidden in ('["4"]', "'4'", "0.72", "= -1.0", "-0.3"):
            assert forbidden not in source, f"{module.__name__} contains {forbidden!r}"


# --- F: ground truth cannot reach inference -----------------------------------

def test_inference_api_has_no_channel_for_ground_truth():
    for function in (analysis.analyze, analysis.analyze_run, graph_module.build_graph,
                     graph_module.fault_model_from_graph, model_module.exact_posterior, ex.pcg_scores):
        for parameter in inspect.signature(function).parameters:
            assert not any(word in parameter.lower() for word in ("truth", "fault_line", "label", "mutant"))
    for module in (analysis, model_module, graph_module):
        assert "truth" not in inspect.getsource(module).lower()
    # The experiment code passes a case's evidence, never its labels, to inference.
    assert "case.truth" not in inspect.getsource(ex.pcg_scores)
    assert "faulty_mask" not in inspect.getsource(ex.pcg_scores)


def test_parameters_for_a_program_exclude_that_programs_own_mutants():
    references = ex.load_references([BY_NAME["sign"], BY_NAME["clamp"], BY_NAME["gcd"]])
    cases, _ = ex.build_first_order_cases(references)
    params, counts = ex.lopo_params(cases, list(references))
    for name in references:
        others = sum(1 for c in cases if c.program_name != name)
        assert counts[name]["coverage"]["training_cases"] == others
        assert name in params[name]["coverage"].provenance


# --- B: the graph drives the posterior ------------------------------------------

def test_removing_one_graph_edge_changes_the_posterior():
    bench, expected, mutant = faulty_version("grade", "4:ROR-flip:0")
    result = analyze(mutant.source, "grade", bench.tests, expected, PARAMS)
    before = exact_posterior(fault_model_from_graph(result.graph, PARAMS)).marginals
    edge = next((u, v) for u, v, d in result.graph.edges(data=True)
                if d["kind"] == "in_scope" and result.graph.nodes[v]["failed"])
    edited = result.graph.copy()
    edited.remove_edge(*edge)
    after = exact_posterior(fault_model_from_graph(edited, PARAMS)).marginals
    assert not np.allclose(before, after)
    assert np.allclose(before, result.posterior.marginals)  # the reported posterior came from this graph


def test_posterior_is_not_a_per_line_function_of_per_line_evidence():
    """Two statements with identical own evidence get different posteriors because of the graph."""
    scopes = np.array([[1, 1, 0], [0, 1, 1], [0, 0, 1]], dtype=bool)
    failed = np.array([True, True, False])
    post = exact_posterior(FaultModel(np.full(3, 0.1), scopes, failed, 0.8, 0.01)).marginals
    # s0 and s2 are each in exactly one failing test; only s2 is also in a passing test, and
    # s1 (in both failing tests) explains both failures at once.
    assert post[1] > post[0] > post[2]


def test_graph_route_and_direct_route_build_the_same_model():
    bench, expected, mutant = faulty_version("is_prime", "5:ROR-flip:0")
    result = analyze(mutant.source, "is_prime", bench.tests, expected, PARAMS)
    direct = exact_posterior(FaultModel(np.full(len(result.program.statements), PARAMS.prior_fault),
                                        result.spectrum.coverage, result.spectrum.failed, PARAMS.theta, PARAMS.leak))
    assert np.allclose(result.posterior.marginals, direct.marginals, atol=1e-12)


def test_static_evidence_enters_as_a_likelihood_ratio():
    source = "def f(x):\n    y = x + 1\n    return z\n"
    result = analyze(source, "f", [[1]], ["return:2"], PARAMS, use_static=True)
    flagged = [line in (2, 3) for line in result.program.statements]
    ratio = np.where(flagged, PARAMS.static_tpr / PARAMS.static_fpr, (1 - PARAMS.static_tpr) / (1 - PARAMS.static_fpr))
    odds = PARAMS.prior_fault / (1 - PARAMS.prior_fault) * ratio
    assert np.allclose(result.model.prior, odds / (1 + odds))
    with pytest.raises(ValueError):  # static evidence cannot be requested without running the analyser
        fault_model_from_graph(analyze(source, "f", [[1]], ["return:2"], PARAMS).graph, PARAMS, use_static=True)


def test_compile_failure_yields_a_diagnostic_and_no_probabilities():
    result = analyze("def f(x):\n    return x +\n", "f", [[1]], ["return:1"], PARAMS)
    assert result.compile_error is not None and result.compile_error.line == 2
    assert result.posterior is None and result.graph is None


# --- K: repair is real -----------------------------------------------------------

def test_targeted_repair_produces_a_validated_patch_inside_the_region():
    bench, expected, mutant = faulty_version("grade", "4:ROR-flip:0")
    program = Program.from_source(mutant.source, "grade")
    result = analyze(mutant.source, "grade", bench.tests, expected, PARAMS)
    report = targeted_repair(program, bench.tests, expected, [line for line, _ in result.ranking()])
    assert report.repaired and report.tests_failed_before > 0 and report.tests_failed_after == 0
    old, new = program.source.splitlines(), report.accepted_source.splitlines()
    changed = [i for i, (a, b) in enumerate(zip(old, new), 1) if a != b]
    assert len(changed) == 1 and changed[0] in report.region_lines  # one line, inside the region
    (verdict,) = validate_patch([report.accepted_source], "grade", bench.tests, expected)
    assert verdict["accepted"]  # independent re-validation
    assert [a.accepted for a in report.attempts].count(True) == 1 and report.attempts[-1].accepted


def test_repair_reports_failure_when_the_region_cannot_fix_the_fault():
    bench, expected, mutant = faulty_version("grade", "4:ROR-flip:0")
    program = Program.from_source(mutant.source, "grade")
    wrong_region = [6, 8]  # two other conditions; the fault is on line 4
    assert mutant.line == 4
    report = targeted_repair(program, bench.tests, expected, wrong_region, top_k=2)
    assert not report.repaired and report.accepted_source is None and report.tests_failed_after is None
    assert all(not a.accepted for a in report.attempts) and report.attempts


def test_external_patch_generator_is_checked_not_trusted():
    bench, expected, mutant = faulty_version("grade", "4:ROR-flip:0")
    program = Program.from_source(mutant.source, "grade")
    reference = Program.from_source(bench.source, "grade").source
    region = [mutant.line]

    outside = program.source.replace("return 'F'", "return 'A'")      # edits a line outside the region
    rewrite = "def grade(score):\n    return 'A'\n"                    # rewrites the whole function
    proposals = iter([outside, rewrite, "def grade(score:\n", None, reference])
    report = repair_with_generator(program, bench.tests, expected, region, lambda *_: next(proposals),
                                   top_k=1, max_attempts=5)
    reasons = [a.reason for a in report.attempts]
    assert "outside region" in reasons[0]
    assert "number of lines" in reasons[1]
    assert not report.attempts[2].compiles
    assert reasons[3] == "no candidate"
    assert report.attempts[4].accepted and report.repaired and report.accepted_source == reference

    assert "score <= 90" in program.source  # the injected fault
    always_wrong = repair_with_generator(program, bench.tests, expected, region,
                                         lambda p, r, n: p.source.replace("score <= 90", "score < 0"), top_k=1, max_attempts=2)
    assert not always_wrong.repaired  # a patch that still fails tests is rejected
    assert all("fails test" in a.reason for a in always_wrong.attempts)


# --- J / N: results cannot be stale or inconsistent -------------------------------

def test_output_directory_is_emptied_and_incomplete_runs_are_detected(tmp_path):
    target = tmp_path / "run"
    target.mkdir()
    (target / "old_result.json").write_text("{}", encoding="utf-8")
    out = ex.OutputDir(target)
    assert not (target / "old_result.json").exists()        # stale output is removed at start
    out.write_json("a.json", {"x": 1})
    with pytest.raises(FileNotFoundError):                   # no manifest yet = not a finished run
        ex.require_complete(target)
    out.finish()
    assert ex.require_complete(target)["status"] == "complete"


@pytest.mark.skipif(not (pipeline.BENCHMARK_DIR / "MANIFEST.json").exists(), reason="benchmark has not been run")
def test_published_summary_matches_the_result_files():
    import hashlib

    manifest = ex.require_complete(pipeline.BENCHMARK_DIR)
    for name, digest in manifest["files"].items():
        data = (pipeline.BENCHMARK_DIR / name).read_bytes()
        if Path(name).suffix in {".json", ".jsonl", ".csv", ".md", ".txt", ".py"}:
            data = data.replace(b"\r\n", b"\n")
        assert hashlib.sha256(data).hexdigest() == digest, f"{name} was modified after the run"
    stored = (pipeline.BENCHMARK_DIR / "SUMMARY.md").read_text(encoding="utf-8")
    assert stored == reporting.build_summary(pipeline.BENCHMARK_DIR)  # every number comes from the data files


@pytest.mark.skipif(not (pipeline.BENCHMARK_DIR / "MANIFEST.json").exists(), reason="benchmark has not been run")
def test_stored_cases_keep_ground_truth_separate_and_counts_agree():
    manifest = ex.require_complete(pipeline.BENCHMARK_DIR)
    lines = (pipeline.BENCHMARK_DIR / "cases.jsonl").read_text(encoding="utf-8").splitlines()
    cases = [json.loads(line) for line in lines]
    assert len(cases) == manifest["counts"]["mutants_valid"]
    assert sum(c["classification"] == "detected" for c in cases) == manifest["counts"]["mutants_detected"]
    for case in cases[:50]:
        truth = case["ground_truth_EVALUATION_ONLY"]["fault_lines"]
        assert len(truth) == 1 and truth[0] in case["statements"]
        if case["classification"] == "detected":  # a detected fault was executed by every failing test
            for failed, covered in zip(case["test_failed"], case["coverage_lines_per_test"]):
                assert not failed or truth[0] in covered


# --- reproducibility ---------------------------------------------------------------

def test_seeded_experiments_are_reproducible():
    references = ex.load_references([BY_NAME["sign"], BY_NAME["clamp"]])
    first, _ = ex.build_two_fault_cases(references, seed=config.SEED)
    second, _ = ex.build_two_fault_cases(references, seed=config.SEED)
    other, _ = ex.build_two_fault_cases(references, seed=config.SEED + 1)
    assert [c.case_id for c in first] == [c.case_id for c in second]
    assert [c.case_id for c in first] != [c.case_id for c in other]
    for case in first:
        assert len(case.truth.fault_lines) == 2 and int(case.faulty_mask.sum()) == 2


def test_undetected_mutants_are_classified_and_never_scored_as_localised():
    references = ex.load_references([BY_NAME["clamp"]])
    cases, _ = ex.build_first_order_cases(references)
    params = {mode: ex.pooled_params(cases, mode) for mode in ("coverage", "slice")}  # any parameters will do here
    undetected = [c for c in cases if not c.detected]
    assert undetected, "clamp is known to have mutants its tests cannot see"
    result = ex.run_first_order(cases, {"clamp": params})
    assert len(result["rows"]) == len(cases) - len(undetected)
    assert not {c.case_id for c in undetected} & {row["case_id"] for row in result["rows"]}
