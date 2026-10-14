"""Tests of the version 4 additions: interventional model, FLITSR, HumanEvalFix loading, metrics.

The checks of the inference are independent of the implementation: closed
forms, the version 2 exact inference, and a brute-force enumeration written
here with plain loops.
"""

import inspect
from itertools import combinations, product

import numpy as np
import pytest

from pcg import metrics, v4
from pcg.flitsr import flitsr
from pcg.humanevalfix import extract_test_inputs
from pcg.interventional import (Enumeration, InterventionParams, VariantObservation, enumerate_configurations,
                                estimate_intervention_params, interventional_posterior, sole_cause_probability,
                                summarise)
from pcg.model import FaultModel, exact_posterior
from pcg.program import Program
from pcg.synthetic import World, simulate

GRID, WEIGHTS, LEAK = (0.2, 0.5, 0.9), (0.3, 0.4, 0.3), 0.01
PARAMS = InterventionParams(alpha=0.8, rho=(1.0,), gamma=(0.95,), beta=(0.05,), kappa=(0.7, 0.3), psi=(0.03, 0.6),
                            eta=(0.2, 0.8))


def _observation(column, coverage, failed, flips_on, breaks=0):
    failing = np.flatnonzero(coverage[:, column] & failed)
    return VariantObservation(column, failing, np.isin(failing, flips_on), int((coverage[:, column] & ~failed).sum()), breaks)


def _random_instance(seed, n=4, m=5, variants_per_statement=2):
    rng = np.random.default_rng(seed)
    while True:
        coverage = rng.random((m, n)) < 0.7
        coverage[:, 0] = True
        failed = rng.random(m) < 0.5
        if failed.any() and (~failed).any():
            break
    observations = []
    for s in range(n):
        for _ in range(int(rng.integers(0, variants_per_statement + 1))):
            failing = np.flatnonzero(coverage[:, s] & failed)
            passing = int((coverage[:, s] & ~failed).sum())
            observations.append(VariantObservation(s, failing, rng.random(len(failing)) < 0.5, passing,
                                                   int(rng.integers(0, passing + 1))))
    return rng.uniform(0.1, 0.3, n), coverage, failed, observations


def _nonrepair(obs, p):
    f, t = int(obs.flips.sum()), len(obs.flips)
    return sum(k * psi ** f * (1 - psi) ** (t - f) * eta ** obs.n_breaks * (1 - eta) ** (obs.n_passing - obs.n_breaks)
               for k, psi, eta in zip(p.kappa, p.psi, p.eta))


def _brute_force(prior, coverage, failed, observations, p, layer, max_faults):
    """Marginals by explicit enumeration of configurations, exposure rates, repair choices and sole causes."""
    m, n = coverage.shape
    by = {}
    for obs in observations:
        by.setdefault(obs.column, []).append(obs)
    weights = {}
    for r in range(max_faults + 1):
        for config in combinations(range(n), r):
            total = 0.0
            for theta, weight in zip(GRID, WEIGHTS):
                value = weight
                for i in range(n):
                    value *= prior[i] if i in config else 1 - prior[i]
                for j in range(m):
                    k = sum(coverage[j, i] for i in config)
                    passes = (1 - LEAK) * (1 - theta) ** k
                    value *= (1 - passes) if failed[j] else passes

                def sole(k):
                    return (1 - LEAK) * theta * (1 - theta) ** (k - 1) / (1 - (1 - LEAK) * (1 - theta) ** k)

                statements = [s for s in config if s in by]
                if layer == "composite":
                    for s in statements:
                        inner = 1.0
                        for obs in by[s]:
                            rep = p.beta[0] ** obs.n_breaks * (1 - p.beta[0]) ** (obs.n_passing - obs.n_breaks)
                            for j, z in zip(obs.failing, obs.flips):
                                q = p.gamma[0] * sole(sum(coverage[j, i] for i in config))
                                rep *= q if z else 1 - q
                            inner *= 1 + p.rho[0] * (rep / _nonrepair(obs, p) - 1)
                        value *= (1 - p.alpha) + p.alpha * inner
                else:
                    variant_layer = 0.0
                    for choice in product(*[[None] + list(range(len(by[s]))) for s in statements]):
                        term = 1.0
                        for s, a in zip(statements, choice):
                            if a is None:
                                term *= 1 - p.alpha
                            else:
                                obs = by[s][a]
                                term *= (p.alpha / len(by[s]) * p.beta[0] ** obs.n_breaks
                                         * (1 - p.beta[0]) ** (obs.n_passing - obs.n_breaks) / _nonrepair(obs, p))
                        for j in np.flatnonzero(failed):
                            scope = [i for i in config if coverage[j, i]]
                            if not scope:
                                continue
                            q = sole(len(scope))
                            chosen = [(s, by[s][a]) for s, a in zip(statements, choice) if a is not None and coverage[j, s]]
                            likelihood = 0.0
                            for cause in scope + [None]:
                                part = q if cause is not None else 1 - len(scope) * q
                                for s, obs in chosen:
                                    z = bool(obs.flips[list(obs.failing).index(j)])
                                    hit = p.gamma[0] if s == cause else p.delta
                                    part *= hit if z else 1 - hit
                                likelihood += part
                            term *= likelihood
                        variant_layer += term
                    value *= variant_layer
                total += value
            weights[config] = total
    norm = sum(weights.values())
    return np.array([sum(w for c, w in weights.items() if i in c) for i in range(n)]) / norm


