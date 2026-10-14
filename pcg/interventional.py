"""Interventional multi-fault diagnosis (version 4).

Every analysis variant is treated as an intervention on one statement. If the
statement is faulty the variant may be a repair, and a repair makes a failing
test pass only when that statement is the *sole cause* of the failure: no other
fault and no leak also made the test fail. The probability of that event,
``q(k, theta)``, depends on the number ``k`` of faulty statements the test
executes, so the variant evidence of one statement depends on which other
statements are faulty. The per-statement tables of version 3 cannot express
this.

Two treatments of the variant layer are implemented:

* ``exclusive`` (the model of record): at most one variant per faulty statement
  is a repair, and for every failing test the likelihood is summed exactly over
  which faulty statement, if any, is its sole cause. Two repairs of different
  statements can then not both be credited with fixing the same test.
* ``composite``: every variant is an independent piece of evidence. Simpler and
  faster, kept as an ablation.

Specification: ``research/MATHEMATICAL_DESIGN.md``. Nothing in this module
receives ground truth except :func:`estimate_intervention_params`, which is
only ever called with programs other than the one analysed.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from itertools import combinations
from typing import Optional, Sequence

import numpy as np

_TINY = 1e-9
#: EM starting values (flip rate, break rate) for the kinds of non-repair variants. The first
#: ``n_nonrepair`` entries are used.
NONREPAIR_START = ((0.02, 0.05), (0.02, 0.9), (0.9, 0.9), (0.5, 0.05), (0.02, 0.4), (0.9, 0.4), (0.5, 0.9))
#: EM starting values (strength gamma, break rate beta) for the kinds of repair.
REPAIR_START = ((0.98, 0.02), (0.5, 0.02), (0.9, 0.5))


@dataclass(frozen=True)
class VariantObservation:
    """What one variant did to the tests that execute the statement it edits.

    Attributes:
        column: index of the edited statement.
        failing: indices of the failing tests that execute the statement.
        flips: boolean, aligned with ``failing``; the variant makes the test pass.
        n_passing: passing tests that execute the statement.
        n_breaks: how many of them the variant makes fail.
    """

    column: int
    failing: np.ndarray
    flips: np.ndarray
    n_passing: int
    n_breaks: int


@dataclass(frozen=True)
class InterventionParams:
    """Parameters of the variant layer (section 3 of the design)."""

    alpha: float              # P(some variant of a faulty statement is a repair)
    rho: tuple[float, ...]    # per kind of repair: its share (composite: per-variant probability)
    gamma: tuple[float, ...]  # per kind: P(it makes a test pass | the statement is the sole cause of the failure)
    beta: tuple[float, ...]   # per kind: P(it breaks a passing test)
    kappa: tuple[float, ...]  # mixing weights of the kinds of non-repair variants
    psi: tuple[float, ...]    # per kind: P(variant makes a failing test pass)
    eta: tuple[float, ...]    # per kind: P(variant breaks a passing test)
    tau: float = 1.0          # temperature of the variant layer
    layer: str = "exclusive"  # "exclusive" or "composite"
    provenance: str = ""

    def to_dict(self) -> dict:
        return asdict(self)

    @property
    def delta(self) -> float:
        """P(a repair makes a test pass although its statement is not the sole cause of the failure).

        Not a free parameter: such a repair acts like an inert change, so the
        smallest flip rate among the non-repair kinds is used.
        """
        return min(self.psi)


def variant_observations(
    statements: Sequence[int],
    coverage: np.ndarray,
    failed: np.ndarray,
    expected: Sequence[str],
    variants: Sequence[tuple[int, Optional[Sequence[str]]]],
) -> list[VariantObservation]:
    """Turn variant outcomes into observations. Variants without a complete result are dropped."""
    coverage = np.asarray(coverage, dtype=bool)
    failed = np.asarray(failed, dtype=bool)
    column = {line: i for i, line in enumerate(statements)}
    observations = []
    for line, signatures in variants:
        if signatures is None or len(signatures) != len(expected) or line not in column:
            continue
        col = column[line]
        correct = np.array([s == e for s, e in zip(signatures, expected)], dtype=bool)
        executed = coverage[:, col]
        failing = np.flatnonzero(executed & failed)
        passing = executed & ~failed
        observations.append(VariantObservation(col, failing, correct[failing], int(passing.sum()),
                                               int((passing & ~correct).sum())))
    return observations


def sole_cause_probability(k: np.ndarray, theta: float, leak: float) -> np.ndarray:
    """``q(k, theta)``: P(a failing test fails only because of one given faulty statement it executes).

    ``k >= 1`` is the number of faulty statements the test executes.
    """
    k = np.asarray(k, dtype=float)
    numerator = (1.0 - leak) * theta * (1.0 - theta) ** (k - 1.0)
    denominator = 1.0 - (1.0 - leak) * (1.0 - theta) ** k
    return numerator / np.maximum(denominator, _TINY)


def _binomial_log(successes, trials, p: float):
    p = min(max(p, _TINY), 1.0 - _TINY)
    return successes * np.log(p) + (trials - successes) * np.log1p(-p)


def log_nonrepair(obs: VariantObservation, p: InterventionParams) -> float:
    """``log N_v``: likelihood of the observation if the variant is not a repair."""
    f, t = int(obs.flips.sum()), len(obs.flips)
    terms = [np.log(k) + _binomial_log(f, t, psi) + _binomial_log(obs.n_breaks, obs.n_passing, eta)
             for k, psi, eta in zip(p.kappa, p.psi, p.eta)]
    return float(np.logaddexp.reduce(terms))


# ----------------------------------------------------------------------------
# Estimation (labelled single-fault programs only)
# ----------------------------------------------------------------------------

def _smooth(successes: float, trials: float) -> float:
    return (successes + 1.0) / (trials + 2.0)


def _split(training):
    clean, faulty_groups = [], []
    for observations, mask in training:
        mask = np.asarray(mask, dtype=bool)
        groups: dict[int, list[VariantObservation]] = {}
        for obs in observations:
            if mask[obs.column]:
                groups.setdefault(obs.column, []).append(obs)
            else:
                clean.append(obs)
        faulty_groups.extend(groups.values())
    if not clean:
        raise ValueError("no variants of fault-free statements to estimate from")
    return clean, faulty_groups


def _fit_nonrepair(clean: Sequence[VariantObservation], kinds: int, iterations: int):
    """EM for the mixture of non-repair kinds. Returns (kappa, psi, eta, log-likelihood)."""
    stats = np.array([[o.flips.sum(), len(o.flips), o.n_breaks, o.n_passing] for o in clean], dtype=float)
    f, t, b, s = stats.T
    kappa = np.full(kinds, 1.0 / kinds)
    psi = [NONREPAIR_START[c][0] for c in range(kinds)]
    eta = [NONREPAIR_START[c][1] for c in range(kinds)]
    total = np.zeros(len(clean))
    for _ in range(iterations):
        log_r = np.stack([np.log(kappa[c]) + _binomial_log(f, t, psi[c]) + _binomial_log(b, s, eta[c])
                          for c in range(kinds)])
        total = np.logaddexp.reduce(log_r, axis=0)
        r = np.exp(log_r - total)
        kappa = (r.sum(axis=1) + 1.0) / (r.shape[1] + kinds)
        psi = [_smooth((r[c] * f).sum(), (r[c] * t).sum()) for c in range(kinds)]
        eta = [_smooth((r[c] * b).sum(), (r[c] * s).sum()) for c in range(kinds)]
    return (tuple(float(x) for x in kappa), tuple(float(x) for x in psi), tuple(float(x) for x in eta),
            float(total.sum()))


def estimate_intervention_params(
    training: Sequence[tuple[Sequence[VariantObservation], np.ndarray]],
    provenance: str,
    n_nonrepair: int = 5,
    n_repair: int = 1,
    layer: str = "exclusive",
    iterations: int = 300,
    tau: float = 1.0,
) -> tuple[InterventionParams, dict]:
    """Fit the variant layer by EM on labelled single-fault programs.

    Args:
        training: ``(observations, faulty_mask)`` per program.
        n_nonrepair, n_repair: number of kinds of non-repair and repair variants.
        layer: which treatment the parameters are for (see module docstring).

    Step 1 fits the mixture of non-repair kinds on variants of fault-free
    statements. Step 2 fits ``alpha`` and the repair kinds on variants of
    faulty statements with the mixture fixed and ``q = 1`` (one fault,
    negligible leak). The returned dictionary holds counts, the maximised
    log-likelihoods and their BIC values.
    """
    if layer not in ("exclusive", "composite"):
        raise ValueError(f"unknown layer {layer!r}")
    clean, faulty_groups = _split(training)
    kappa, psi, eta, loglik_clean = _fit_nonrepair(clean, n_nonrepair, iterations)
    mixture = InterventionParams(0.5, (0.5,), (0.9,), (0.05,), kappa, psi, eta)
    groups = [np.array([[o.flips.sum(), len(o.flips), o.n_breaks, o.n_passing, log_nonrepair(o, mixture)] for o in g],
                       dtype=float) for g in faulty_groups]

    alpha = 0.5
    rho = np.full(n_repair, (1.0 if layer == "exclusive" else 0.3) / n_repair)
    gamma = [REPAIR_START[c][0] for c in range(n_repair)]
    beta = [REPAIR_START[c][1] for c in range(n_repair)]
    loglik_faulty = 0.0
    for _ in range(iterations):
        sum_a = sum_variants = 0.0
        sum_rep, flips, flip_trials = np.zeros(n_repair), np.zeros(n_repair), np.zeros(n_repair)
        breaks, break_trials = np.zeros(n_repair), np.zeros(n_repair)
        loglik_faulty = 0.0
        for g in groups:
            fv, tv, bv, sv, ln = g.T
            log_rep = np.stack([np.log(rho[c]) + _binomial_log(fv, tv, gamma[c]) + _binomial_log(bv, sv, beta[c])
                                for c in range(n_repair)])
            if layer == "exclusive":
                # exactly one variant (uniformly chosen) is the repair, of kind c with share rho[c]
                log_terms = log_rep - ln - np.log(len(fv))
                log_a1 = np.log(alpha) + np.logaddexp.reduce(log_terms, axis=None)
                log_a0 = np.log1p(-alpha)
                log_group = np.logaddexp(log_a1, log_a0)
                resp = np.exp(np.log(alpha) + log_terms - log_group)
                p_a = float(np.exp(log_a1 - log_group))
                loglik_faulty += float(log_group + ln.sum())
            else:
                log_non = np.log1p(-rho.sum()) + ln
                log_any = np.logaddexp(np.logaddexp.reduce(log_rep, axis=0), log_non)
                log_a1 = np.log(alpha) + log_any.sum()
                log_a0 = np.log1p(-alpha) + ln.sum()
                log_group = np.logaddexp(log_a1, log_a0)
                p_a = float(np.exp(log_a1 - log_group))
                resp = p_a * np.exp(log_rep - log_any)
                loglik_faulty += float(log_group)
            sum_a += p_a
            sum_variants += p_a * len(fv)
            sum_rep += resp.sum(axis=1)
            flips, flip_trials = flips + resp @ fv, flip_trials + resp @ tv
            breaks, break_trials = breaks + resp @ bv, break_trials + resp @ sv
        alpha = _smooth(sum_a, len(groups))
        if layer == "exclusive":
            rho = (sum_rep + 1.0) / (sum_rep.sum() + n_repair)
        else:
            rho = (sum_rep + 1.0) / (sum_variants + n_repair + 1.0)
        gamma = [_smooth(flips[c], flip_trials[c]) for c in range(n_repair)]
        beta = [_smooth(breaks[c], break_trials[c]) for c in range(n_repair)]
    params = InterventionParams(float(alpha), tuple(float(x) for x in rho), tuple(float(x) for x in gamma),
                                tuple(float(x) for x in beta), kappa, psi, eta, tau, layer, provenance)
    counts = {"variants_of_fault_free_statements": len(clean), "faulty_statements_with_variants": len(groups),
              "variants_of_faulty_statements": int(sum(len(g) for g in groups)),
              "loglik_nonrepair": loglik_clean,
              "bic_nonrepair": float((3 * n_nonrepair - 1) * np.log(len(clean)) - 2 * loglik_clean),
              "loglik_repair": loglik_faulty,
              "bic_repair": float((3 * n_repair) * np.log(max(len(groups), 1)) - 2 * loglik_faulty)}
    return params, counts


# ----------------------------------------------------------------------------
# Inference
# ----------------------------------------------------------------------------

@dataclass(frozen=True)
class InterventionalPosterior:
    """Result of bounded-cardinality inference.

    Attributes:
        marginals: P(F_i = 1 | evidence), shape (n,).
        boundary_mass: posterior mass on configurations with exactly ``max_faults`` faults.
        expected_faults: posterior mean of the number of faulty statements.
        map_faults: indices of the most probable configuration.
        n_configurations: configurations enumerated.
        size_distribution: posterior probability of 0, 1, ..., max_faults faults.
    """

    marginals: np.ndarray
    boundary_mass: float
    expected_faults: float
    map_faults: tuple[int, ...]
    n_configurations: int
    size_distribution: tuple[float, ...]


def _configurations(active: Sequence[int], max_faults: int) -> list[tuple[int, ...]]:
    return [c for r in range(min(max_faults, len(active)) + 1) for c in combinations(active, r)]


def _composite_layer(value, member, counts, by_statement, log_n, params, sole):
    """Add the composite variant layer to ``value`` (shape (N,)) for one theta."""
    q = [np.clip(g_r * sole, _TINY, 1.0 - _TINY) for g_r in params.gamma]
    log_q, log_not_q = [np.log(x) for x in q], [np.log1p(-x) for x in q]
    for s, group in by_statement.items():
        rows = np.flatnonzero(member[:, s])
        total = np.zeros(len(rows))
        for obs in group:
            k = counts[np.ix_(rows, obs.failing)]
            excess = np.zeros(len(rows))
            for r, rho_r in enumerate(params.rho):
                log_rep = np.where(obs.flips[None, :], log_q[r][k], log_not_q[r][k]).sum(axis=1)
                log_rep = log_rep + _binomial_log(obs.n_breaks, obs.n_passing, params.beta[r])
                excess += rho_r * (np.exp(np.minimum(log_rep - log_n[id(obs)], 700.0)) - 1.0)
            total += np.log1p(excess)
        value[rows] += params.tau * np.logaddexp(np.log1p(-params.alpha), np.log(params.alpha) + total)


class _ExclusiveLayer:
    """Exact variant likelihood under "at most one repair per faulty statement".

    For a configuration ``F`` the latent choice ``a_s`` of each faulty statement
    is "no repair among my variants" or one (variant, kind) pair. Given the
    choices, every failing test is summed over which faulty statement in its
    scope is the sole cause of its failure (or none).
    """

    def __init__(self, by_statement, log_n, params, failed, coverage, sole_by_theta):
        self.params = params
        self.failed_tests = np.flatnonzero(failed)
        self.coverage = coverage
        self.sole = sole_by_theta  # (G, k_max + 1)
        m = coverage.shape[0]
        self.options = {}
        for s, group in by_statement.items():
            log_w = [np.log1p(-params.alpha)]
            present = [False]
            flip = [np.zeros(m, dtype=bool)]
            kind = [0]
            for obs in group:
                z = np.zeros(m, dtype=bool)
                z[obs.failing[obs.flips]] = True
                for r, rho_r in enumerate(params.rho):
                    log_w.append(np.log(params.alpha) + np.log(rho_r) - np.log(len(group))
                                 + _binomial_log(obs.n_breaks, obs.n_passing, params.beta[r]) - log_n[id(obs)])
                    present.append(True)
                    flip.append(z)
                    kind.append(r)
            self.options[s] = (np.array(log_w), np.array(present), np.array(flip), np.array(kind))

    def log_ratio(self, config: tuple[int, ...], counts_row: np.ndarray) -> np.ndarray:
        """log of sum over choices of P(variant observations | F, theta) / prod_v N_v, per theta (shape (G,))."""
        statements = [s for s in config if s in self.options]
        g = self.sole.shape[0]
        if not statements:
            return np.zeros(g)
        p = self.params
        gamma = np.array(p.gamma)
        delta = p.delta
        dims = [len(self.options[s][0]) for s in statements]

        def shape(axis: int) -> tuple[int, ...]:
            return tuple(dims[a] if a == axis else 1 for a in range(len(dims)))

        lead = (g,) + (1,) * len(dims)
        log_total = np.zeros((g, *dims))
        for axis, s in enumerate(statements):
            log_total = log_total + self.options[s][0].reshape((1, *shape(axis)))
        for j in self.failed_tests:
            in_scope = [(axis, s) for axis, s in enumerate(statements) if self.coverage[j, s]]
            if not in_scope:
                continue
            k = int(counts_row[j])
            q = self.sole[:, k]
            no_flip, sole_term = [], []
            for axis, s in in_scope:
                _, present, flip, kind = self.options[s]
                z = flip[:, j]
                no_flip.append(np.where(present, np.where(z, delta, 1.0 - delta), 1.0).reshape(shape(axis)))
                strength = gamma[kind]
                sole_term.append(np.where(present, np.where(z, strength, 1.0 - strength), 1.0).reshape(shape(axis)))
            all_no_flip = no_flip[0]
            for term in no_flip[1:]:
                all_no_flip = all_no_flip * term
            inner = np.zeros(tuple(dims))
            for c in range(len(in_scope)):
                term = sole_term[c]
                for other in range(len(in_scope)):
                    if other != c:
                        term = term * no_flip[other]
                inner = inner + term
            # faulty statements in the test's scope that have no variants can also be the sole cause
            silent = k - len(in_scope)
            lik = (q.reshape(lead) * (inner + silent * all_no_flip)[None]
                   + np.maximum(1.0 - k * q, 0.0).reshape(lead) * all_no_flip[None])
            log_total = log_total + np.log(np.maximum(lik, 1e-300))
        flat = log_total.reshape(g, -1)
        peak = flat.max(axis=1)
        return peak + np.log(np.exp(flat - peak[:, None]).sum(axis=1))


@dataclass(frozen=True)
class Enumeration:
    """Unnormalised posterior over the enumerated fault configurations (exposure rate summed out)."""

    configs: list[tuple[int, ...]]
    member: np.ndarray      # (N, n) boolean
    sizes: np.ndarray       # (N,)
    log_weight: np.ndarray  # (N,)
    prior: np.ndarray       # (n,)
    active: list[int]
    max_faults: int


def enumerate_configurations(
    prior: np.ndarray,
    coverage: np.ndarray,
    failed: np.ndarray,
    observations: Sequence[VariantObservation],
    params: Optional[InterventionParams],
    theta_grid: Sequence[float],
    theta_weights: Sequence[float],
    leak: float,
    max_faults: int = 3,
) -> Enumeration:
    """Score every configuration with at most ``max_faults`` faulty statements.

    ``params=None`` (or no observations) gives the spectrum-only model
    restricted to the same configurations.
    """
    prior = np.asarray(prior, dtype=float)
    coverage = np.asarray(coverage, dtype=bool)
    failed = np.asarray(failed, dtype=bool)
    n = coverage.shape[1]
    active = np.flatnonzero(coverage.any(axis=0)).tolist()
    configs = _configurations(active, max_faults)
    member = np.zeros((len(configs), n), dtype=bool)
    for row, config in enumerate(configs):
        member[row, list(config)] = True
    counts = member.astype(np.int64) @ coverage.T.astype(np.int64)  # (N, m): k_j of each configuration
    k_max = int(counts.max()) if counts.size else 0
    ks = np.arange(k_max + 1, dtype=float)
    grid = np.asarray(theta_grid, dtype=float)

    log_odds = np.log(prior) - np.log1p(-prior)
    log_prior = member @ log_odds  # the constant sum_i log(1 - prior_i) cancels on normalisation

    by_statement: dict[int, list[VariantObservation]] = {}
    if params is not None:
        for obs in observations:
            by_statement.setdefault(obs.column, []).append(obs)
    log_n = {id(obs): log_nonrepair(obs, params) for group in by_statement.values() for obs in group}
    sole = np.stack([sole_cause_probability(np.maximum(ks, 1.0), theta, leak) for theta in grid])  # (G, k_max+1)

    log_joint = np.empty((len(grid), len(configs)))
    for g, theta in enumerate(grid):
        pass_log = np.log1p(-leak) + ks * np.log1p(-theta)
        fail_log = np.log(np.maximum(1.0 - np.exp(pass_log), _TINY))
        table = np.where(failed[None, :], fail_log[counts], pass_log[counts])
        value = log_prior + table.sum(axis=1)
        if by_statement and params.layer == "composite":
            _composite_layer(value, member, counts, by_statement, log_n, params, sole[g])
        log_joint[g] = np.log(theta_weights[g]) + value
    if by_statement and params.layer == "exclusive":
        layer = _ExclusiveLayer(by_statement, log_n, params, failed, coverage, sole)
        for row, config in enumerate(configs):
            if config:
                log_joint[:, row] += params.tau * layer.log_ratio(config, counts[row])

    peak = log_joint.max(axis=0)
    log_weight = peak + np.log(np.exp(log_joint - peak[None, :]).sum(axis=0))
    return Enumeration(configs, member, member.sum(axis=1), log_weight, prior, active, max_faults)


def summarise(enumeration: Enumeration, max_faults: Optional[int] = None, odds_scale: float = 1.0) -> InterventionalPosterior:
    """Posterior from an enumeration, optionally with fewer faults allowed or rescaled prior odds.

    ``odds_scale`` multiplies the prior odds of every statement; because a
    failing test rules out the empty configuration, this is in effect the
    prior odds of each *additional* fault.
    """
    e = enumeration
    limit = e.max_faults if max_faults is None else max_faults
    if limit > e.max_faults:
        raise ValueError("cannot allow more faults than were enumerated")
    keep = e.sizes <= limit
    log_weight = e.log_weight[keep] + e.sizes[keep] * np.log(odds_scale)
    member, sizes = e.member[keep], e.sizes[keep]
    weight = np.exp(log_weight - log_weight.max())
    weight /= weight.sum()
    marginals = e.prior.copy()
    marginals[e.active] = (weight[:, None] * member[:, e.active]).sum(axis=0)
    top = min(limit, len(e.active))
    size_distribution = tuple(float(weight[sizes == r].sum()) for r in range(top + 1))
    boundary = size_distribution[-1] if limit < len(e.active) else 0.0
    kept = [c for c, k in zip(e.configs, keep) if k]
    return InterventionalPosterior(marginals, boundary, float((weight * sizes).sum()),
                                   kept[int(np.argmax(weight))], len(kept), size_distribution)


def interventional_posterior(
    prior: np.ndarray,
    coverage: np.ndarray,
    failed: np.ndarray,
    observations: Sequence[VariantObservation],
    params: Optional[InterventionParams],
    theta_grid: Sequence[float],
    theta_weights: Sequence[float],
    leak: float,
    max_faults: int = 3,
) -> InterventionalPosterior:
    """Posterior over fault configurations with at most ``max_faults`` faulty statements.

    Statements no test executes keep their prior. Pass ``max_faults >= n`` for
    the unrestricted posterior (composite layer or no variants only: the
    exclusive layer grows too fast with the number of faults).
    """
    return summarise(enumerate_configurations(prior, coverage, failed, observations, params, theta_grid,
                                              theta_weights, leak, max_faults))
