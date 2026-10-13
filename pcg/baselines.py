"""Baseline suspiciousness scores (none of them is a probability).

All baselines receive exactly the evidence the PCG model receives from
execution: the coverage matrix and the pass/fail vector. None sees ground truth.

For statement ``i``: ``ef`` / ``ep`` = number of failing / passing tests that
executed it, ``F`` / ``P`` = total failing / passing tests.
"""

from __future__ import annotations

import numpy as np


def spectrum_counts(coverage: np.ndarray, failed: np.ndarray) -> tuple[np.ndarray, np.ndarray, int, int]:
    """Return ``(ef, ep, F, P)`` for a coverage matrix and outcome vector."""
    coverage = np.asarray(coverage, dtype=bool)
    failed = np.asarray(failed, dtype=bool)
    ef = coverage[failed].sum(axis=0).astype(float)
    ep = coverage[~failed].sum(axis=0).astype(float)
    return ef, ep, int(failed.sum()), int((~failed).sum())


def ochiai(coverage: np.ndarray, failed: np.ndarray) -> np.ndarray:
    """Ochiai: ``ef / sqrt(F * (ef + ep))`` (Abreu et al., 2007). 0 when undefined."""
    ef, ep, total_failed, _ = spectrum_counts(coverage, failed)
    denominator = np.sqrt(total_failed * (ef + ep))
    return np.divide(ef, denominator, out=np.zeros_like(ef), where=denominator > 0)


def tarantula(coverage: np.ndarray, failed: np.ndarray) -> np.ndarray:
    """Tarantula: ``(ef/F) / (ef/F + ep/P)`` (Jones & Harrold, 2005). 0 when undefined."""
    ef, ep, total_failed, total_passed = spectrum_counts(coverage, failed)
    fail_rate = ef / total_failed if total_failed else np.zeros_like(ef)
    pass_rate = ep / total_passed if total_passed else np.zeros_like(ep)
    denominator = fail_rate + pass_rate
    return np.divide(fail_rate, denominator, out=np.zeros_like(ef), where=denominator > 0)


def execution_only(coverage: np.ndarray, failed: np.ndarray) -> np.ndarray:
    """Execution-only baseline: number of failing tests that ran the statement.

    Uses failing runs alone and ignores what the passing tests say.
    """
    ef, _, _, _ = spectrum_counts(coverage, failed)
    return ef


def simple_heuristic(coverage: np.ndarray, failed: np.ndarray) -> np.ndarray:
    """A plain heuristic, labelled as such: ``ef - ep`` (failing minus passing runs)."""
    ef, ep, _, _ = spectrum_counts(coverage, failed)
    return ef - ep


def chance(coverage: np.ndarray, failed: np.ndarray) -> np.ndarray:
    """No information: every statement gets the same score (a full tie)."""
    return np.zeros(np.asarray(coverage).shape[1], dtype=float)


BASELINES = {
    "chance": chance,
    "execution_only": execution_only,
    "simple_heuristic": simple_heuristic,
    "tarantula": tarantula,
    "ochiai": ochiai,
}