def test_sole_cause_probability_closed_forms():
    for theta in (0.1, 0.5, 0.9):
        assert sole_cause_probability(1, theta, 0.0) == pytest.approx(1.0)
        assert sole_cause_probability(2, theta, 0.0) == pytest.approx((1 - theta) / (2 - theta))
        assert sole_cause_probability(3, theta, 0.0) == pytest.approx((1 - theta) ** 2 / (3 - 3 * theta + theta ** 2))
    # the events "statement i is the sole cause" are disjoint, so k of them cannot have probability above one
    assert 3 * sole_cause_probability(3, 0.01, 0.05) < 1.0


@pytest.mark.parametrize("seed", range(5))
def test_without_variants_the_model_is_version_2(seed):
    prior, coverage, failed, _ = _random_instance(seed, n=5)
    ours = interventional_posterior(prior, coverage, failed, [], None, GRID, WEIGHTS, LEAK, max_faults=5).marginals
    reference = exact_posterior(FaultModel(prior, coverage, failed, GRID, LEAK, WEIGHTS)).marginals
    assert ours == pytest.approx(reference, abs=1e-9)


@pytest.mark.parametrize("layer", ["exclusive", "composite"])
@pytest.mark.parametrize("seed", range(6))
def test_variant_layers_match_brute_force(seed, layer):
    prior, coverage, failed, observations = _random_instance(100 + seed)
    params = InterventionParams(**{**PARAMS.to_dict(), "layer": layer, "rho": (1.0,) if layer == "exclusive" else (0.3,)})
    ours = interventional_posterior(prior, coverage, failed, observations, params, GRID, WEIGHTS, LEAK, max_faults=3).marginals
    assert ours == pytest.approx(_brute_force(prior, coverage, failed, observations, params, layer, 3), abs=1e-8)


def test_summarise_is_consistent_with_separate_enumerations():
    prior, coverage, failed, observations = _random_instance(7, n=5)
    enumeration = enumerate_configurations(prior, coverage, failed, observations, PARAMS, GRID, WEIGHTS, LEAK, 3)
    for limit in (1, 2, 3):
        direct = interventional_posterior(prior, coverage, failed, observations, PARAMS, GRID, WEIGHTS, LEAK, limit)
        assert summarise(enumeration, max_faults=limit).marginals == pytest.approx(direct.marginals, abs=1e-10)
    full = summarise(enumeration)
    assert sum(full.size_distribution) == pytest.approx(1.0)
    assert summarise(enumeration, odds_scale=0.25).expected_faults < full.expected_faults
    with pytest.raises(ValueError):
        summarise(enumeration, max_faults=4)


def _two_fault_scene():
    # 6 statements, every test executes all of them; tests 0-3 fail, 4-5 pass.
    coverage = np.ones((6, 6), dtype=bool)
    failed = np.array([True, True, True, True, False, False])
    return np.full(6, 1 / 6), coverage, failed


