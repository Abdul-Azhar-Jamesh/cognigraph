"""Tests of the version-3 components (research/v3/MATHEMATICAL_DESIGN.md, section 8)."""

import inspect

import numpy as np
import pytest

from pcg import config, experiments as ex, metrics, research
from pcg.analysis import analyze_run
from pcg.barinel import _log_likelihood, barinel, barinel_candidates, max_likelihood, minimal_hitting_sets
from pcg.benchmark_programs import BY_NAME
from pcg.config import ModelParams
from pcg.discriminative import Recalibration, fit_logistic, fit_recalibration, statement_features
from pcg.execution import run_sources
from pcg.fusion import (FusionCase, FusionParams, effective_prior, estimate_fusion_params,
                        mutation_likelihood_ratio, size_aware_prior)
from pcg.graph import fault_model_from_graph
from pcg.mbfl import (CONTEXT_ALL, CONTEXT_NONE, CONTEXT_PART, LEVEL_NO_EFFECT, MutationEvidence, coverage_context,
                      hybrid_average, mutation_evidence)
from pcg.model import FaultModel, exact_posterior
from pcg.program import Program
from pcg.quixbugs import _json_equal, fault_lines_from_diff, load_quixbugs

PARAMS = ModelParams(prior_fault=0.1, theta=0.8, leak=0.01, provenance="test fixture")
# The illustrative tables of the worked example (not estimates).
FUSION = FusionParams(mu=1.0, level_given_fault=(0.05, 0.15, 0.05, 0.15, 0.60),
                      level_given_clean=(0.10, 0.60, 0.10, 0.10, 0.10),
                      level_given_fault_nocontext=(0.05, 0.15, 0.05, 0.15, 0.60),
                      level_given_clean_nocontext=(0.10, 0.60, 0.10, 0.10, 0.10), provenance="worked example")
SCOPES = np.array([[1, 1, 0], [0, 1, 1], [0, 0, 1]], dtype=bool)
FAILED = np.array([True, False, False])


def evidence(levels, contexts):
    n = len(levels)
    return MutationEvidence(np.array(levels), np.array(contexts), np.zeros(n), np.zeros(n), 0, 0)


# --- T12: the worked example of the design document -----------------------------------

def test_worked_example_of_the_design_document():
    ev = evidence([4, 1, 1], coverage_context(SCOPES, FAILED))
    assert ev.contexts.tolist() == [CONTEXT_ALL, CONTEXT_ALL, CONTEXT_NONE]
    spectrum_only = exact_posterior(FaultModel(effective_prior(3, 0.1, FUSION, size_aware=True), SCOPES, FAILED, 0.8, 0.01))
    assert np.round(spectrum_only.marginals, 4).tolist() == [0.8327, 0.2378, 0.0196]
    assert round(spectrum_only.p_no_fault, 4) == 0.0182
    prior = effective_prior(3, 0.1, FUSION, ev, size_aware=True, use_mutation=True)
    assert np.round(prior, 4).tolist() == [0.75, 0.1111, 0.3333]
    fused = exact_posterior(FaultModel(prior, SCOPES, FAILED, 0.8, 0.01))
    assert np.round(fused.marginals, 4).tolist() == [0.988, 0.0367, 0.0196]
    assert round(fused.p_no_fault, 4) == 0.0039
    no_context = effective_prior(3, 0.1, FUSION, ev, size_aware=True, use_mutation=True, use_context=False)
    assert np.round(no_context, 4).tolist() == [0.75, 0.1111, 0.1111]
    doubled = exact_posterior(FaultModel(no_context, SCOPES, FAILED, 0.8, 0.01)).marginals
    assert round(float(doubled[2]), 4) == 0.005  # the coverage fact counted twice
    recal = Recalibration(0.7, -0.3).apply(np.array([0.9, 0.5, 0.1]))
    assert np.round(recal, 4).tolist() == [0.7752, 0.4256, 0.1373]


# --- T1, T2, T4, T6: properties of the new factors --------------------------------------

