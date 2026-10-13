"""Mathematical tests of the model and its inference (not just "does it run")."""

import itertools

import numpy as np
import pytest

from pcg.model import (
    FaultModel,
    ImpossibleEvidenceError,
    apply_likelihood_ratio,
    exact_posterior,
    gibbs_posterior,
    infer,
)


def brute_force(prior, scopes, failed, thetas, weights, leak):
    """Independent, deliberately naive implementation of the joint distribution."""
    n = len(prior)
    evidence, marginals, no_fault = 0.0, np.zeros(n), 0.0
    for theta, weight in zip(thetas, weights):
        for config in itertools.product([0, 1], repeat=n):
            p = weight
            for i in range(n):
                p *= prior[i] if config[i] else 1.0 - prior[i]
            for j in range(len(failed)):
                k = sum(config[i] for i in range(n) if scopes[j][i])
                p_pass = (1.0 - leak) * (1.0 - theta) ** k
                p *= (1.0 - p_pass) if failed[j] else p_pass
            evidence += p
            marginals += p * np.array(config)
            if not any(config):
                no_fault += p
    return marginals / evidence, no_fault / evidence, evidence


def random_model(rng, grid=False):
    n, m = int(rng.integers(1, 7)), int(rng.integers(0, 6))
    thetas = rng.uniform(0.05, 0.99, size=3) if grid else np.array([rng.uniform(0.05, 0.99)])
    weights = rng.dirichlet(np.ones(thetas.size))
    return dict(prior=rng.uniform(0.02, 0.6, n), scopes=rng.random((m, n)) < 0.5, failed=rng.random(m) < 0.4,
                thetas=thetas, weights=weights, leak=float(rng.uniform(0.001, 0.2)))


@pytest.mark.parametrize("grid", [False, True])
def test_exact_inference_matches_brute_force_enumeration(grid):
    rng = np.random.default_rng(7)
    for _ in range(40):
        m = random_model(rng, grid)
        post = exact_posterior(FaultModel(m["prior"], m["scopes"], m["failed"], m["thetas"], m["leak"], m["weights"]))
        marginals, no_fault, evidence = brute_force(m["prior"], m["scopes"], m["failed"], m["thetas"], m["weights"], m["leak"])
        assert np.allclose(post.marginals, marginals, atol=1e-12)
        assert post.p_no_fault == pytest.approx(no_fault, abs=1e-12)
        assert np.exp(post.log_evidence) == pytest.approx(evidence, rel=1e-10)
        assert post.theta_posterior.sum() == pytest.approx(1.0)
        assert np.all((post.marginals >= 0.0) & (post.marginals <= 1.0))


def test_joint_distribution_is_normalised():
    """Summing P(F, T) over every fault configuration and every outcome vector gives 1."""
    prior, scopes = np.array([0.2, 0.4, 0.1]), np.array([[1, 1, 0], [0, 1, 1]], dtype=bool)
    total = 0.0
    for outcome in itertools.product([False, True], repeat=2):
        total += np.exp(exact_posterior(FaultModel(prior, scopes, np.array(outcome), [0.3, 0.9], 0.05, [0.4, 0.6])).log_evidence)
    assert total == pytest.approx(1.0, abs=1e-12)


def test_closed_form_one_failing_test_two_statements():
    """Hand derivation (MATHEMATICAL_MODEL.md, worked example)."""
    pi, theta, leak = 0.1, 0.8, 0.02
    post = exact_posterior(FaultModel([pi, pi], [[True, True]], [True], theta, leak))
    p_fail = 1 - (1 - leak) * (1 - pi * theta) ** 2
    p_fail_and_f1 = pi * (1 - (1 - leak) * (1 - theta) * (1 - pi * theta))
    assert post.marginals[0] == pytest.approx(p_fail_and_f1 / p_fail, abs=1e-12)
    assert post.marginals[1] == pytest.approx(post.marginals[0], abs=1e-12)  # symmetric statements
    assert np.exp(post.log_evidence) == pytest.approx(p_fail, abs=1e-12)
    assert post.p_no_fault == pytest.approx((1 - pi) ** 2 * leak / p_fail, abs=1e-12)


def test_closed_form_passing_tests_single_statement():
    """One statement, k passing tests: posterior odds = prior odds * (1 - theta)^k."""
    pi, theta, leak, k = 0.3, 0.6, 0.01, 4
    post = exact_posterior(FaultModel([pi], np.ones((k, 1), dtype=bool), np.zeros(k, dtype=bool), theta, leak))
    odds = pi / (1 - pi) * (1 - theta) ** k
    assert post.marginals[0] == pytest.approx(odds / (1 + odds), abs=1e-12)


