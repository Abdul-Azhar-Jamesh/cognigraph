"""Discriminative baselines: logistic regression on per-statement features.

This is the learned, black-box way of combining evidence that the literature
uses (pointwise learning to rank). It receives the same information as the
Bayesian model and is trained on the same programs, so it is the fair
competitor both for ranking and, because it minimises log loss, for the
quality of probabilities.

Also here: Platt scaling of posterior log-odds (recalibration), which is a
one-feature logistic regression.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import numpy as np

from . import baselines, config
from .mbfl import CONTEXT_ALL, MutationEvidence

SPECTRUM_FEATURES = ("ef_fraction", "ep_fraction", "ochiai", "tarantula", "context_all")
FUSION_FEATURES = SPECTRUM_FEATURES + (
    "metallaxis", "muse", "level_0", "level_1", "level_2", "level_3", "level_4", "static_flag")


def statement_features(coverage: np.ndarray, failed: np.ndarray,
                       evidence: Optional[MutationEvidence] = None,
                       static_flags: Optional[np.ndarray] = None) -> np.ndarray:
    """Feature matrix (statements x features). Spectrum features only if no evidence is given."""
    ef, ep, total_failed, total_passed = baselines.spectrum_counts(coverage, failed)
    columns = [
        ef / max(total_failed, 1),
        ep / max(total_passed, 1),
        baselines.ochiai(coverage, failed),
        baselines.tarantula(coverage, failed),
        (ef == total_failed).astype(float) if total_failed else np.zeros_like(ef),
    ]
    if evidence is not None:
        levels = np.asarray(evidence.levels, dtype=int)
        columns += [evidence.metallaxis, evidence.muse]
        columns += [(levels == v).astype(float) for v in range(config.MUTATION_LEVELS)]
        columns.append(np.zeros_like(ef) if static_flags is None else np.asarray(static_flags, dtype=float))
        assert np.array_equal(np.asarray(evidence.contexts) == CONTEXT_ALL, columns[4].astype(bool))
    return np.column_stack(columns)


def _sigmoid(z: np.ndarray) -> np.ndarray:
    return 1.0 / (1.0 + np.exp(-np.clip(z, -700.0, 700.0)))


@dataclass(frozen=True)
class LogisticModel:
    """A fitted logistic regression with its feature standardisation."""

    weights: np.ndarray   # for standardised features
    intercept: float
    mean: np.ndarray
    scale: np.ndarray
    converged: bool

    def predict(self, features: np.ndarray) -> np.ndarray:
        z = ((np.asarray(features, dtype=float) - self.mean) / self.scale) @ self.weights + self.intercept
        return _sigmoid(z)


def fit_logistic(features: np.ndarray, labels: np.ndarray, l2: float = config.LOGISTIC_L2,
                 standardise: bool = True, max_iterations: int = 100) -> LogisticModel:
    """L2-penalised logistic regression by damped Newton iterations.

    Minimises ``sum_i logloss_i + (l2 / 2) * ||w||^2``; the intercept is not
    penalised. The objective is strictly convex for ``l2 > 0``, so the solution
    is unique and the procedure is deterministic.
    """
    x = np.asarray(features, dtype=float)
    y = np.asarray(labels, dtype=float)
    if x.ndim != 2 or x.shape[0] != y.shape[0] or x.shape[0] == 0:
        raise ValueError("features must be (samples, features) with one label per sample")
    mean = x.mean(axis=0) if standardise else np.zeros(x.shape[1])
    scale = x.std(axis=0) if standardise else np.ones(x.shape[1])
    scale = np.where(scale > 1e-12, scale, 1.0)
    design = np.column_stack([(x - mean) / scale, np.ones(x.shape[0])])
    penalty = np.full(design.shape[1], l2)
    penalty[-1] = 0.0

    def objective(beta: np.ndarray) -> float:
        z = design @ beta
        return float(np.sum(np.logaddexp(0.0, z) - y * z) + 0.5 * np.sum(penalty * beta ** 2))

    beta = np.zeros(design.shape[1])
    value = objective(beta)
    converged = False
    for _ in range(max_iterations):
        p = _sigmoid(design @ beta)
        gradient = design.T @ (p - y) + penalty * beta
        hessian = (design * (p * (1.0 - p))[:, None]).T @ design + np.diag(penalty) + 1e-10 * np.eye(design.shape[1])
        step = np.linalg.solve(hessian, gradient)
        scale_step = 1.0
        while scale_step > 1e-8:  # halve the step until the objective does not increase
            candidate = beta - scale_step * step
            candidate_value = objective(candidate)
            if candidate_value <= value + 1e-12:
                break
            scale_step /= 2.0
        else:  # no step length lowers the objective: we are at the minimum
            converged = True
            break
        improvement = value - candidate_value
        beta, value = candidate, candidate_value
        if np.max(np.abs(gradient)) < 1e-8 or improvement < 1e-12:
            converged = True
            break
    return LogisticModel(beta[:-1], float(beta[-1]), mean, scale, converged)


def _logit(p: np.ndarray, eps: float = 1e-9) -> np.ndarray:
    p = np.clip(np.asarray(p, dtype=float), eps, 1.0 - eps)
    return np.log(p / (1.0 - p))


@dataclass(frozen=True)
class Recalibration:
    """``p' = sigmoid(a * logit(p) + b)`` with ``a > 0``."""

    a: float
    b: float

    def apply(self, probabilities: np.ndarray) -> np.ndarray:
        return _sigmoid(self.a * _logit(probabilities) + self.b)


def fit_recalibration(probabilities: np.ndarray, labels: np.ndarray) -> Recalibration:
    """Platt scaling on the log-odds, fitted by maximum likelihood.

    If the fitted slope is not positive the identity map is returned: a
    non-increasing map would reverse rankings and is never acceptable.
    """
    model = fit_logistic(_logit(probabilities)[:, None], labels, l2=1e-6, standardise=False)
    a = float(model.weights[0])
    if not np.isfinite(a) or a <= 0:
        return Recalibration(1.0, 0.0)
    return Recalibration(a, model.intercept)