def test_neutral_evidence_gives_back_the_spectrum_only_model():
    neutral = FusionParams(1.0, (0.2,) * 5, (0.2,) * 5, (0.2,) * 5, (0.2,) * 5)
    ev = evidence([4, 1, 0], [CONTEXT_ALL, CONTEXT_ALL, CONTEXT_ALL])
    assert np.allclose(effective_prior(3, 0.1, neutral, ev, use_mutation=True), 0.1)
    assert np.allclose(effective_prior(3, 0.1), 0.1)  # the version-2 prior is the default


def test_likelihood_ratio_is_exactly_one_outside_the_all_context():
    for level in range(config.MUTATION_LEVELS):
        ev = evidence([level, level, level], [CONTEXT_NONE, CONTEXT_PART, CONTEXT_ALL])
        ratio = mutation_likelihood_ratio(ev, FUSION)
        assert ratio[0] == 1.0 and ratio[1] == 1.0
        assert ratio[2] == pytest.approx(FUSION.level_given_fault[level] / FUSION.level_given_clean[level])


def test_stronger_mutation_evidence_raises_the_posterior():
    values = []
    for level in (1, 0, 3, 4):  # likelihood ratios 0.25, 0.5, 1.5, 6
        ev = evidence([level, 1, 1], [CONTEXT_ALL, CONTEXT_ALL, CONTEXT_NONE])
        prior = effective_prior(3, 0.1, FUSION, ev, size_aware=True, use_mutation=True)
        values.append(exact_posterior(FaultModel(prior, SCOPES, FAILED, 0.8, 0.01)).marginals[0])
    assert values == sorted(values)


@pytest.mark.parametrize("n", [2, 3, 5, 16, 100])
def test_size_aware_prior_keeps_the_expected_number_of_faults_constant(n):
    assert n * size_aware_prior(n, 1.0) == pytest.approx(1.0)
    assert size_aware_prior(1, 1.0) == 0.5  # capped
    with pytest.raises(ValueError):
        size_aware_prior(0, 1.0)


def test_version_three_options_require_their_parameters():
    with pytest.raises(ValueError):
        effective_prior(3, 0.1, None, size_aware=True)
    with pytest.raises(ValueError):
        effective_prior(3, 0.1, FUSION, None, use_mutation=True)
    with pytest.raises(ValueError):
        FusionParams(1.0, (0.5, 0.5, 0, 0, 0), (0.2,) * 5, (0.2,) * 5, (0.2,) * 5)


# --- T5: estimation --------------------------------------------------------------------

def test_mutation_tables_are_recovered_from_simulated_data():
    rng = np.random.default_rng(4)
    true_fault, true_clean = np.array([0.1, 0.05, 0.05, 0.1, 0.7]), np.array([0.2, 0.55, 0.15, 0.08, 0.02])
    cases = []
    for _ in range(4000):
        n = int(rng.integers(4, 10))
        faulty = np.zeros(n, dtype=bool)
        faulty[rng.integers(n)] = True
        contexts = np.where(faulty | (rng.random(n) < 0.5), CONTEXT_ALL, CONTEXT_NONE)
        levels = np.array([rng.choice(5, p=true_fault if f else true_clean) if c == CONTEXT_ALL else LEVEL_NO_EFFECT
                           for f, c in zip(faulty, contexts)])
        cases.append(FusionCase(MutationEvidence(levels, contexts, np.zeros(n), np.zeros(n), 0, 0), faulty))
    params, counts = estimate_fusion_params(cases, "simulated")
    assert params.mu == 1.0
    assert np.allclose(params.level_given_fault, true_fault, atol=0.03)
    assert np.allclose(params.level_given_clean, true_clean, atol=0.02)
    assert sum(params.level_given_fault) == pytest.approx(1.0) and min(params.level_given_clean) > 0
    assert counts["training_cases"] == 4000
    # Ignoring the context mixes in statements whose level is forced, which biases the clean table.
    assert params.level_given_clean_nocontext[1] > params.level_given_clean[1] + 0.05


# --- T3, T9: mutation evidence and the mutation-based baselines --------------------------

