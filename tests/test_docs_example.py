"""The worked example of docs/MATHEMATICAL_MODEL.md, section 8, recomputed by the code."""

import numpy as np
import pytest

from pcg.model import FaultModel, apply_likelihood_ratio, exact_posterior

SCOPES = np.array([[1, 1, 0], [0, 1, 1], [0, 0, 1]], dtype=bool)
FAILED = np.array([True, False, False])


def test_worked_example_fixed_theta():
    post = exact_posterior(FaultModel([0.1, 0.1, 0.1], SCOPES, FAILED, 0.8, 0.01))
    assert np.round(post.marginals, 4).tolist() == [0.7668, 0.1693, 0.0044]
    assert round(post.p_no_fault, 4) == 0.0834
    assert np.exp(post.log_evidence) == pytest.approx(0.0856212, abs=5e-8)


def test_worked_example_static_evidence_prior():
    assert apply_likelihood_ratio(np.array([0.1]), np.array([0.2 / 0.05]))[0] == pytest.approx(0.3077, abs=5e-5)


def test_worked_example_uncertain_exposure_rate():
    post = exact_posterior(FaultModel([0.1, 0.1, 0.1], SCOPES, FAILED, [0.2, 0.8], 0.01, [0.5, 0.5]))
    assert np.round(post.marginals, 4).tolist() == [0.6734, 0.2456, 0.0249]
    assert round(float(post.theta_posterior[1]), 4) == 0.6695
