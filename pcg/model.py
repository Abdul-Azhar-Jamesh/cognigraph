"""The probabilistic model and its inference algorithms.

Model (MATHEMATICAL_MODEL.md gives the derivation):

* ``F_i in {0, 1}``: latent, statement ``i`` is faulty.
* ``T_j in {0, 1}``: observed, test ``j`` failed.
* ``Theta``: latent *exposure rate*, the probability that an executed faulty
  statement makes a test fail. It is unknown and differs from fault to fault,
  so it gets a discrete prior ``P(Theta = theta_g) = w_g`` on a grid and is
  summed out. A grid with a single point gives the fixed-theta model.
* Prior: the ``F_i`` are independent Bernoulli(``prior[i]``). Per-statement
  evidence (static analysis, an LLM signal) enters by Bayes' rule as a
  likelihood ratio that turns the base prior into ``prior[i]``.
* Likelihood: noisy-OR. With ``k_j(F)`` the number of faulty statements in the
  scope of test ``j``::

      P(T_j = pass | F, Theta) = (1 - leak) * (1 - Theta) ** k_j(F)

* Joint: ``P(F, Theta, T) = P(Theta) * prod_i P(F_i) * prod_j P(T_j | F, Theta)``.

Each failing test couples every statement in its scope, so the posterior does
not factorise over statements. It is computed exactly by enumerating fault
configurations and grid points, or approximately by Gibbs sampling when there
are too many statements.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from typing import Optional, Sequence, Union

import numpy as np

from . import config


class ImpossibleEvidenceError(ValueError):
    """The observed test outcomes have probability zero under the model."""


@dataclass(frozen=True)
class FaultModel:
    """A fully specified model instance for one program and one test run.

    Attributes:
        prior: shape (n,), P(F_i = 1) after per-statement evidence.
        scopes: boolean shape (m, n); ``scopes[j, i]`` is True when statement
            ``i`` can influence test ``j``. This is the graph structure.
        failed: boolean shape (m,), observed test outcomes.
        theta: grid of exposure rates, shape (g,). A scalar is accepted and
            means a single fixed value.
        leak: P(test fails with no faulty statement in scope).
        theta_weights: prior probability of each grid point (uniform if None).
    """

    prior: np.ndarray
    scopes: np.ndarray
    failed: np.ndarray
    theta: Union[float, Sequence[float], np.ndarray]
    leak: float
    theta_weights: Optional[Union[Sequence[float], np.ndarray]] = None

    def __post_init__(self) -> None:
        prior = np.asarray(self.prior, dtype=float)
        scopes = np.asarray(self.scopes, dtype=bool)
        failed = np.asarray(self.failed, dtype=bool)
        theta = np.atleast_1d(np.asarray(self.theta, dtype=float))
        weights = (np.full(theta.size, 1.0 / theta.size) if self.theta_weights is None
                   else np.asarray(self.theta_weights, dtype=float))
        if prior.ndim != 1:
            raise ValueError("prior must be a vector")
        if scopes.ndim != 2 or scopes.shape[1] != prior.shape[0]:
            raise ValueError("scopes must have shape (tests, statements)")
        if failed.shape != (scopes.shape[0],):
            raise ValueError("failed must have one entry per test")
        if np.any(~np.isfinite(prior)) or np.any(prior < 0.0) or np.any(prior > 1.0):
            raise ValueError("priors must be probabilities in [0, 1]")
        if theta.ndim != 1 or theta.size == 0 or np.any(theta < 0.0) or np.any(theta > 1.0):
            raise ValueError("theta values must be probabilities in [0, 1]")
        if weights.shape != theta.shape or np.any(weights < 0.0) or abs(weights.sum() - 1.0) > 1e-9:
            raise ValueError("theta_weights must be a probability vector matching theta")
        if not 0.0 <= self.leak < 1.0:
            raise ValueError("leak must be in [0, 1)")
        object.__setattr__(self, "prior", prior)
        object.__setattr__(self, "scopes", scopes)
        object.__setattr__(self, "failed", failed)
        object.__setattr__(self, "theta", theta)
        object.__setattr__(self, "theta_weights", weights)

    @property
    def n_statements(self) -> int:
        return int(self.prior.shape[0])

    @property
    def n_tests(self) -> int:
        return int(self.scopes.shape[0])


@dataclass(frozen=True)
class Posterior:
    """Result of inference.

    Attributes:
        marginals: shape (n,), P(F_i = 1 | evidence).
        p_no_fault: P(no statement is faulty | evidence); None for Gibbs.
        log_evidence: log P(observed test outcomes); None for Gibbs.
        expected_faults: posterior mean number of faulty statements.
        theta_posterior: shape (g,), P(Theta = theta_g | evidence).
        method: "exact" or "gibbs".
        rhat: largest Gelman-Rubin statistic over statements (Gibbs only).
    """

    marginals: np.ndarray
    p_no_fault: Optional[float]
    log_evidence: Optional[float]
    expected_faults: float
    theta_posterior: np.ndarray
    method: str
    rhat: Optional[float] = None


def apply_likelihood_ratio(prior: np.ndarray, likelihood_ratio: np.ndarray) -> np.ndarray:
    """Bayes' rule in odds form for per-statement evidence.

    ``posterior odds = prior odds * P(e | F=1) / P(e | F=0)``, element-wise.
    """
    prior = np.asarray(prior, dtype=float)
    ratio = np.asarray(likelihood_ratio, dtype=float)
    if np.any(ratio < 0.0) or np.any(~np.isfinite(ratio)):
        raise ValueError("likelihood ratios must be finite and non-negative")
    numerator = prior * ratio
    return numerator / (numerator + (1.0 - prior))


def log_test_likelihood(scopes: np.ndarray, failed: np.ndarray, theta: float, leak: float,
                        configs: np.ndarray) -> np.ndarray:
    """log P(observed outcomes | F, theta) for each row of ``configs`` (shape (c, n)).

    Returns ``-inf`` for configurations under which the outcomes are impossible.
    """
    counts = configs.astype(np.float64) @ scopes.T.astype(np.float64)  # (c, m): k_j(F)
    p_pass = (1.0 - leak) * np.power(1.0 - theta, counts)
    p_outcome = np.where(failed[None, :], 1.0 - p_pass, p_pass)
    with np.errstate(divide="ignore"):
        return np.log(p_outcome).sum(axis=1)


def _log_prior(prior: np.ndarray, configs: np.ndarray) -> np.ndarray:
    with np.errstate(divide="ignore"):
        log_p1, log_p0 = np.log(prior), np.log1p(-prior)
    # A statement with prior exactly 0 or 1 must contribute 0, not 0 * -inf.
    on = np.where(configs, log_p1[None, :], 0.0)
    off = np.where(configs, 0.0, log_p0[None, :])
    return (on + off).sum(axis=1)


def _all_configs(n: int, start: int, stop: int) -> np.ndarray:
    """Rows ``start..stop-1`` of the 2**n binary configurations, as booleans."""
    index = np.arange(start, stop, dtype=np.int64)[:, None]
    return ((index >> np.arange(n, dtype=np.int64)[None, :]) & 1).astype(bool)


_CHUNK = 1 << 16


@lru_cache(maxsize=1024)
def _likelihood_table(scopes_bytes: bytes, failed_bytes: bytes, m: int, a: int, theta: float, leak: float) -> np.ndarray:
    """log P(outcomes | F, theta) for all ``2**a`` configurations.

    The table depends on the graph structure, the outcomes and (theta, leak)
    but not on the priors, so it is cached and reused when only per-statement
    evidence changes. The cache never changes a result.
    """
    scopes = np.frombuffer(scopes_bytes, dtype=bool).reshape(m, a)
    failed = np.frombuffer(failed_bytes, dtype=bool)
    total = 1 << a
    out = np.empty(total, dtype=np.float64)
    for start in range(0, total, _CHUNK):
        stop = min(total, start + _CHUNK)
        out[start:stop] = log_test_likelihood(scopes, failed, theta, leak, _all_configs(a, start, stop))
    out.setflags(write=False)
    return out


def _logsumexp(values: np.ndarray) -> float:
    peak = values.max()
    if not np.isfinite(peak):
        return float("-inf")
    return float(peak + np.log(np.exp(values - peak).sum()))


def exact_posterior(model: FaultModel) -> Posterior:
    """Exact posterior marginals by enumeration.

    Statements outside every test scope are independent of the tests, so their
    posterior equals their prior and they are left out of the enumeration. For
    the ``a`` remaining ("active") statements and ``g`` grid points all
    ``g * 2**a`` joint states are summed in log space.
    Cost: ``O(g * 2**a * (a + m))`` time.
    """
    active = np.flatnonzero(model.scopes.any(axis=0))
    a = int(active.size)
    if a > config.EXACT_MAX_ACTIVE:
        raise ValueError(
            f"{a} active statements exceed the exact-inference limit "
            f"({config.EXACT_MAX_ACTIVE}); use gibbs_posterior"
        )
    prior = model.prior[active]
    scopes = np.ascontiguousarray(model.scopes[:, active])
    total = 1 << a

    log_prior = np.empty(total, dtype=np.float64)
    for start in range(0, total, _CHUNK):
        stop = min(total, start + _CHUNK)
        log_prior[start:stop] = _log_prior(prior, _all_configs(a, start, stop))

    log_joint = np.full(total, -np.inf)  # log P(F, T), Theta summed out
    log_theta_joint = np.empty(model.theta.size)  # log P(Theta = theta_g, T)
    for g, (theta, weight) in enumerate(zip(model.theta, model.theta_weights)):
        table = _likelihood_table(scopes.tobytes(), model.failed.tobytes(), model.n_tests, a, float(theta), model.leak)
        with np.errstate(divide="ignore"):
            term = np.log(weight) + log_prior + table
        log_theta_joint[g] = _logsumexp(term)
        log_joint = np.logaddexp(log_joint, term)

    log_evidence = _logsumexp(log_joint)
    if not np.isfinite(log_evidence):
        raise ImpossibleEvidenceError(
            "the observed test outcomes have zero probability under the model "
            "(for example a failing test with an empty scope and leak = 0)"
        )
    weights = np.exp(log_joint - log_evidence)

    marginals = model.prior.copy()
    index = np.arange(total, dtype=np.int64)
    for position, column in enumerate(active):
        marginals[column] = float(weights[((index >> position) & 1).astype(bool)].sum())

    inactive = np.setdiff1d(np.arange(model.n_statements), active)
    return Posterior(
        marginals=marginals,
        p_no_fault=float(weights[0] * np.prod(1.0 - model.prior[inactive])),
        log_evidence=log_evidence,
        expected_faults=float(marginals.sum()),
        theta_posterior=np.exp(log_theta_joint - log_evidence),
        method="exact",
    )


def gibbs_posterior(
    model: FaultModel,
    n_samples: int = config.GIBBS_SAMPLES,
    burn_in: int = config.GIBBS_BURN_IN,
    n_chains: int = config.GIBBS_CHAINS,
    seed: int = config.SEED,
) -> Posterior:
    """Approximate posterior marginals by Gibbs sampling.

    Each sweep resamples every active ``F_i`` from ``P(F_i | F_-i, Theta, T)``
    and then ``Theta`` from ``P(Theta | F, T)``. Several chains are run from
    different starting points and compared with the Gelman-Rubin statistic
    (values near 1 mean the chains agree; it cannot prove convergence). The
    noisy-OR posterior can be multi-modal, so mixing may be slow when ``leak``
    is very small.
    """
    rng = np.random.default_rng(seed)
    active = np.flatnonzero(model.scopes.any(axis=0))
    marginals = model.prior.copy()
    if model.leak == 0.0 and np.any(model.failed & ~model.scopes.any(axis=1)):
        raise ImpossibleEvidenceError("a test with an empty scope failed although leak = 0")
    if active.size == 0:
        return Posterior(marginals, None, None, float(marginals.sum()), model.theta_weights.copy(), "gibbs", rhat=1.0)

    scopes = model.scopes[:, active].astype(np.float64)  # (m, a)
    prior = model.prior[active]
    log_base = np.log1p(-model.leak)
    with np.errstate(divide="ignore"):
        log_q = np.log1p(-model.theta)  # per grid point; -inf when theta == 1
        log_w = np.log(model.theta_weights)

    def log_likelihood(counts: np.ndarray, g: int) -> float:
        with np.errstate(invalid="ignore"):
            log_pass = log_base + np.where(counts > 0, counts * log_q[g], 0.0)
        with np.errstate(divide="ignore"):
            log_fail = np.log(-np.expm1(log_pass))
        return float(np.where(model.failed, log_fail, log_pass).sum())

    chain_means = np.zeros((n_chains, active.size))
    chain_vars = np.zeros((n_chains, active.size))
    theta_counts = np.zeros(model.theta.size)
    for chain in range(n_chains):
        state = np.ones(active.size) if chain % 2 == 0 else (rng.random(active.size) < 0.5).astype(float)
        counts = scopes @ state
        g = int(rng.integers(model.theta.size))
        if not np.isfinite(log_likelihood(counts, g)):
            # "Every in-scope statement faulty" is the most permissive start.
            state = np.ones(active.size)
            counts = scopes @ state
            finite = [k for k in range(model.theta.size) if np.isfinite(log_likelihood(counts, k))]
            if not finite:
                raise ImpossibleEvidenceError("no state with positive probability was found")
            g = finite[0]
        draws = np.zeros((n_samples, active.size))
        for sweep in range(burn_in + n_samples):
            for i in range(active.size):
                counts_off = counts - scopes[:, i] * state[i]
                counts_on = counts_off + scopes[:, i]
                with np.errstate(divide="ignore"):
                    log_on = np.log(prior[i]) + log_likelihood(counts_on, g)
                    log_off = np.log1p(-prior[i]) + log_likelihood(counts_off, g)
                p_on = 1.0 / (1.0 + np.exp(np.clip(log_off - log_on, -700.0, 700.0)))
                state[i] = 1.0 if rng.random() < p_on else 0.0
                counts = counts_on if state[i] == 1.0 else counts_off
            if model.theta.size > 1:
                log_p = log_w + np.array([log_likelihood(counts, k) for k in range(model.theta.size)])
                p = np.exp(log_p - log_p.max())
                g = int(rng.choice(model.theta.size, p=p / p.sum()))
            if sweep >= burn_in:
                draws[sweep - burn_in] = state
                theta_counts[g] += 1
        chain_means[chain] = draws.mean(axis=0)
        chain_vars[chain] = draws.var(axis=0, ddof=1)

    marginals[active] = chain_means.mean(axis=0)
    within = chain_vars.mean(axis=0)
    between = n_samples * chain_means.var(axis=0, ddof=1) if n_chains > 1 else np.zeros(active.size)
    with np.errstate(divide="ignore", invalid="ignore"):
        pooled = (n_samples - 1) / n_samples * within + between / n_samples
        rhat = np.sqrt(np.where(within > 0, pooled / within, 1.0))
    return Posterior(
        marginals=marginals,
        p_no_fault=None,
        log_evidence=None,
        expected_faults=float(marginals.sum()),
        theta_posterior=theta_counts / theta_counts.sum(),
        method="gibbs",
        rhat=float(np.max(rhat)),
    )


def infer(model: FaultModel, seed: int = config.SEED) -> Posterior:
    """Exact inference when feasible, Gibbs sampling otherwise."""
    if int(model.scopes.any(axis=0).sum()) <= config.EXACT_MAX_ACTIVE:
        return exact_posterior(model)
    return gibbs_posterior(model, seed=seed)
