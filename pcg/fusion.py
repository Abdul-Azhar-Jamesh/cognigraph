"""Version-3 model components: size-aware prior and the mutation-evidence factor.

See research/MATHEMATICAL_DESIGN.md, sections 3 and 4. Everything here is
estimated from labelled cases of *other* programs; nothing is set by hand.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Optional, Sequence

import numpy as np

from . import config
from .mbfl import CONTEXT_ALL, MutationEvidence


@dataclass(frozen=True)
class FusionParams:
    """Learned quantities of the version-3 model.

    Attributes:
        mu: expected number of faulty statements in a program under analysis.
        level_given_fault / level_given_clean: ``P(M = v | F, context = all)``,
            estimated among statements that every failing test executed.
        level_given_fault_nocontext / level_given_clean_nocontext: the same
            tables estimated over all statements; used only by the ablation
            that ignores the coverage context.
        provenance: where the numbers came from.
    """

    mu: float
    level_given_fault: tuple[float, ...]
    level_given_clean: tuple[float, ...]
    level_given_fault_nocontext: tuple[float, ...]
    level_given_clean_nocontext: tuple[float, ...]
    provenance: str = "unspecified"

    def __post_init__(self) -> None:
        if self.mu <= 0:
            raise ValueError("mu must be positive")
        for name in ("level_given_fault", "level_given_clean",
                     "level_given_fault_nocontext", "level_given_clean_nocontext"):
            table = tuple(float(v) for v in getattr(self, name))
            if len(table) != config.MUTATION_LEVELS or min(table) <= 0 or abs(sum(table) - 1.0) > 1e-9:
                raise ValueError(f"{name} must be a strictly positive distribution over {config.MUTATION_LEVELS} levels")
            object.__setattr__(self, name, table)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "FusionParams":
        return cls(**data)


def size_aware_prior(n_statements: int, mu: float) -> float:
    """Prior fault probability ``min(mu / n, 1/2)`` of a statement in a program of size n."""
    if n_statements <= 0:
        raise ValueError("a program needs at least one statement")
    return min(mu / n_statements, 0.5)


def mutation_likelihood_ratio(
    evidence: MutationEvidence, fusion: FusionParams, use_context: bool = True
) -> np.ndarray:
    """``P(M_i | F_i = 1, K_i) / P(M_i | F_i = 0, K_i)`` for every statement.

    With ``use_context`` (the model): the learned ratio for statements that all
    failing tests executed, exactly 1 for every other statement. Without it
    (the ablation): one table for all statements.
    """
    levels = np.asarray(evidence.levels, dtype=int)
    if use_context:
        ratio = np.array(fusion.level_given_fault)[levels] / np.array(fusion.level_given_clean)[levels]
        return np.where(np.asarray(evidence.contexts) == CONTEXT_ALL, ratio, 1.0)
    return np.array(fusion.level_given_fault_nocontext)[levels] / np.array(fusion.level_given_clean_nocontext)[levels]


@dataclass(frozen=True)
class FusionCase:
    """A labelled training example for the version-3 quantities."""

    evidence: MutationEvidence
    faulty: np.ndarray  # boolean (n,), ground truth of a training program


def _table(counts: np.ndarray) -> tuple[float, ...]:
    """Add-one smoothed distribution over the levels."""
    return tuple(((counts + 1.0) / (counts.sum() + counts.size)).tolist())


def estimate_fusion_params(cases: Sequence[FusionCase], provenance: str) -> tuple[FusionParams, dict]:
    """Estimate ``mu`` and the mutation-evidence tables from labelled cases.

    Only cases with at least one failing test should be passed in: the evidence
    variable is undefined when nothing fails.
    """
    if not cases:
        raise ValueError("cannot estimate fusion parameters from zero cases")
    levels = config.MUTATION_LEVELS
    fault_all, clean_all = np.zeros(levels), np.zeros(levels)
    fault_any, clean_any = np.zeros(levels), np.zeros(levels)
    total_faults = 0
    for case in cases:
        faulty = np.asarray(case.faulty, dtype=bool)
        total_faults += int(faulty.sum())
        in_context = np.asarray(case.evidence.contexts) == CONTEXT_ALL
        for level, is_faulty, is_all in zip(case.evidence.levels, faulty, in_context):
            (fault_any if is_faulty else clean_any)[level] += 1
            if is_all:
                (fault_all if is_faulty else clean_all)[level] += 1
    params = FusionParams(
        mu=total_faults / len(cases),
        level_given_fault=_table(fault_all),
        level_given_clean=_table(clean_all),
        level_given_fault_nocontext=_table(fault_any),
        level_given_clean_nocontext=_table(clean_any),
        provenance=provenance,
    )
    counts = {
        "training_cases": len(cases),
        "faulty_statements": total_faults,
        "context_all_faulty_by_level": fault_all.astype(int).tolist(),
        "context_all_clean_by_level": clean_all.astype(int).tolist(),
        "any_context_faulty_by_level": fault_any.astype(int).tolist(),
        "any_context_clean_by_level": clean_any.astype(int).tolist(),
    }
    return params, counts


def effective_prior(
    n_statements: int,
    base_prior: float,
    fusion: Optional[FusionParams] = None,
    evidence: Optional[MutationEvidence] = None,
    *,
    size_aware: bool = False,
    use_mutation: bool = False,
    use_context: bool = True,
) -> np.ndarray:
    """Per-statement prior after the version-3 components (no test evidence yet)."""
    from .model import apply_likelihood_ratio

    if (size_aware or use_mutation) and fusion is None:
        raise ValueError("fusion parameters are required for the size-aware prior and for mutation evidence")
    prior_value = size_aware_prior(n_statements, fusion.mu) if size_aware else base_prior
    prior = np.full(n_statements, prior_value)
    if use_mutation:
        if evidence is None:
            raise ValueError("mutation evidence requested but none was supplied")
        prior = apply_likelihood_ratio(prior, mutation_likelihood_ratio(evidence, fusion, use_context))
    return prior