def test_levels_metallaxis_and_muse_on_a_hand_computed_example():
    statements = [10, 20, 30]
    coverage = np.array([[1, 1, 1], [1, 1, 0], [0, 1, 1]], dtype=bool)
    failed = np.array([True, False, False])
    base, expected = ["a", "b", "c"], ["x", "b", "c"]
    variants = [
        (10, ["x", "b", "c"]),  # makes the failing test pass, breaks nothing
        (10, ["a", "b", "z"]),  # breaks a passing test
        (20, ["q", "b", "c"]),  # changes the failing test's behaviour without fixing it
        (20, ["a", "k", "c"]),  # breaks a passing test
        (20, None),             # did not compile or timed out: ignored
    ]
    ev = mutation_evidence(statements, coverage, failed, base, expected, variants)
    assert ev.levels.tolist() == [4, 1, 0]
    assert ev.contexts.tolist() == [CONTEXT_ALL, CONTEXT_ALL, CONTEXT_ALL]
    assert (ev.n_variants, ev.n_usable) == (5, 4)
    # Metallaxis: killed failing / sqrt(total failing * killed); maximum over a statement's variants.
    assert ev.metallaxis.tolist() == [1.0, 1.0, 0.0]
    # MUSE: alpha = total f2p / total p2f = 1 / 2; mean of (f2p - alpha * p2f) over variants.
    assert ev.muse.tolist() == pytest.approx([0.25, -0.25, -1.25])
    assert hybrid_average(np.array([0.5, 1.0]), np.array([1.0, 0.0])).tolist() == [0.75, 0.5]


def test_no_failing_test_means_no_mutation_evidence():
    ev = mutation_evidence([1, 2], np.ones((2, 2), dtype=bool), np.array([False, False]), ["a", "b"], ["a", "b"],
                           [(1, ["z", "b"])])
    assert ev.levels.tolist() == [0, 0] and ev.contexts.tolist() == [CONTEXT_NONE, CONTEXT_NONE]
    assert np.all(mutation_likelihood_ratio(ev, FUSION) == 1.0)


def real_case(name="grade", mutant_id="4:ROR-flip:0"):
    references = ex.load_references([BY_NAME[name]])
    cases, _ = ex.build_first_order_cases(references)
    return references, cases, next(c for c in cases if c.case_id == f"{name}:{mutant_id}")


def test_variants_of_statements_no_failing_test_runs_cannot_change_a_failing_test():
    """The structural fact behind the context conditioning, checked on real executions."""
    _, cases, _ = real_case()
    detected = [c for c in cases if c.detected]
    found, _, cost = research.collect_evidence(detected, config.STEP_LIMIT, config.SUBPROCESS_TIMEOUT_S, None,
                                               log=lambda _m: None)
    checked = 0
    for case in detected:
        ev = found[case.case_id]
        outside = ev.contexts == CONTEXT_NONE
        assert np.all(ev.levels[outside] <= LEVEL_NO_EFFECT)
        checked += int(outside.sum())
    assert checked > 0 and cost["variant_texts_run"] > 0


def test_mutation_node_in_the_graph_drives_the_posterior():
    _, cases, case = real_case()
    found, _, _ = research.collect_evidence([case], config.STEP_LIMIT, config.SUBPROCESS_TIMEOUT_S, None,
                                            log=lambda _m: None)
    ev = found[case.case_id]
    result = analyze_run(case.program, case.run, case.expected, PARAMS, mutation=ev, fusion=FUSION,
                         size_aware=True, use_mutation=True)
    direct = research.posterior(case, effective_prior(len(case.program.statements), PARAMS.prior_fault, FUSION, ev,
                                                      size_aware=True, use_mutation=True), PARAMS)
    assert np.allclose(result.posterior.marginals, direct, atol=1e-12)  # graph route = direct route
    line = case.truth.fault_lines[0]
    assert result.graph.nodes[f"m:{line}"]["context"] == CONTEXT_ALL
    edited = result.graph.copy()
    edited.remove_node(f"m:{line}")
    after = exact_posterior(fault_model_from_graph(edited, PARAMS, fusion=FUSION, size_aware=True, use_mutation=True))
    assert not np.allclose(after.marginals, result.posterior.marginals)
    with pytest.raises(ValueError):  # mutation evidence cannot be requested from a graph that has none
        plain = analyze_run(case.program, case.run, case.expected, PARAMS)
        fault_model_from_graph(plain.graph, PARAMS, fusion=FUSION, use_mutation=True)


# --- T8: Barinel ------------------------------------------------------------------------