def test_two_partial_repairs_are_read_as_two_faults():
    """Design scenario S2: each of two faults has a repair that fixes "its" failing tests only."""
    prior, coverage, failed = _two_fault_scene()
    observations = [_observation(1, coverage, failed, [0, 1]), _observation(4, coverage, failed, [2, 3])]
    observations += [_observation(s, coverage, failed, []) for s in (0, 2, 3, 5)]
    post = interventional_posterior(prior, coverage, failed, observations, PARAMS, GRID, WEIGHTS, LEAK)
    order = np.argsort(-post.marginals)
    assert set(order[:2]) == {1, 4}
    assert post.map_faults == (1, 4)
    assert post.expected_faults > 1.8
    # limited to one fault, the same evidence cannot be explained
    single = interventional_posterior(prior, coverage, failed, observations, PARAMS, GRID, WEIGHTS, LEAK, max_faults=1)
    assert single.marginals[[1, 4]].sum() <= 1.0 + 1e-9


def test_two_repairs_cannot_both_fix_the_same_test():
    """Exclusivity: full repairs at two statements are one fault with an alternative patch, not two faults."""
    prior, coverage, failed = _two_fault_scene()
    observations = [_observation(1, coverage, failed, [0, 1, 2, 3]), _observation(4, coverage, failed, [0, 1, 2, 3])]
    exclusive = interventional_posterior(prior, coverage, failed, observations, PARAMS, GRID, WEIGHTS, LEAK)
    assert exclusive.expected_faults < 1.2
    assert exclusive.marginals[1] == pytest.approx(exclusive.marginals[4])
    composite = InterventionParams(**{**PARAMS.to_dict(), "layer": "composite", "rho": (0.3,)})
    assert interventional_posterior(prior, coverage, failed, observations, composite, GRID, WEIGHTS,
                                    LEAK).expected_faults > exclusive.expected_faults


def test_failing_to_find_a_repair_costs_at_most_one_minus_alpha():
    prior, coverage, failed = _two_fault_scene()
    coverage = coverage.copy()
    coverage[:, 1:] = False  # only statement 0 is executed: it must be the fault
    coverage[:, 1] = ~failed  # statement 1 is executed by passing tests only
    many_duds = [_observation(0, coverage, failed, []) for _ in range(12)]
    post = interventional_posterior(prior, coverage, failed, many_duds, PARAMS, GRID, WEIGHTS, LEAK, max_faults=1)
    assert post.marginals[0] > 0.99  # nothing else can explain the failures, however many variants did nothing
    # and in a symmetric scene the weight of the statement drops by no more than the factor 1 - alpha
    prior2, coverage2, failed2 = _two_fault_scene()
    post2 = interventional_posterior(prior2, coverage2, failed2, [_observation(0, coverage2, failed2, []) for _ in range(12)],
                                     PARAMS, GRID, WEIGHTS, LEAK, max_faults=1)
    # with one fault allowed the marginals are proportional to the configuration weights
    assert post2.marginals[0] / post2.marginals[1] >= (1 - PARAMS.alpha) - 1e-9


def test_estimation_recovers_generating_parameters():
    world = World(InterventionParams(0.7, (1.0,), (0.95,), (0.03,), (0.6, 0.3, 0.1), (0.01, 0.02, 0.8), (0.1, 0.9, 0.8)),
                  GRID, WEIGHTS, 0.002)
    rng = np.random.default_rng(5)
    training = [simulate(rng, world, 1, "well_specified") for _ in range(400)]
    fitted, counts = estimate_intervention_params([(c.observations, c.faulty) for c in training], "test", n_nonrepair=3)
    assert fitted.alpha == pytest.approx(0.7, abs=0.08)
    assert fitted.gamma[0] == pytest.approx(0.95, abs=0.04)
    assert fitted.beta[0] == pytest.approx(0.03, abs=0.03)
    assert max(fitted.psi) == pytest.approx(0.8, abs=0.08)
    assert counts["faulty_statements_with_variants"] > 300


def test_posteriors_are_calibrated_when_the_model_is_right():
    """Simulate from the model and check that statements given probability p are faulty about p of the time."""
    world = World(PARAMS, GRID, WEIGHTS, LEAK)
    rng = np.random.default_rng(11)
    probabilities, labels = [], []
    for index in range(240):
        case = simulate(rng, world, 1 + index % 3, "well_specified")
        n = case.coverage.shape[1]
        # the simulator draws 1, 2 or 3 faults with equal probability; give inference that prior over the count
        enumeration = enumerate_configurations(np.full(n, 0.5), case.coverage, case.failed, case.observations, world.iv,
                                               GRID, WEIGHTS, LEAK, 3)
        keep = enumeration.sizes >= 1
        log_weight = enumeration.log_weight[keep] - np.log([len(list(combinations(range(n), int(r))))
                                                            for r in enumeration.sizes[keep]])
        weight = np.exp(log_weight - log_weight.max())
        weight /= weight.sum()
        probabilities.extend((weight[:, None] * enumeration.member[keep]).sum(axis=0))
        labels.extend(case.faulty)
    assert metrics.expected_calibration_error(np.array(probabilities), np.array(labels)) < 0.03


