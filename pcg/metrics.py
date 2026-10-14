"""Evaluation metrics: ranking quality, probabilistic quality, uncertainty.

Ties are handled analytically. If the faulty statement sits in a group of
equally scored statements occupying rank positions ``a..b``, every metric is
its *expected value under a uniformly random tie-break*. This is deterministic
and treats all methods the same way.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Sequence

import numpy as np

from . import config


def tie_interval(scores: np.ndarray, index: int) -> tuple[int, int]:
    """Best and worst 1-based rank of ``scores[index]`` (higher score = more suspicious)."""
    rounded = np.round(np.asarray(scores, dtype=float), config.RANK_DECIMALS)
    better = int((rounded > rounded[index]).sum())
    tied = int((rounded == rounded[index]).sum())
    return better + 1, better + tied


@dataclass(frozen=True)
class RankMetrics:
    """Ranking metrics for one faulty program with a single labelled fault."""

    top1: float
    top3: float
    reciprocal_rank: float
    expected_rank: float
    exam: float  # expected fraction of statements inspected before reaching the fault
    tie_size: int


def rank_metrics(scores: np.ndarray, fault_index: int) -> RankMetrics:
    """Expected Top-1, Top-3, reciprocal rank and EXAM for one fault."""
    best, worst = tie_interval(scores, fault_index)
    size = worst - best + 1
    positions = np.arange(best, worst + 1)

    def top(k: int) -> float:
        return float(np.clip((k - best + 1) / size, 0.0, 1.0))

    expected_rank = (best + worst) / 2.0
    return RankMetrics(
        top1=top(1),
        top3=top(3),
        reciprocal_rank=float(np.mean(1.0 / positions)),
        expected_rank=expected_rank,
        exam=expected_rank / len(scores),
        tie_size=size,
    )


def multi_fault_metrics(scores: np.ndarray, fault_indices: Sequence[int]) -> dict[str, float]:
    """Metrics when several statements are faulty, using mid-ranks for ties.

    ``first_*`` concern the best-ranked fault (the first one a developer would
    reach); ``all_top5`` asks whether every fault is within the top five.
    """
    mid = [sum(tie_interval(scores, i)) / 2.0 for i in fault_indices]
    first, last = min(mid), max(mid)
    return {
        "first_top1": float(first <= 1.0),
        "first_top3": float(first <= 3.0),
        "first_reciprocal_rank": 1.0 / first,
        "all_top3": float(last <= 3.0),
        "all_top5": float(last <= 5.0),
        "mean_rank": float(np.mean(mid)),
    }


# --- probabilistic quality ---------------------------------------------------

def brier_score(probabilities: np.ndarray, labels: np.ndarray) -> float:
    """Mean squared difference between predicted probability and 0/1 outcome."""
    p, y = np.asarray(probabilities, dtype=float), np.asarray(labels, dtype=float)
    return float(np.mean((p - y) ** 2))


def log_loss(probabilities: np.ndarray, labels: np.ndarray, eps: float = 1e-12) -> float:
    """Mean negative log-likelihood; probabilities are clipped to [eps, 1 - eps]."""
    p = np.clip(np.asarray(probabilities, dtype=float), eps, 1.0 - eps)
    y = np.asarray(labels, dtype=float)
    return float(-np.mean(y * np.log(p) + (1.0 - y) * np.log(1.0 - p)))


def reliability_table(probabilities: np.ndarray, labels: np.ndarray, bins: int = config.ECE_BINS) -> list[dict]:
    """Equal-width reliability bins: mean prediction vs observed frequency."""
    p, y = np.asarray(probabilities, dtype=float), np.asarray(labels, dtype=float)
    edges = np.linspace(0.0, 1.0, bins + 1)
    which = np.minimum(np.digitize(p, edges[1:-1], right=False), bins - 1)
    table = []
    for b in range(bins):
        mask = which == b
        count = int(mask.sum())
        table.append({
            "bin_low": float(edges[b]),
            "bin_high": float(edges[b + 1]),
            "count": count,
            "mean_predicted": float(p[mask].mean()) if count else None,
            "observed_frequency": float(y[mask].mean()) if count else None,
        })
    return table


def expected_calibration_error(probabilities: np.ndarray, labels: np.ndarray, bins: int = config.ECE_BINS) -> float:
    """ECE with equal-width bins. Depends on the binning; read with the table."""
    total = len(np.asarray(probabilities))
    error = 0.0
    for row in reliability_table(probabilities, labels, bins):
        if row["count"]:
            error += row["count"] / total * abs(row["mean_predicted"] - row["observed_frequency"])
    return float(error)


# --- uncertainty of aggregate metrics ----------------------------------------

def cluster_means(values: np.ndarray, clusters: Sequence[str]) -> tuple[np.ndarray, np.ndarray, list[str]]:
    """Per-cluster sums and counts, in sorted cluster order."""
    names = sorted(set(clusters))
    position = {name: i for i, name in enumerate(names)}
    sums, counts = np.zeros(len(names)), np.zeros(len(names))
    for value, cluster in zip(values, clusters):
        sums[position[cluster]] += value
        counts[position[cluster]] += 1
    return sums, counts, names


def cluster_bootstrap_ci(
    values: np.ndarray,
    clusters: Sequence[str],
    resamples: int = config.BOOTSTRAP_RESAMPLES,
    seed: int = config.SEED,
    level: float = 0.95,
) -> tuple[float, float]:
    """Percentile bootstrap CI for a mean, resampling whole clusters.

    Mutants of the same program share code and tests, so they are not
    independent observations. The program is the sampling unit: programs are
    drawn with replacement and all their mutants come along.
    """
    sums, counts, names = cluster_means(np.asarray(values, dtype=float), clusters)
    rng = np.random.default_rng(seed)
    draws = rng.integers(0, len(names), size=(resamples, len(names)))
    stats = sums[draws].sum(axis=1) / counts[draws].sum(axis=1)
    alpha = (1.0 - level) / 2.0
    return float(np.quantile(stats, alpha)), float(np.quantile(stats, 1.0 - alpha))


def paired_sign_flip_test(
    differences_by_cluster: np.ndarray,
    resamples: int = config.PERMUTATION_RESAMPLES,
    seed: int = config.SEED,
) -> float:
    """Two-sided Monte Carlo sign-flip permutation test on paired differences.

    Null hypothesis: within each cluster the two methods are exchangeable, so
    the sign of each per-cluster mean difference is equally likely to be + or -.
    Returns the p-value with the +1 correction (never exactly zero).
    """
    d = np.asarray(differences_by_cluster, dtype=float)
    observed = abs(d.mean())
    rng = np.random.default_rng(seed)
    signs = rng.choice((-1.0, 1.0), size=(resamples, d.size))
    permuted = np.abs((signs * d[None, :]).mean(axis=1))
    return float((1 + np.sum(permuted >= observed - 1e-15)) / (resamples + 1))


def summarize(
    values: np.ndarray, clusters: Sequence[str], statistic: Callable[[np.ndarray], float] = np.mean
) -> dict[str, float]:
    """Mean with a cluster-bootstrap 95% interval."""
    low, high = cluster_bootstrap_ci(values, clusters)
    return {"mean": float(statistic(np.asarray(values, dtype=float))), "ci_low": low, "ci_high": high}


# --- selective localisation ----------------------------------------------------

def brier_skill(probabilities: np.ndarray, labels: np.ndarray, reference: np.ndarray) -> float:
    """Skill score ``1 - Brier(model) / Brier(reference)``; positive means better than the reference."""
    return 1.0 - brier_score(probabilities, labels) / brier_score(reference, labels)


def risk_coverage(confidence: np.ndarray, correctness: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Risk at every coverage level when the most confident cases are answered first.

    ``correctness`` is the (tie-aware, expected) Top-1 of each case. Cases with
    equal confidence are averaged, so the curve does not depend on their order.
    Returns ``(coverage, risk)`` with ``coverage[k-1] = k / N``.
    """
    confidence = np.round(np.asarray(confidence, dtype=float), config.RANK_DECIMALS)
    correctness = np.asarray(correctness, dtype=float)
    order = np.argsort(-confidence, kind="stable")
    sorted_conf, sorted_correct = confidence[order], correctness[order].copy()
    start = 0
    while start < len(order):  # replace each tie group by its mean correctness
        stop = start
        while stop < len(order) and sorted_conf[stop] == sorted_conf[start]:
            stop += 1
        sorted_correct[start:stop] = sorted_correct[start:stop].mean()
        start = stop
    answered = np.arange(1, len(order) + 1)
    return answered / len(order), 1.0 - np.cumsum(sorted_correct) / answered