def test_minimal_hitting_sets_of_the_first_example_in_the_barinel_paper():
    # Table I of the paper; the text concludes that {c1, c2} is the only diagnosis.
    coverage = np.array([[1, 0, 1], [0, 1, 1], [1, 0, 0], [0, 1, 0], [1, 1, 1]], dtype=bool)
    failed = np.array([True, True, True, True, False])
    assert minimal_hitting_sets(coverage[failed], 3) == [(0, 1)]
    assert barinel(coverage, failed, 0.1).tolist() == [1.0, 1.0, 0.0]


def test_barinel_likelihood_matches_the_papers_worked_example():
    coverage = np.array([[1, 1, 0], [0, 1, 1], [1, 0, 0], [1, 0, 1]], dtype=bool)
    failed = np.array([True, True, True, False])
    # The paper reports Pr(e|d1) = 0.185 at h = (0.47, 0.19) and Pr(e|d2) = 0.036 at h = (0.41, 0.50).
    d1, d2 = coverage[:, [0, 1]], coverage[:, [0, 2]]
    assert np.exp(_log_likelihood(np.array([0.47, 0.19]), d1, failed)) == pytest.approx(0.185, abs=0.002)
    assert np.exp(_log_likelihood(np.array([0.41, 0.50]), d2, failed)) == pytest.approx(0.036, abs=0.001)
    # Those are not the exact maxima: Pr(e|d1) = (1 - h1 h2)(1 - h2)(1 - h1) h1 decreases in h2,
    # so the maximum is at h2 = 0, h1 = 1/2 with value 1/4; for d2 it is 1/27 at h1 = 1/3, h3 = 1/2.
    value1, h1 = max_likelihood(d1, failed)
    value2, h2 = max_likelihood(d2, failed)
    assert value1 == pytest.approx(0.25, abs=1e-6) and h1 == pytest.approx([0.5, 0.0], abs=1e-3)
    assert value2 == pytest.approx(1 / 27, abs=1e-6) and h2 == pytest.approx([1 / 3, 0.5], abs=1e-3)
    ranked = barinel_candidates(coverage, failed, 0.1)
    assert [c for c, _ in ranked] == [(0, 1), (0, 2)]          # same order as in the paper
    assert ranked[0][1] == pytest.approx(0.25 / (0.25 + 1 / 27))
    assert sum(p for _, p in ranked) == pytest.approx(1.0)


def test_barinel_single_fault_closed_form_and_edge_cases():
    coverage = np.array([[1, 1], [1, 0], [1, 1], [0, 1]], dtype=bool)
    failed = np.array([True, True, False, False])
    value, h = max_likelihood(coverage[:, [0]], failed)       # 1 pass and 2 fails among its 3 runs
    assert h[0] == pytest.approx(1 / 3) and value == pytest.approx((1 / 3) * (2 / 3) ** 2)
    assert max_likelihood(coverage[:, [1]], failed)[0] == 0.0  # does not cover the second failing run
    assert barinel(coverage, np.zeros(4, dtype=bool), 0.1).tolist() == [0.0, 0.0]


# --- T10, T7: logistic regression and recalibration ---------------------------------------

def test_logistic_regression_recovers_known_coefficients_and_is_stationary():
    rng = np.random.default_rng(0)
    x = rng.normal(size=(20000, 3))
    true_w, true_b = np.array([1.0, -2.0, 0.5]), -0.7
    y = (rng.random(20000) < 1 / (1 + np.exp(-(x @ true_w + true_b)))).astype(float)
    model = fit_logistic(x, y, l2=1e-6)
    assert model.converged
    assert np.allclose(model.weights / model.scale, true_w, atol=0.06)
    assert model.intercept - (model.mean / model.scale) @ model.weights == pytest.approx(true_b, abs=0.06)
    p = model.predict(x)
    design = np.column_stack([(x - model.mean) / model.scale, np.ones(len(y))])
    gradient = design.T @ (p - y) + np.append(1e-6 * model.weights, 0.0)
    assert np.max(np.abs(gradient)) < 1e-4  # first-order optimality
    assert metrics.expected_calibration_error(p, y) < 0.02  # calibrated on its own distribution
    with pytest.raises(ValueError):
        fit_logistic(np.zeros((0, 2)), np.zeros(0))


