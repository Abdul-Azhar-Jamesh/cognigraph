"""Mutation-analysis evidence and the mutation-based baselines.

For a program under analysis, every single-edit *variant* of each statement is
run against the test suite. What the variants do to the test outcomes is
summarised per statement in three ways:

* the evidence variable ``M_i`` (five levels) with its coverage context, used
  by the Bayesian model (research/v3/MATHEMATICAL_DESIGN.md, section 4);
* the Metallaxis score and the MUSE score, two published mutation-based
  suspiciousness measures, defined as in Pearson et al. (ICSE 2017, sec. III-A).

Nothing in this module knows where the fault is. "Variant" is used for the
mutants generated *for analysis*, to keep them apart from the mutants that
serve as faulty programs in the benchmark.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Sequence

import numpy as np

#: Coverage contexts of a statement.
CONTEXT_NONE, CONTEXT_PART, CONTEXT_ALL = 0, 1, 2
CONTEXT_NAMES = ("none", "part", "all")

#: Levels of the evidence variable M_i.
LEVEL_NO_VARIANT = 0      # no operator applies to the statement
LEVEL_NO_EFFECT = 1       # no variant makes a failing test pass
LEVEL_PARTIAL = 2         # some variant makes some, not all, failing tests pass
LEVEL_FIXES_BREAKS = 3    # a variant makes all failing tests pass but breaks a passing one
LEVEL_PLAUSIBLE = 4       # a variant makes every test pass
LEVEL_NAMES = ("no variant", "no effect", "partial", "fixes failing, breaks passing", "all tests pass")


@dataclass(frozen=True)
class MutationEvidence:
    """Per-statement summary of the mutation analysis of one program.

    Attributes:
        levels: shape (n,), the level of ``M_i`` for each statement.
        contexts: shape (n,), coverage context of each statement.
        metallaxis: shape (n,), Metallaxis suspiciousness.
        muse: shape (n,), MUSE suspiciousness.
        n_variants: variants generated.
        n_usable: variants that compiled and returned a result for every test.
    """

    levels: np.ndarray
    contexts: np.ndarray
    metallaxis: np.ndarray
    muse: np.ndarray
    n_variants: int
    n_usable: int


def coverage_context(coverage: np.ndarray, failed: np.ndarray) -> np.ndarray:
    """Context of each statement: executed by all, some or none of the failing tests."""
    coverage = np.asarray(coverage, dtype=bool)
    failed = np.asarray(failed, dtype=bool)
    n_failed = int(failed.sum())
    if n_failed == 0:
        return np.full(coverage.shape[1], CONTEXT_NONE, dtype=int)
    hits = coverage[failed].sum(axis=0)
    return np.where(hits == n_failed, CONTEXT_ALL, np.where(hits > 0, CONTEXT_PART, CONTEXT_NONE)).astype(int)


def mutation_evidence(
    statements: Sequence[int],
    coverage: np.ndarray,
    failed: np.ndarray,
    base_signatures: Sequence[str],
    expected: Sequence[str],
    variants: Sequence[tuple[int, Optional[Sequence[str]]]],
) -> MutationEvidence:
    """Summarise variant outcomes.

    Args:
        statements: statement lines of the analysed program.
        coverage, failed: its spectrum.
        base_signatures: behaviour of the analysed program on each test.
        expected: the oracle's behaviour on each test.
        variants: ``(line, signatures)`` for every variant; ``signatures`` is
            None when the variant did not compile or gave no result.
    """
    statements = list(statements)
    failed = np.asarray(failed, dtype=bool)
    n, m = len(statements), len(expected)
    column = {line: i for i, line in enumerate(statements)}
    contexts = coverage_context(coverage, failed)
    n_failed = int(failed.sum())

    levels = np.full(n, LEVEL_NO_VARIANT, dtype=int)
    metallaxis = np.zeros(n)
    muse_sum, muse_count = np.zeros(n), np.zeros(n)
    usable: list[tuple[int, int, int, int, int]] = []  # (column, f2p, p2f, killed_failing, killed_passing)
    for line, signatures in variants:
        if signatures is None or len(signatures) != m or line not in column:
            continue
        same_as_oracle = np.array([s == e for s, e in zip(signatures, expected)])
        changed = np.array([s != b for s, b in zip(signatures, base_signatures)])
        usable.append((
            column[line],
            int((same_as_oracle & failed).sum()),
            int((~same_as_oracle & ~failed).sum()),
            int((changed & failed).sum()),
            int((changed & ~failed).sum()),
        ))

    if n_failed == 0:  # nothing to explain: the evidence variable is undefined
        return MutationEvidence(levels, contexts, metallaxis, np.zeros(n), len(variants), len(usable))

    total_f2p = sum(u[1] for u in usable)
    total_p2f = sum(u[2] for u in usable)
    alpha = total_f2p / total_p2f if total_p2f > 0 else 0.0
    for col, f2p, p2f, killed_failing, killed_passing in usable:
        if f2p == n_failed and p2f == 0:
            level = LEVEL_PLAUSIBLE
        elif f2p == n_failed:
            level = LEVEL_FIXES_BREAKS
        elif f2p > 0:
            level = LEVEL_PARTIAL
        else:
            level = LEVEL_NO_EFFECT
        levels[col] = max(levels[col], level)
        denominator = np.sqrt(n_failed * (killed_failing + killed_passing))
        if denominator > 0:
            metallaxis[col] = max(metallaxis[col], killed_failing / denominator)
        muse_sum[col] += f2p - alpha * p2f
        muse_count[col] += 1

    has_variant = muse_count > 0
    muse = np.zeros(n)
    muse[has_variant] = muse_sum[has_variant] / muse_count[has_variant]
    # Statements without variants are placed below every statement that has some.
    floor = (muse[has_variant].min() if has_variant.any() else 0.0) - 1.0
    muse[~has_variant] = floor
    return MutationEvidence(levels, contexts, metallaxis, muse, len(variants), len(usable))


def hybrid_average(ochiai_scores: np.ndarray, metallaxis_scores: np.ndarray) -> np.ndarray:
    """Mean of a spectrum score and a mutation score (both in [0, 1]).

    In the spirit of the MCBFL-hybrid-avg technique of Pearson et al.; their
    coverage-based adjustment of mutant scores is not reproduced.
    """
    return (np.asarray(ochiai_scores, dtype=float) + np.asarray(metallaxis_scores, dtype=float)) / 2.0