def test_no_evidence_returns_the_prior():
    prior = np.array([0.1, 0.5, 0.9])
    post = exact_posterior(FaultModel(prior, np.zeros((0, 3), dtype=bool), np.zeros(0, dtype=bool), 0.7, 0.01))
    assert np.allclose(post.marginals, prior)
    assert post.p_no_fault == pytest.approx(np.prod(1 - prior))
    assert post.log_evidence == pytest.approx(0.0)


def test_unexecuted_statement_keeps_its_prior_exactly():
    post = exact_posterior(FaultModel([0.1, 0.1, 0.25], [[True, True, False], [True, False, False]], [True, False], 0.8, 0.01))
    assert post.marginals[2] == 0.25


def test_no_failure_suite_lowers_but_never_zeroes_fault_probability():
    post = exact_posterior(FaultModel(np.full(3, 0.2), np.ones((5, 3), dtype=bool), np.zeros(5, dtype=bool), 0.7, 0.01))
    assert np.all(post.marginals < 0.2) and np.all(post.marginals > 0.0)
    assert post.p_no_fault > (1 - 0.2) ** 3  # more confident than the prior, yet below 1
    assert post.p_no_fault < 1.0


def test_all_failing_suite_raises_fault_probability_of_executed_statements():
    post = exact_posterior(FaultModel(np.full(3, 0.2), [[True, True, False]] * 4, np.ones(4, dtype=bool), 0.7, 0.01))
    assert post.marginals[0] > 0.2 and post.marginals[1] > 0.2
    assert post.marginals[2] == 0.2
    assert post.p_no_fault < 1e-4


def test_statement_covered_by_passing_and_failing_tests_is_less_suspicious():
    """s0 runs only in the failing test; s1 runs in the failing test and in two passing ones."""
    post = exact_posterior(FaultModel([0.1, 0.1], [[True, True], [False, True], [False, True]], [True, False, False], 0.7, 0.01))
    assert post.marginals[0] > post.marginals[1] > 0.0


def test_explaining_away_between_statements_sharing_a_failing_test():
    """The posterior does not factorise: evidence about s0 changes the belief about s1."""
    shared = exact_posterior(FaultModel([0.1, 0.1], [[True, True]], [True], 0.8, 0.01))
    more = exact_posterior(FaultModel([0.1, 0.1], [[True, True], [True, False]], [True, True], 0.8, 0.01))
    assert more.marginals[0] > shared.marginals[0]
    assert more.marginals[1] < shared.marginals[1]  # s0 now explains the shared failure


def test_two_failures_with_disjoint_scopes_need_two_faults():
    post = exact_posterior(FaultModel(np.full(4, 0.1), [[True, True, False, False], [False, False, True, True]], [True, True], 0.9, 0.001))
    assert post.expected_faults > 1.9
    assert np.allclose(post.marginals, post.marginals[0])


def test_contradictory_evidence_is_reported_not_hidden():
    with pytest.raises(ImpossibleEvidenceError):  # a failure nothing can explain
        exact_posterior(FaultModel([0.1], [[False]], [True], 0.8, 0.0))
    with pytest.raises(ImpossibleEvidenceError):  # a certain fault that certainly fails, yet the test passed
        exact_posterior(FaultModel([1.0], [[True]], [False], 1.0, 0.0))
    with pytest.raises(ImpossibleEvidenceError):
        gibbs_posterior(FaultModel([0.1], [[False]], [True], 0.8, 0.0), n_samples=10, burn_in=5)


def test_a_positive_leak_makes_an_unexplained_failure_possible():
    post = exact_posterior(FaultModel([0.1], [[False]], [True], 0.8, 0.01))
    assert post.marginals[0] == 0.1 and np.exp(post.log_evidence) == pytest.approx(0.01)


@pytest.mark.parametrize("kwargs", [
    dict(prior=[1.2], scopes=[[True]], failed=[True], theta=0.5, leak=0.1),
    dict(prior=[0.2], scopes=[[True, False]], failed=[True], theta=0.5, leak=0.1),
    dict(prior=[0.2], scopes=[[True]], failed=[True, False], theta=0.5, leak=0.1),
    dict(prior=[0.2], scopes=[[True]], failed=[True], theta=1.5, leak=0.1),
    dict(prior=[0.2], scopes=[[True]], failed=[True], theta=0.5, leak=1.0),
    dict(prior=[0.2], scopes=[[True]], failed=[True], theta=[0.2, 0.8], leak=0.1, theta_weights=[0.9, 0.9]),
    dict(prior=[float("nan")], scopes=[[True]], failed=[True], theta=0.5, leak=0.1),
])
def test_malformed_models_are_rejected(kwargs):
    with pytest.raises(ValueError):
        FaultModel(**kwargs)