# --- FLITSR --------------------------------------------------------------------

def test_flitsr_puts_a_masked_second_fault_first_after_the_first():
    # statement 0 fails tests 0-2, statement 3 fails test 3 only; statement 1 is executed by everything
    coverage = np.array([[1, 1, 0, 0], [1, 1, 0, 0], [1, 1, 1, 0], [0, 1, 0, 1], [0, 1, 1, 0], [0, 1, 1, 1]], dtype=bool)
    failed = np.array([True, True, True, True, False, False])
    scores = flitsr(coverage, failed)
    order = np.argsort(-scores)
    assert set(order[:2]) == {0, 3}
    basis = np.flatnonzero(scores > 1.0)
    assert all(coverage[j, basis].any() for j in np.flatnonzero(failed))  # a span
    for element in basis:  # minimal: dropping any element uncovers a failing test
        rest = [b for b in basis if b != element]
        assert not all(coverage[j, rest].any() for j in np.flatnonzero(failed))


def test_flitsr_star_ranks_further_bases_and_keeps_the_single_fault_answer():
    coverage = np.array([[1, 1, 0], [1, 1, 0], [0, 1, 1], [0, 1, 1]], dtype=bool)
    failed = np.array([True, True, False, False])
    single = flitsr(coverage, failed)
    assert int(np.argmax(single)) == 0
    star = flitsr(coverage, failed, multi_round=True)
    assert int(np.argmax(star)) == 0
    assert (star > 1.0).sum() >= (single > 1.0).sum()
    assert flitsr(coverage, np.zeros(4, dtype=bool)).max() <= 1.0  # nothing fails: plain base scores


# --- metrics -------------------------------------------------------------------

def test_average_precision_and_auc():
    scores = np.array([0.9, 0.8, 0.7, 0.1])
    assert metrics.average_precision(scores, [0]) == pytest.approx(1.0)
    assert metrics.average_precision(scores, [2]) == pytest.approx(1 / 3)
    assert metrics.average_precision(scores, [0, 2]) == pytest.approx((1 / 1 + 2 / 3) / 2)
    tied = np.array([0.5, 0.5, 0.5, 0.5])
    assert metrics.average_precision(tied, [1]) == pytest.approx(1 / 2.5)
    assert metrics.roc_auc(np.array([3.0, 2.0, 1.0]), np.array([True, False, False])) == pytest.approx(1.0)
    assert metrics.roc_auc(np.array([1.0, 1.0]), np.array([True, False])) == pytest.approx(0.5)


# --- data ----------------------------------------------------------------------

def test_test_inputs_are_taken_from_literal_calls_only():
    source = ("def check(candidate):\n"
              "    assert candidate([1, 2], 0.5) == True\n"
              "    assert candidate([1, 2], 0.5) == True\n"
              "    assert candidate((1, 2)) == 3\n"
              "    assert candidate(helper(3)) == 1\n"
              "    assert abs(candidate('a', n=2) - 1) < 1e-6\n"
              "    assert candidate({'k': [None, 'x']}) is None\n")
    assert extract_test_inputs(source, ("candidate",)) == [([1, 2], 0.5), ({"k": [None, "x"]},)]


def test_injected_faults_are_on_fresh_distinct_lines():
    source = ("def f(a, b):\n    total = a + b\n    if total > 10:\n        total = total - 1\n"
              "    result = total * 2\n    return result\n")
    program = Program.from_source(source, "f")
    items = v4.injected_items(program, "f", base_truth=(2,), n_new=2, limit=6, rng=np.random.default_rng(1), prefix="T")
    assert items
    for _, mutated, truth in items:
        changed = [i for i, (a, b) in enumerate(zip(program.source.splitlines(), mutated.splitlines()), 1) if a != b]
        assert len(changed) == 2 and 2 not in changed
        assert truth.fault_lines == tuple(sorted({2, *changed}))


def test_scoring_receives_no_ground_truth():
    parameters = set(inspect.signature(v4.score).parameters)
    assert parameters == {"case", "observed", "fitted", "ablations"}
    source = inspect.getsource(v4.score)
    assert ".truth" not in source and "fault_lines" not in source and "faulty_mask" not in source


