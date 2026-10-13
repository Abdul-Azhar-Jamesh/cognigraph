"""Barinel: the established Bayesian spectrum-based localiser, as a baseline.

Reimplemented from Abreu, Zoeteweij and van Gemund, "Spectrum-based Multiple
Fault Localization" (ASE 2009), section III:

* candidates ``d`` are minimal hitting sets of the failing runs;
* ``Pr(d) = p^|d| (1 - p)^(n - |d|)``;
* a run that executed the candidate's components ``c`` passes with probability
  ``prod_{j in c} h_j`` and fails with ``1 - prod h_j``;
* the health values ``h`` are chosen to maximise ``Pr(e | d)`` for each candidate;
* candidates are ranked by ``Pr(d | e)``.

Difference from the paper: the paper finds candidates with the heuristic
STACCATO and truncates the list at 100. The programs here are small, so the
minimal hitting sets are enumerated exhaustively up to a fixed size. The
optimiser is coordinate ascent from several starting points instead of
gradient ascent; it reproduces the paper's worked example (see tests).
"""

from __future__ import annotations

from itertools import combinations, product

import numpy as np

from . import config

_GOLDEN = (np.sqrt(5.0) - 1.0) / 2.0


def minimal_hitting_sets(failing_coverage: np.ndarray, max_size: int) -> list[tuple[int, ...]]:
    """All minimal sets of statements that intersect every failing run."""
    failing_coverage = np.asarray(failing_coverage, dtype=bool)
    if failing_coverage.shape[0] == 0:
        return []
    relevant = [int(i) for i in np.flatnonzero(failing_coverage.any(axis=0))]
    found: list[tuple[int, ...]] = []
    for size in range(1, max_size + 1):
        for combo in combinations(relevant, size):
            if any(set(smaller) <= set(combo) for smaller in found):
                continue  # a proper subset already hits everything: not minimal
            if failing_coverage[:, list(combo)].any(axis=1).all():
                found.append(combo)
    return found


def _log_likelihood(h: np.ndarray, patterns: np.ndarray, failed: np.ndarray) -> float:
    """log Pr(e | d, h); ``patterns[r, k]`` says whether run r executed component k of d."""
    with np.errstate(divide="ignore"):
        log_h = np.log(h)
    log_pass = np.where(patterns, log_h[None, :], 0.0).sum(axis=1)
    with np.errstate(divide="ignore"):
        log_fail = np.log(-np.expm1(log_pass))
    return float(np.where(failed, log_fail, log_pass).sum())


def max_likelihood(patterns: np.ndarray, failed: np.ndarray) -> tuple[float, np.ndarray]:
    """Maximise ``Pr(e | d, h)`` over ``h`` in [0, 1]^k. Returns (likelihood, h)."""
    patterns = np.asarray(patterns, dtype=bool)
    failed = np.asarray(failed, dtype=bool)
    involved = patterns.any(axis=1)
    if np.any(failed & ~involved):
        return 0.0, np.full(patterns.shape[1], np.nan)  # a failing run the candidate cannot explain
    patterns, failed = patterns[involved], failed[involved]
    k = patterns.shape[1]
    if k == 1:  # closed form: the pass fraction among the runs that executed the component
        n_pass, n_fail = int((~failed).sum()), int(failed.sum())
        h = np.array([n_pass / (n_pass + n_fail)]) if n_pass + n_fail else np.array([1.0])
        return float(np.exp(_log_likelihood(h, patterns, failed))), h

    starts = product((0.1, 0.3, 0.5, 0.7, 0.9), repeat=k)
    best_value, best_h = -np.inf, None
    for start in starts:
        value = _log_likelihood(np.array(start), patterns, failed)
        if value > best_value:
            best_value, best_h = value, np.array(start)
    h = best_h.copy()
    for _ in range(60):  # coordinate ascent; each coordinate's objective is concave
        previous = best_value
        for j in range(k):
            low, high = 0.0, 1.0
            for _ in range(40):  # golden-section search on [0, 1]
                a, b = high - _GOLDEN * (high - low), low + _GOLDEN * (high - low)
                trial = h.copy()
                trial[j] = a
                value_a = _log_likelihood(trial, patterns, failed)
                trial[j] = b
                value_b = _log_likelihood(trial, patterns, failed)
                if value_a < value_b:
                    low = a
                else:
                    high = b
            h[j] = (low + high) / 2.0
        best_value = _log_likelihood(h, patterns, failed)
        if best_value - previous < 1e-10:
            break
    return float(np.exp(best_value)), h


def barinel_candidates(coverage: np.ndarray, failed: np.ndarray, prior: float,
                       max_size: int = config.BARINEL_MAX_CANDIDATE_SIZE) -> list[tuple[tuple[int, ...], float]]:
    """Ranked diagnosis: ``(candidate, posterior)`` pairs, most probable first."""
    coverage = np.asarray(coverage, dtype=bool)
    failed = np.asarray(failed, dtype=bool)
    n = coverage.shape[1]
    weights = []
    candidates = minimal_hitting_sets(coverage[failed], max_size)
    for candidate in candidates:
        likelihood, _ = max_likelihood(coverage[:, list(candidate)], failed)
        weights.append(prior ** len(candidate) * (1.0 - prior) ** (n - len(candidate)) * likelihood)
    total = sum(weights)
    if total <= 0:
        return []
    ranked = sorted(zip(candidates, (w / total for w in weights)), key=lambda item: (-item[1], item[0]))
    return ranked


def barinel(coverage: np.ndarray, failed: np.ndarray, prior: float,
            max_size: int = config.BARINEL_MAX_CANDIDATE_SIZE) -> np.ndarray:
    """Statement scores: the posterior of the best candidate containing the statement.

    Sorting statements by this score gives the order in which they appear in
    Barinel's ranked diagnosis. Statements in no candidate score 0. These
    scores are not statement-level fault probabilities.
    """
    scores = np.zeros(np.asarray(coverage).shape[1])
    for candidate, posterior in barinel_candidates(coverage, failed, prior, max_size):
        for statement in candidate:
            scores[statement] = max(scores[statement], posterior)
    return scores
