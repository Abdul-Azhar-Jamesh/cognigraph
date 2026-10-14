"""FLITSR: multi-fault spectrum-based localisation by iterative test-suite reduction.

Re-implemented from Callaghan and Fischer, "Improving Spectrum-Based
Localization of Multiple Faults by Iterative Test Suite Reduction" (ISSTA
2023): the core algorithm and the multi-round variant FLITSR*. This is an
independent implementation, not the authors' tool; it is checked against the
properties stated in the paper (see ``tests/test_v4.py``).

Core algorithm, with a base metric (here Ochiai):

1. rank the elements on the current test suite and take the top one (with all
   elements that have the same spectrum, its ambiguity group);
2. remove every failing test that executes it; repeat until no failing test
   is left. The selected elements form a *span*;
3. go through the selections from last to first and drop a selection whose
   failing tests are all executed by selections kept so far. What remains is
   a *basis*.

Basis elements are ranked first, in selection order; the other elements follow
in the order of the base metric. FLITSR* repeats the procedure on the elements
outside the bases found so far.
"""

from __future__ import annotations

import numpy as np

from .baselines import ochiai


def _basis(coverage: np.ndarray, passing: np.ndarray, failing: np.ndarray, elements: np.ndarray,
           base_scores: np.ndarray) -> list[list[int]]:
    """One FLITSR round restricted to ``elements``. Returns the basis as groups in selection order."""
    remaining = failing.copy()
    full_failing = coverage[failing].sum(axis=0)
    selected: list[list[int]] = []
    while remaining.any():
        suite = passing | remaining  # removed failing tests are no longer part of the suite
        scores = ochiai(coverage[suite], remaining[suite])
        scores = np.where(elements & coverage[remaining].any(axis=0), scores, -np.inf)
        best = scores.max()
        if not np.isfinite(best):
            break  # the remaining failing tests execute no available element
        tied = np.flatnonzero(scores == best)
        # tie-break: original score, then number of failing tests in the original suite, then position
        top = min(tied, key=lambda i: (-base_scores[i], -full_failing[i], i))
        group = [int(i) for i in tied if np.array_equal(coverage[:, i], coverage[:, top])]  # ambiguity group
        selected.append(group)
        remaining = remaining & ~coverage[:, group].any(axis=1)
    explained = np.zeros(len(failing), dtype=bool)
    kept: list[list[int]] = []
    for group in reversed(selected):
        own = failing & coverage[:, group].any(axis=1)
        if (own & ~explained).any():
            kept.append(group)
            explained |= own
    return kept[::-1]


def flitsr(coverage: np.ndarray, failed: np.ndarray, multi_round: bool = False) -> np.ndarray:
    """Suspiciousness scores that reproduce the FLITSR (or FLITSR*) ranking.

    Basis elements get scores above 1 (decreasing with selection order), which
    puts them above every base-metric score (Ochiai is at most 1); the other
    elements keep their Ochiai score.
    """
    coverage = np.asarray(coverage, dtype=bool)
    failed = np.asarray(failed, dtype=bool)
    base = ochiai(coverage, failed)
    ranked: list[list[int]] = []
    elements = np.ones(coverage.shape[1], dtype=bool)
    failing = failed.copy()
    while failing.any():
        basis = _basis(coverage, ~failed, failing, elements, base)
        if not basis:
            break
        ranked.extend(basis)
        if not multi_round:
            break
        elements[[i for group in basis for i in group]] = False
        # drop failing tests that only ranked elements execute: nothing else can explain them
        failing = failing & coverage[:, elements].any(axis=1)
    scores = base.astype(float).copy()
    for position, group in enumerate(ranked):
        scores[group] = 1.0 + (len(ranked) - position)
    return scores
