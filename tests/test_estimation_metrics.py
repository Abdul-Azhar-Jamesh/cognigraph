"""Parameter estimation, baselines and metrics, checked against known answers."""

import numpy as np
import pytest

from pcg import baselines, metrics
from pcg.estimation import LabelledCase, bin_index, estimate_binned_likelihood, estimate_params, fit_exposure_prior


def synthetic_cases(rng, n_cases, theta_values, theta_probs, leak, n_statements=6, n_tests=12):
    """Sample single-fault cases from the model itself."""
    cases = []
    for _ in range(n_cases):
        faulty = np.zeros(n_statements, dtype=bool)
        faulty[rng.integers(n_statements)] = True
        scopes = rng.random((n_tests, n_statements)) < 0.6
        theta = rng.choice(theta_values, p=theta_probs)
        k = scopes[:, faulty].sum(axis=1)
        p_fail = 1.0 - (1.0 - leak) * (1.0 - theta) ** k
        cases.append(LabelledCase(scopes, rng.random(n_tests) < p_fail, faulty, rng.random(n_statements) < np.where(faulty, 0.5, 0.05)))
    return cases


def test_estimator_recovers_parameters_of_data_sampled_from_the_model():
    rng = np.random.default_rng(1)
    params, counts = estimate_params(synthetic_cases(rng, 3000, [0.7], [1.0], leak=0.05), "synthetic")
    assert params.theta == pytest.approx(0.7, abs=0.02)
    assert params.leak == pytest.approx(0.05, abs=0.01)
    assert params.prior_fault == pytest.approx(1 / 6, abs=0.005)
    assert params.static_tpr == pytest.approx(0.5, abs=0.03)
    assert params.static_fpr == pytest.approx(0.05, abs=0.01)
    assert counts["training_cases"] == 3000
    assert sum(params.theta_weights) == pytest.approx(1.0)


def test_em_recovers_a_two_component_exposure_mixture():
    rng = np.random.default_rng(2)
    true_theta = rng.choice([0.15, 0.85], size=4000, p=[0.3, 0.7])
    trials = np.full(4000, 40)
    fails = rng.binomial(trials, true_theta)
    grid, weights = fit_exposure_prior(trials, fails, leak=0.0)
    assert weights.sum() == pytest.approx(1.0)
    low, high = weights[grid < 0.5].sum(), weights[grid > 0.5].sum()
    assert low == pytest.approx(0.3, abs=0.03) and high == pytest.approx(0.7, abs=0.03)
    assert weights[np.argmin(np.abs(grid - 0.15))] > 0.2 and weights[np.argmin(np.abs(grid - 0.85))] > 0.5


def test_em_ignores_faults_without_data_and_never_returns_zero_weights():
    grid, weights = fit_exposure_prior([0, 0, 5], [0, 0, 5], leak=0.01)
    assert np.all(weights > 0) and weights.sum() == pytest.approx(1.0)
    assert weights[-1] == weights.max()  # the only informative fault always failed
    _, uniform = fit_exposure_prior([0], [0], leak=0.01)
    assert np.allclose(uniform, 0.1)


def test_estimator_rejects_what_it_was_not_derived_for():
    two_faults = LabelledCase(np.ones((2, 3), dtype=bool), np.array([True, False]), np.array([True, True, False]))
    with pytest.raises(ValueError):
        estimate_params([two_faults], "x")
    with pytest.raises(ValueError):
        estimate_params([], "x")


def test_binned_likelihoods_are_distributions_and_reflect_the_data():
    values = np.array([0.05, 0.1, 0.15, 0.9, 0.95, 0.85, 0.92, 0.88])
    labels = np.array([1, 1, 1, 0, 0, 0, 0, 0], dtype=bool)
    p_fault, p_clean = estimate_binned_likelihood(values, labels, bins=5)
    assert p_fault.sum() == pytest.approx(1.0) and p_clean.sum() == pytest.approx(1.0)
    assert p_fault[0] > p_clean[0] and p_fault[4] < p_clean[4]
    assert bin_index(np.array([0.0, 0.199, 0.2, 1.0]), 5).tolist() == [0, 0, 1, 4]


COVERAGE = np.array([[1, 1, 0], [1, 0, 1], [1, 1, 1], [0, 1, 0]], dtype=bool)
FAILED = np.array([True, True, False, False])


def test_spectrum_baselines_match_hand_computation():
    # statement 0: ef=2, ep=1; statement 1: ef=1, ep=2; statement 2: ef=1, ep=1; F=2, P=2
    assert baselines.execution_only(COVERAGE, FAILED).tolist() == [2, 1, 1]
    assert baselines.simple_heuristic(COVERAGE, FAILED).tolist() == [1, -1, 0]
    assert np.allclose(baselines.ochiai(COVERAGE, FAILED), [2 / np.sqrt(2 * 3), 1 / np.sqrt(2 * 3), 1 / np.sqrt(2 * 2)])
    assert np.allclose(baselines.tarantula(COVERAGE, FAILED), [1 / 1.5, 0.5 / 1.5, 0.5 / 1.0])
    assert baselines.chance(COVERAGE, FAILED).tolist() == [0, 0, 0]