def test_empty_program_and_empty_suite():
    post = infer(FaultModel(np.zeros(0), np.zeros((0, 0), dtype=bool), np.zeros(0, dtype=bool), 0.5, 0.1))
    assert post.marginals.size == 0 and post.p_no_fault == pytest.approx(1.0)


def test_likelihood_ratio_update_is_bayes_rule():
    prior, tpr, fpr = 0.2, 0.7, 0.1
    by_hand = prior * tpr / (prior * tpr + (1 - prior) * fpr)
    assert apply_likelihood_ratio(np.array([prior]), np.array([tpr / fpr]))[0] == pytest.approx(by_hand)
    assert apply_likelihood_ratio(np.array([prior]), np.array([1.0]))[0] == pytest.approx(prior)
    with pytest.raises(ValueError):
        apply_likelihood_ratio(np.array([prior]), np.array([-1.0]))


def test_posterior_is_monotone_in_the_prior():
    values = [exact_posterior(FaultModel([p, 0.1], [[True, True]], [True], 0.8, 0.01)).marginals[0]
              for p in (0.01, 0.05, 0.2, 0.5, 0.9)]
    assert values == sorted(values)


def test_mixture_over_theta_is_the_evidence_weighted_average():
    """Summing out Theta = averaging fixed-theta posteriors with weights P(theta | T)."""
    prior, scopes, failed = np.array([0.1, 0.2, 0.15]), np.array([[1, 1, 0], [0, 1, 1], [1, 0, 1]], dtype=bool), np.array([True, False, False])
    grid, weights = np.array([0.2, 0.9]), np.array([0.3, 0.7])
    mixed = exact_posterior(FaultModel(prior, scopes, failed, grid, 0.01, weights))
    parts = [exact_posterior(FaultModel(prior, scopes, failed, t, 0.01)) for t in grid]
    w = weights * np.exp([p.log_evidence for p in parts])
    w /= w.sum()
    assert np.allclose(mixed.theta_posterior, w)
    assert np.allclose(mixed.marginals, w[0] * parts[0].marginals + w[1] * parts[1].marginals)


def test_gibbs_agrees_with_exact_inference_and_is_reproducible():
    rng = np.random.default_rng(3)
    model = FaultModel(np.full(5, 0.15), rng.random((6, 5)) < 0.6, np.array([True, False, True, False, False, False]),
                       [0.3, 0.8], 0.05, [0.5, 0.5])
    exact = exact_posterior(model)
    a = gibbs_posterior(model, n_samples=1500, burn_in=300, n_chains=4, seed=11)
    b = gibbs_posterior(model, n_samples=1500, burn_in=300, n_chains=4, seed=11)
    assert np.array_equal(a.marginals, b.marginals)  # same seed, same numbers
    assert np.max(np.abs(a.marginals - exact.marginals)) < 0.04  # Monte Carlo error
    assert np.max(np.abs(a.theta_posterior - exact.theta_posterior)) < 0.05
    assert a.rhat < 1.1


def test_exact_inference_matches_pgmpy_variable_elimination():
    """Cross-check against an independent library implementation of Bayesian networks."""
    pytest.importorskip("pgmpy")
    from pgmpy.factors.discrete import TabularCPD
    from pgmpy.inference import VariableElimination
    from pgmpy.models import DiscreteBayesianNetwork

    prior = [0.1, 0.3, 0.2, 0.15]
    scopes = np.array([[1, 1, 0, 0], [0, 1, 1, 0], [1, 0, 1, 1]], dtype=bool)
    failed, theta, leak = [True, False, True], 0.7, 0.03
    edges = [(f"F{i}", f"T{j}") for j in range(3) for i in range(4) if scopes[j, i]]
    network = DiscreteBayesianNetwork(edges)
    for i, p in enumerate(prior):
        network.add_cpds(TabularCPD(f"F{i}", 2, [[1 - p], [p]]))
    for j in range(3):
        parents = [f"F{i}" for i in range(4) if scopes[j, i]]
        columns = list(itertools.product([0, 1], repeat=len(parents)))
        p_pass = [(1 - leak) * (1 - theta) ** sum(c) for c in columns]
        network.add_cpds(TabularCPD(f"T{j}", 2, [p_pass, [1 - v for v in p_pass]], evidence=parents,
                                    evidence_card=[2] * len(parents)))
    assert network.check_model()
    engine = VariableElimination(network)
    evidence = {f"T{j}": int(failed[j]) for j in range(3)}
    ours = exact_posterior(FaultModel(prior, scopes, failed, theta, leak))
    for i in range(4):
        theirs = engine.query([f"F{i}"], evidence=evidence, show_progress=False).values[1]
        assert ours.marginals[i] == pytest.approx(theirs, abs=1e-9)