def test_expected_average_precision_never_exceeds_one():
    from pcg.v4_sensitivity import expected_average_precision
    rng = np.random.default_rng(0)
    tied = np.array([0.5, 0.5, 0.1, 0.1])
    assert metrics.average_precision(tied, [0, 1]) == pytest.approx(2 / 1.5)  # the pre-registered formula overshoots
    assert expected_average_precision(tied, [0, 1], rng, draws=50) == pytest.approx(1.0)
    all_tied = np.zeros(4)
    assert expected_average_precision(all_tied, [0, 1], rng, draws=4000) == pytest.approx(expected_value_two_of_four(), abs=0.01)
    assert expected_average_precision(np.array([3.0, 2.0, 1.0]), [0], rng) == pytest.approx(1.0)


def expected_value_two_of_four():
    """Exact expected AP of two faults at uniformly random positions among four."""
    from itertools import combinations
    values = [np.mean([(i + 1) / p for i, p in enumerate(pair)]) for pair in combinations([1, 2, 3, 4], 2)]
    return float(np.mean(values))


def test_hierarchical_prior_matches_numerical_integration_and_the_independent_limit():
    from pcg.interventional import cardinality_log_prior
    n, mean, kappa = 6, 1 / 6, 6.0
    a, b = mean * kappa, (1 - mean) * kappa
    grid = np.linspace(0, 1, 400001)[1:-1]
    density = grid ** (a - 1) * (1 - grid) ** (b - 1)
    density /= np.trapezoid(density, grid)
    sizes = np.array([1, 2, 3])
    numeric = np.array([np.trapezoid(grid ** r * (1 - grid) ** (n - r) * density, grid) for r in sizes])
    ours = np.exp(cardinality_log_prior(sizes, n, mean, kappa))
    from math import lgamma
    const = lgamma(a + b) - lgamma(a) - lgamma(b) - lgamma(a + b + n)  # the part that does not depend on r
    assert ours * np.exp(const) == pytest.approx(numeric, rel=2e-3)
    # large concentration: independent faults with probability `mean`
    big = cardinality_log_prior(sizes, n, mean, 1e9)
    assert np.diff(big) == pytest.approx(np.log(mean / (1 - mean)) * np.ones(2), abs=1e-5)


def test_hierarchical_prior_changes_only_the_prior_over_the_fault_count():
    prior, coverage, failed, observations = _random_instance(3, n=5)
    prior = np.full(5, 0.2)
    enumeration = enumerate_configurations(prior, coverage, failed, observations, PARAMS, GRID, WEIGHTS, LEAK, 3)
    plain = summarise(enumeration)
    near_independent = summarise(enumeration, kappa=1e9)
    assert near_independent.marginals == pytest.approx(plain.marginals, abs=1e-6)
    heavy_tail = summarise(enumeration, kappa=1.0)
    assert heavy_tail.expected_faults != pytest.approx(plain.expected_faults, abs=1e-3)
    with pytest.raises(ValueError):
        non_uniform = Enumeration(enumeration.configs, enumeration.member, enumeration.sizes, enumeration.log_weight,
                                  np.array([0.1, 0.2, 0.2, 0.2, 0.2]), enumeration.active, enumeration.max_faults)
        summarise(non_uniform, kappa=2.0)


def test_mbpp_helpers_are_deterministic_and_keep_the_kind_of_value():
    from pcg.mbpp import amplify, perturb, tested_function
    code = "def helper(x):\n    return x\n\ndef f(a, b):\n    return helper(a) + b\n"
    tests = ["assert f(1, 2) == 3", "assert f(2, 2) == 4", "assert helper(1) == 1"]
    assert tested_function(code, tests) == "f"
    assert tested_function(code, ["assert g(1) == 1"]) is None
    inputs = [(1, 2), (2, 2), ([1, 2, 3], "ab")]
    first = amplify(inputs, np.random.default_rng(5))
    assert first == amplify(inputs, np.random.default_rng(5))
    assert 0 < len(first) <= 12 and len(set(map(repr, first))) == len(first) and not {repr(x) for x in first} & {repr(x) for x in inputs}
    rng = np.random.default_rng(1)
    assert perturb(True, rng) is False and isinstance(perturb(3, rng), int) and isinstance(perturb(2.0, rng), float)
    assert isinstance(perturb("abc", rng), str) and isinstance(perturb([1, 2], rng), list) and perturb(None, rng) is None