def test_recalibration_fixes_probabilities_and_cannot_change_a_ranking():
    rng = np.random.default_rng(1)
    p = rng.uniform(0.01, 0.99, 50000)
    z = np.log(p / (1 - p))
    y = (rng.random(50000) < 1 / (1 + np.exp(-(0.6 * z - 0.4)))).astype(float)
    fitted = fit_recalibration(p, y)
    assert fitted.a == pytest.approx(0.6, abs=0.03) and fitted.b == pytest.approx(-0.4, abs=0.03)
    assert metrics.brier_score(fitted.apply(p), y) < metrics.brier_score(p, y)
    scores = rng.uniform(0, 1, 12)
    for fault in range(12):
        assert metrics.rank_metrics(scores, fault) == metrics.rank_metrics(fitted.apply(scores), fault)
    # A map that would reverse rankings is refused: perfectly anti-correlated labels give the identity.
    assert fit_recalibration(np.array([0.9, 0.8, 0.2, 0.1] * 50), np.array([0, 0, 1, 1] * 50)) == Recalibration(1.0, 0.0)


def test_statement_features_have_the_documented_layout():
    coverage = np.array([[1, 1, 0], [1, 0, 1], [1, 1, 1], [0, 1, 0]], dtype=bool)
    failed = np.array([True, True, False, False])
    spectrum = statement_features(coverage, failed)
    assert spectrum.shape == (3, 5)
    assert spectrum[:, 0].tolist() == [1.0, 0.5, 0.5] and spectrum[:, 4].tolist() == [1.0, 0.0, 0.0]
    ev = MutationEvidence(np.array([4, 1, 0]), coverage_context(coverage, failed), np.array([1.0, 0.2, 0.0]),
                          np.array([0.5, -0.1, -1.1]), 3, 3)
    fused = statement_features(coverage, failed, ev, np.array([False, True, False]))
    assert fused.shape == (3, 13)
    assert fused[:, 7:12].tolist() == [[0, 0, 0, 0, 1], [0, 1, 0, 0, 0], [1, 0, 0, 0, 0]] and fused[:, 12].tolist() == [0, 1, 0]


# --- T11: selective localisation ----------------------------------------------------------

def test_risk_coverage_on_a_hand_computed_example():
    confidence, correct = np.array([0.9, 0.8, 0.3, 0.1]), np.array([1.0, 1.0, 0.0, 0.0])
    coverage, risk = metrics.risk_coverage(confidence, correct)
    assert coverage.tolist() == [0.25, 0.5, 0.75, 1.0]
    assert risk.tolist() == pytest.approx([0.0, 0.0, 1 / 3, 0.5])
    assert metrics.aurc(confidence, correct) == pytest.approx((0 + 0 + 1 / 3 + 0.5) / 4)
    reference = metrics.aurc_reference_values(correct)
    assert reference["oracle"] == metrics.aurc(confidence, correct)      # this confidence is already ideal
    assert reference["uninformative"] == pytest.approx(0.5)              # ties everywhere: the error rate
    assert metrics.aurc(-confidence, correct) > reference["uninformative"]  # a perverse confidence is worse
    # Tied confidences are averaged, so the order of tied cases does not matter.
    assert metrics.aurc(np.array([0.5, 0.5, 0.5]), np.array([1.0, 0.0, 0.0])) == metrics.aurc(
        np.array([0.5, 0.5, 0.5]), np.array([0.0, 0.0, 1.0]))
    assert metrics.brier_skill(np.array([1.0, 0.0]), np.array([1, 0]), np.array([0.5, 0.5])) == 1.0


# --- T13: no leakage ------------------------------------------------------------------------