def test_baselines_are_defined_when_nothing_fails_or_nothing_is_covered():
    nothing_failed = np.zeros(4, dtype=bool)
    for name, fn in baselines.BASELINES.items():
        assert np.all(np.isfinite(fn(COVERAGE, nothing_failed))), name
        assert np.all(np.isfinite(fn(np.zeros((4, 3), dtype=bool), FAILED))), name


def test_rank_metrics_with_and_without_ties():
    alone = metrics.rank_metrics(np.array([0.9, 0.5, 0.1]), 0)
    assert (alone.top1, alone.top3, alone.reciprocal_rank, alone.expected_rank, alone.tie_size) == (1.0, 1.0, 1.0, 1.0, 1)
    # Fault tied with two others for ranks 1..3: a random tie-break puts it first one time in three.
    tied = metrics.rank_metrics(np.array([0.7, 0.7, 0.7, 0.1]), 1)
    assert tied.top1 == pytest.approx(1 / 3) and tied.top3 == 1.0
    assert tied.reciprocal_rank == pytest.approx((1 + 1 / 2 + 1 / 3) / 3)
    assert tied.expected_rank == 2.0 and tied.exam == 0.5 and tied.tie_size == 3
    # Tie straddling the top-3 boundary: positions 3..4.
    straddle = metrics.rank_metrics(np.array([0.9, 0.8, 0.5, 0.5]), 3)
    assert straddle.top1 == 0.0 and straddle.top3 == 0.5
    # Floating-point noise below the rounding precision must not break a tie.
    noisy = metrics.rank_metrics(np.array([0.5, 0.5 + 1e-13]), 0)
    assert noisy.tie_size == 2


def test_chance_baseline_scores_equal_their_analytic_values():
    m = metrics.rank_metrics(np.zeros(8), 3)
    assert m.top1 == pytest.approx(1 / 8) and m.top3 == pytest.approx(3 / 8) and m.exam == pytest.approx(4.5 / 8)


def test_multi_fault_metrics():
    m = metrics.multi_fault_metrics(np.array([0.9, 0.1, 0.8, 0.2, 0.3]), [2, 1])
    assert m["first_top1"] == 0.0 and m["first_top3"] == 1.0 and m["first_reciprocal_rank"] == 0.5
    assert m["all_top3"] == 0.0 and m["all_top5"] == 1.0 and m["mean_rank"] == 3.5


def test_probabilistic_scores_on_known_values():
    p, y = np.array([0.9, 0.1, 0.8, 0.3]), np.array([1, 0, 1, 0])
    assert metrics.brier_score(p, y) == pytest.approx((0.01 + 0.01 + 0.04 + 0.09) / 4)
    assert metrics.log_loss(p, y) == pytest.approx(-(np.log(0.9) + np.log(0.9) + np.log(0.8) + np.log(0.7)) / 4)
    assert np.isfinite(metrics.log_loss(np.array([0.0, 1.0]), np.array([1, 0])))  # clipped, not infinite


def test_ece_is_zero_for_a_perfectly_calibrated_predictor_and_large_for_a_bad_one():
    rng = np.random.default_rng(0)
    p = rng.choice([0.05, 0.25, 0.55, 0.85], size=200_000)
    y = rng.random(p.size) < p
    assert metrics.expected_calibration_error(p, y) < 0.01
    assert metrics.expected_calibration_error(np.full(1000, 0.95), np.zeros(1000)) == pytest.approx(0.95)
    table = metrics.reliability_table(np.array([0.0, 0.05, 1.0]), np.array([0, 0, 1]))
    assert table[0]["count"] == 2 and table[-1]["count"] == 1 and sum(r["count"] for r in table) == 3


def test_cluster_bootstrap_is_deterministic_and_respects_clusters():
    values = np.array([1.0, 1.0, 1.0, 0.0, 0.0, 0.0])
    clusters = ["a", "a", "a", "b", "b", "b"]
    first = metrics.cluster_bootstrap_ci(values, clusters, resamples=2000, seed=5)
    assert first == metrics.cluster_bootstrap_ci(values, clusters, resamples=2000, seed=5)
    # With two clusters that are internally constant the mean can only be 0, 0.5 or 1.
    assert first == (0.0, 1.0)
    # Treating the six values as independent would give a much narrower interval.
    independent = metrics.cluster_bootstrap_ci(values, list("abcdef"), resamples=2000, seed=5)
    assert independent[0] > 0.0 and independent[1] < 1.0


def test_sign_flip_test_behaves_at_the_extremes():
    assert metrics.paired_sign_flip_test(np.zeros(10)) == 1.0
    strong = metrics.paired_sign_flip_test(np.full(20, 0.3), resamples=20000, seed=1)
    assert strong < 0.001
    symmetric = metrics.paired_sign_flip_test(np.array([0.2, -0.2, 0.1, -0.1, 0.3, -0.3]), resamples=5000, seed=1)
    assert symmetric == 1.0
