"""Parameter estimation from labelled faulty programs.

The parameters are *estimated*, never chosen by hand. Training data are
single-fault mutants whose fault location is known because we injected it.
In every experiment the programs used for estimation are disjoint from the
program being analysed (leave-one-program-out), so no label of the evaluated
program can reach its own inference.

All estimates are posterior means under a uniform Beta(1, 1) prior ("add-one"
smoothing): ``(successes + 1) / (trials + 2)``. This keeps every estimate
strictly inside (0, 1) even when an event was never observed.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Sequence

import numpy as np

from . import config
from .config import ModelParams


@dataclass(frozen=True)
class LabelledCase:
    """One training example: evidence plus the known fault location.

    Attributes:
        scopes: boolean (m, n), test scopes exactly as inference will use them.
        failed: boolean (m,), test outcomes.
        faulty: boolean (n,), ground truth; exactly one True entry.
        static_flags: boolean (n,), analyser flags, or None when not collected.
    """

    scopes: np.ndarray
    failed: np.ndarray
    faulty: np.ndarray
    static_flags: Optional[np.ndarray] = None


def _beta_mean(successes: int, trials: int) -> float:
    return (successes + 1.0) / (trials + 2.0)


def estimate_params(cases: Sequence[LabelledCase], provenance: str) -> tuple[ModelParams, dict]:
    """Estimate ``ModelParams`` and return them with the raw counts used.

    For a single-fault program the model says a test fails with probability

    * ``leak`` when the faulty statement is outside the test's scope, and
    * ``q = 1 - (1 - leak)(1 - theta)`` when it is inside.

    Both are binomial proportions, so ``leak`` and ``q`` are estimated directly
    and the pooled ``theta`` is recovered as ``1 - (1 - q) / (1 - leak)``. The
    prior over fault-specific exposure rates is fitted by
    :func:`fit_exposure_prior`.
    """
    if not cases:
        raise ValueError("cannot estimate parameters from zero cases")
    in_scope_trials = in_scope_fails = out_scope_trials = out_scope_fails = 0
    faulty_statements = total_statements = 0
    flagged_faulty = flagged_clean = clean_statements = 0
    have_static = all(case.static_flags is not None for case in cases)
    per_fault_trials: list[int] = []
    per_fault_fails: list[int] = []

    for case in cases:
        faulty = np.asarray(case.faulty, dtype=bool)
        if int(faulty.sum()) != 1:
            raise ValueError("the estimator is derived for single-fault training cases")
        covers_fault = np.asarray(case.scopes, dtype=bool)[:, faulty].any(axis=1)
        failed = np.asarray(case.failed, dtype=bool)
        per_fault_trials.append(int(covers_fault.sum()))
        per_fault_fails.append(int((covers_fault & failed).sum()))
        in_scope_trials += int(covers_fault.sum())
        in_scope_fails += int((covers_fault & failed).sum())
        out_scope_trials += int((~covers_fault).sum())
        out_scope_fails += int((~covers_fault & failed).sum())
        faulty_statements += 1
        total_statements += int(faulty.size)
        if have_static:
            flags = np.asarray(case.static_flags, dtype=bool)
            flagged_faulty += int((flags & faulty).sum())
            flagged_clean += int((flags & ~faulty).sum())
            clean_statements += int((~faulty).sum())

    leak = _beta_mean(out_scope_fails, out_scope_trials)
    q = _beta_mean(in_scope_fails, in_scope_trials)
    theta = float(np.clip(1.0 - (1.0 - q) / (1.0 - leak), 1e-6, 1.0 - 1e-6))
    grid, weights = fit_exposure_prior(per_fault_trials, per_fault_fails, leak)
    params = ModelParams(
        prior_fault=_beta_mean(faulty_statements, total_statements),
        theta=theta,
        leak=leak,
        theta_grid=tuple(grid.tolist()),
        theta_weights=tuple(weights.tolist()),
        static_tpr=_beta_mean(flagged_faulty, faulty_statements) if have_static else None,
        static_fpr=_beta_mean(flagged_clean, clean_statements) if have_static else None,
        provenance=provenance,
    )
    counts = {
        "training_cases": len(cases),
        "in_scope_trials": in_scope_trials,
        "in_scope_fails": in_scope_fails,
        "out_scope_trials": out_scope_trials,
        "out_scope_fails": out_scope_fails,
        "faults_with_exposure_data": int(sum(1 for n in per_fault_trials if n > 0)),
        "faulty_statements": faulty_statements,
        "total_statements": total_statements,
        "flagged_faulty": flagged_faulty if have_static else None,
        "flagged_clean": flagged_clean if have_static else None,
        "clean_statements": clean_statements if have_static else None,
    }
    return params, counts


def fit_exposure_prior(
    trials: Sequence[int],
    fails: Sequence[int],
    leak: float,
    grid_size: int = config.THETA_GRID_SIZE,
    iterations: int = config.EM_ITERATIONS,
) -> tuple[np.ndarray, np.ndarray]:
    """Fit the discrete prior over the exposure rate ``Theta`` by EM.

    Faults differ in how often they make a covering test fail, so one shared
    ``theta`` is a poor description. Each training fault ``f`` contributes
    ``fails[f]`` failures out of ``trials[f]`` tests that executed it. Under
    the model these are binomial with success probability
    ``q_g = 1 - (1 - leak) * (1 - theta_g)`` when the fault's exposure rate is
    grid point ``theta_g``. The weights ``w_g`` of this mixture of binomials
    are fitted by expectation-maximisation:

    * E-step: ``r[f, g]  proportional to  w_g * Binomial(fails[f]; trials[f], q_g)``
    * M-step: ``w_g = mean over f of r[f, g]``

    The log-likelihood is concave in ``w``, so EM from the uniform start
    climbs to the maximum. One pseudo-observation per grid point is then
    mixed in so that no weight is exactly zero. Faults that no test executed
    carry no information and are skipped.
    """
    grid = (np.arange(grid_size) + 0.5) / grid_size
    n = np.array([t for t in trials if t > 0], dtype=float)
    x = np.array([f for t, f in zip(trials, fails) if t > 0], dtype=float)
    weights = np.full(grid_size, 1.0 / grid_size)
    if n.size == 0:
        return grid, weights
    q = 1.0 - (1.0 - leak) * (1.0 - grid)
    # log Binomial(x; n, q_g) without the binomial coefficient (constant in g).
    log_lik = x[:, None] * np.log(q)[None, :] + (n - x)[:, None] * np.log1p(-q)[None, :]
    for _ in range(iterations):
        log_r = np.log(weights)[None, :] + log_lik
        log_r -= log_r.max(axis=1, keepdims=True)
        r = np.exp(log_r)
        r /= r.sum(axis=1, keepdims=True)
        new_weights = np.maximum(r.mean(axis=0), 1e-300)
        converged = np.max(np.abs(new_weights - weights)) < 1e-12
        weights = new_weights
        if converged:
            break
    weights = (n.size * weights + 1.0) / (n.size + grid_size)
    return grid, weights / weights.sum()


def estimate_binned_likelihood(
    values: np.ndarray, labels: np.ndarray, bins: int
) -> tuple[np.ndarray, np.ndarray]:
    """Estimate ``P(bin | F = 1)`` and ``P(bin | F = 0)`` for a score in [0, 1].

    Used for the LLM-confidence channel: the raw score is not trusted as a
    probability; instead the model learns how each score range is distributed
    among faulty and fault-free statements (add-one smoothing per bin).
    """
    which = bin_index(values, bins)
    labels = np.asarray(labels, dtype=bool)
    p_fault = np.array([(np.sum(which[labels] == b) + 1.0) for b in range(bins)]) / (labels.sum() + bins)
    p_clean = np.array([(np.sum(which[~labels] == b) + 1.0) for b in range(bins)]) / ((~labels).sum() + bins)
    return p_fault, p_clean


def bin_index(values: np.ndarray, bins: int) -> np.ndarray:
    """Equal-width bin index in ``0..bins-1`` for values in [0, 1]."""
    values = np.asarray(values, dtype=float)
    return np.minimum((values * bins).astype(int), bins - 1)