def test_scoring_receives_no_ground_truth_and_folds_exclude_the_held_out_program():
    for function in (research.score_case, research.posterior, research.features_of, effective_prior,
                     mutation_likelihood_ratio, mutation_evidence):
        for parameter in inspect.signature(function).parameters:
            assert not any(word in parameter.lower() for word in ("truth", "fault_line", "label", "faulty"))
    source = inspect.getsource(research.score_case)
    assert "case.truth" not in source and "faulty_mask" not in source

    references = ex.load_references([BY_NAME["sign"], BY_NAME["clamp"], BY_NAME["gcd"]])
    cases, _ = ex.build_first_order_cases(references)
    detected = [c for c in cases if c.detected]
    found, _, _ = research.collect_evidence(detected, config.STEP_LIMIT, config.SUBPROCESS_TIMEOUT_S, None,
                                            log=lambda _m: None)
    for c in cases:
        found.setdefault(c.case_id, MutationEvidence(*(np.zeros(len(c.program.statements), dtype=int),) * 2,
                                                     *(np.zeros(len(c.program.statements)),) * 2, 0, 0))
    d1 = research.run_d1(cases, found, list(references), log=lambda _m: None)
    for held_out, fold in d1["trained"].items():
        others = [c for c in detected if c.program_name != held_out]
        expected, counts = estimate_fusion_params([FusionCase(found[c.case_id], c.faulty_mask) for c in others], "x")
        assert fold.fusion.level_given_fault == expected.level_given_fault
        assert counts["training_cases"] == len(others)
        assert held_out in fold.params.provenance
    assert len(d1["rows"]) == len(detected) and len(d1["labels"]) == sum(len(c.program.statements) for c in detected)


# --- external benchmark and the language features it needs ------------------------------------

def test_nested_functions_generators_and_recursion_are_traced():
    source = (
        "def outer(xs):\n"
        "    def keep(x):\n"
        "        return x > 0\n"
        "    for x in xs:\n"
        "        if keep(x):\n"
        "            yield x\n"
    )
    program = Program.from_source(source, "outer")
    assert program.statements == (3, 4, 5, 6, 7)  # the canonical form puts a blank line before a nested def
    (run,) = run_sources([program.source], "outer", [[[1, -1, 2]], [[]]])
    assert run.tests[0].signature == "return:[1, 2]" and run.tests[0].value_json == "[1, 2]"
    assert sorted(run.tests[0].lines) == [3, 4, 5, 6, 7] and sorted(run.tests[1].lines) == [3, 5]
    recursive = Program.from_source("def fact(n):\n    if n <= 1:\n        return 1\n    return n * fact(n - 1)\n", "fact")
    (run,) = run_sources([recursive.source], "fact", [[4]])
    assert run.tests[0].signature == "return:24" and run.tests[0].exit_line == 4


def test_ground_truth_lines_from_a_diff():
    correct = Program.from_source("def f(a, b):\n    c = a + b\n    if c > 0:\n        return c\n    return 0\n", "f")
    modified = Program.from_source("def f(a, b):\n    c = a - b\n    if c > 0:\n        return c\n    return 0\n", "f")
    assert fault_lines_from_diff(modified, correct) == ((2,), "modified line")
    missing = Program.from_source("def f(a, b):\n    if c > 0:\n        return c\n    return 0\n", "f")
    assert fault_lines_from_diff(missing, correct) == ((2,), "missing line")  # the statement after the gap
    assert fault_lines_from_diff(correct, correct) == ((), "none")


def test_json_comparison_used_for_the_oracle_check():
    assert _json_equal([1, [2.0, 3]], [1, [2.0000000001, 3]]) and not _json_equal([1, 2], [1, 3])
    assert not _json_equal(True, 1) and _json_equal({"a": [1]}, {"a": [1]}) and not _json_equal("1", 1)


@pytest.mark.skipif(not (config.QUIXBUGS_DIR / "json_testcases").is_dir(), reason="QuixBugs is not available")
def test_quixbugs_loader_checks_the_oracle_and_finds_one_fault_per_program():
    programs, report = load_quixbugs()
    assert len(report) == 31 and len(programs) >= 25
    for program in programs:
        assert len(program.fault_lines) >= 1 and set(program.fault_lines) <= set(program.buggy.statements)
        assert len(program.tests) == len(program.expected) >= 1
        assert all(signature.startswith("return:") for signature in program.expected)
    with pytest.raises(FileNotFoundError):
        load_quixbugs(config.PROJECT_ROOT / "no_such_folder")


def test_behaviour_signatures_do_not_contain_memory_addresses():
    """A returned generator or function prints with its address; signatures must be the same in every process."""
    source = "def f(n):\n    return [(x for x in range(n)), len]\n"
    program = Program.from_source(source, "f")
    first, second = (run_sources([program.source], "f", [[2]])[0].tests[0].signature for _ in range(2))
    assert first == second and "0x?" in first and "generator object" in first