def aurc(confidence: np.ndarray, correctness: np.ndarray) -> float:
    """Area under the risk-coverage curve (mean risk over all coverage levels). Lower is better."""
    return float(risk_coverage(confidence, correctness)[1].mean())


def aurc_reference_values(correctness: np.ndarray) -> dict[str, float]:
    """AURC of an uninformative confidence (all cases tied) and of an oracle confidence."""
    correctness = np.asarray(correctness, dtype=float)
    return {
        "uninformative": aurc(np.zeros(correctness.size), correctness),
        "oracle": aurc(correctness, correctness),
    }


# --- several faults ------------------------------------------------------------

def average_precision(scores: np.ndarray, fault_indices: Sequence[int]) -> float:
    """Average precision over the faulty statements, with mid-ranks for ties.

    ``AP = mean over faults t of |{faults u : r(u) <= r(t)}| / r(t)`` where
    ``r`` is the mid-rank. With one fault this is its reciprocal mid-rank.
    """
    mid = [sum(tie_interval(scores, i)) / 2.0 for i in fault_indices]
    return float(np.mean([sum(1 for u in mid if u <= r) / r for r in mid]))


def roc_auc(scores: np.ndarray, labels: np.ndarray) -> float:
    """Probability that a positive has a higher score than a negative (ties count one half)."""
    scores, labels = np.asarray(scores, dtype=float), np.asarray(labels, dtype=bool)
    positives, negatives = scores[labels], scores[~labels]
    if len(positives) == 0 or len(negatives) == 0:
        return float("nan")
    greater = (positives[:, None] > negatives[None, :]).sum()
    ties = (positives[:, None] == negatives[None, :]).sum()
    return float((greater + 0.5 * ties) / (len(positives) * len(negatives)))
