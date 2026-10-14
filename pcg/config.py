"""Explicit configuration: every tunable number in the project lives here.

Nothing in this file is a *result*. Model parameters (prior, theta, leak, the
static-analysis likelihoods) are estimated from data by ``pcg.estimation`` and
carried in :class:`ModelParams`; this module only defines the containers and
the engineering settings (limits, seeds, grids).
"""

from __future__ import annotations

import os
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from typing import Optional

PROJECT_ROOT = Path(__file__).resolve().parent.parent
RESULTS_DIR = PROJECT_ROOT / "results"

# --- execution sandbox -------------------------------------------------------
#: A test is stopped (and counted as failed) after this many traced line events.
#: A step count is used instead of wall-clock time so outcomes are deterministic.
STEP_LIMIT = 20_000
#: Wall-clock safety net for one runner subprocess, in seconds. A normal run
#: takes about 0.1 s, so this only triggers for pathological programs.
SUBPROCESS_TIMEOUT_S = 10.0
#: Number of runner processes allowed at the same time.
MAX_WORKERS = min(16, os.cpu_count() or 4)
#: Number of program versions sent to one runner process.
RUNNER_BATCH_SIZE = 8

# --- inference ---------------------------------------------------------------
#: Exact enumeration is used while the number of statements that appear in at
#: least one test scope is at most this value (2**22 ~ 4 million states).
EXACT_MAX_ACTIVE = 22
GIBBS_SAMPLES = 4_000
GIBBS_BURN_IN = 1_000
GIBBS_CHAINS = 4
#: Scores are rounded to this many decimals before ranking so that statements
#: that are tied in theory are not separated by floating-point noise.
RANK_DECIMALS = 9

#: Number of grid points of the exposure-rate prior (centres (g + 0.5) / G).
THETA_GRID_SIZE = 10
#: Maximum iterations of the EM algorithm that fits the exposure-rate prior.
EM_ITERATIONS = 2_000

# --- experiments -------------------------------------------------------------
SEED = 20261013
BOOTSTRAP_RESAMPLES = 5_000
PERMUTATION_RESAMPLES = 20_000
ECE_BINS = 10
#: Maximum number of two-fault mutants sampled per program.
TWO_FAULT_PER_PROGRAM = 15
#: Parameter grid for the sensitivity analysis (fixed values, not estimates).
SENSITIVITY_THETA = (0.3, 0.5, 0.7, 0.9, 0.99)
SENSITIVITY_LEAK = (0.0001, 0.001, 0.01, 0.05)
SENSITIVITY_PRIOR = (0.02, 0.05, 0.1, 0.2, 0.3)

# --- research phase (version 3) ------------------------------------------------
#: External programs (QuixBugs) are larger and recursive: a higher step limit
#: and a longer wall-clock limit per runner process.
EXTERNAL_STEP_LIMIT = 100_000
EXTERNAL_TIMEOUT_S = 120.0
#: Mutants sampled per correct QuixBugs program (dataset D3).
EXTERNAL_MUTANTS_PER_PROGRAM = 15
#: Number of levels of the mutation-evidence variable M_i.
MUTATION_LEVELS = 5
#: L2 penalty of the logistic-regression baselines (on standardised features).
LOGISTIC_L2 = 1.0
#: Largest candidate (set of statements) considered by the Barinel baseline.
BARINEL_MAX_CANDIDATE_SIZE = 3
#: Default location of the QuixBugs files (python programs and JSON tests only; see data/external/README.md).
QUIXBUGS_DIR = PROJECT_ROOT / "data" / "external" / "QuixBugs"

# --- repair ------------------------------------------------------------------
#: A "targeted" repair may only edit the K most suspicious statements.
REPAIR_TOP_K = 3

# --- static analysis ---------------------------------------------------------
#: pylint message types treated as potentially correctness-relevant.
STATIC_RELEVANT_TYPES = ("error", "fatal", "warning")
#: Warnings that are about layout or comments, never about behaviour.
#: ``unnecessary-pass`` is excluded for a second reason: the deletion mutation
#: operator writes ``pass`` in place of a statement, so this message would
#: simply reveal where the benchmark injected the fault (see LIMITATIONS.md).
STATIC_IGNORED_SYMBOLS = (
    "unnecessary-pass",
    "bad-indentation",
    "unnecessary-semicolon",
    "fixme",
    "mixed-line-endings",
    "trailing-whitespace",
)


@dataclass(frozen=True)
class ModelParams:
    """Parameters of the PCG model. See MATHEMATICAL_MODEL.md, section 4.

    Attributes:
        prior_fault: pi = P(F_i = 1), prior probability a statement is faulty.
        theta: single pooled estimate of the exposure rate, P(an executed
            faulty statement makes the test fail). Used by the fixed-theta
            ablation and as a summary.
        leak: lambda = P(test fails although no statement in its scope is faulty).
        theta_grid / theta_weights: discrete prior over the exposure rate used
            by the main model. Empty means "use the single value ``theta``".
        static_tpr: P(A_i = 1 | F_i = 1), analyser flags a faulty statement.
        static_fpr: P(A_i = 1 | F_i = 0), analyser flags a fault-free statement.
        provenance: where the numbers came from (never empty).
    """

    prior_fault: float
    theta: float
    leak: float
    theta_grid: tuple[float, ...] = ()
    theta_weights: tuple[float, ...] = ()
    static_tpr: Optional[float] = None
    static_fpr: Optional[float] = None
    provenance: str = "unspecified"

    def __post_init__(self) -> None:
        for name in ("prior_fault", "theta"):
            value = getattr(self, name)
            if not 0.0 < value < 1.0:
                raise ValueError(f"{name} must be strictly between 0 and 1, got {value}")
        if not 0.0 <= self.leak < 1.0:
            raise ValueError(f"leak must be in [0, 1), got {self.leak}")
        for name in ("static_tpr", "static_fpr"):
            value = getattr(self, name)
            if value is not None and not 0.0 < value < 1.0:
                raise ValueError(f"{name} must be strictly between 0 and 1, got {value}")
        object.__setattr__(self, "theta_grid", tuple(float(v) for v in self.theta_grid))
        object.__setattr__(self, "theta_weights", tuple(float(v) for v in self.theta_weights))
        if len(self.theta_grid) != len(self.theta_weights):
            raise ValueError("theta_grid and theta_weights must have the same length")
        if self.theta_grid and abs(sum(self.theta_weights) - 1.0) > 1e-9:
            raise ValueError("theta_weights must sum to 1")

    def exposure_prior(self) -> tuple[tuple[float, ...], tuple[float, ...]]:
        """Grid and weights of the exposure-rate prior (one point if no grid)."""
        if self.theta_grid:
            return self.theta_grid, self.theta_weights
        return (self.theta,), (1.0,)

    def with_fixed_theta(self) -> "ModelParams":
        """The same parameters with the exposure rate fixed at ``theta``."""
        return replace(self, theta_grid=(), theta_weights=(), provenance=self.provenance + " [fixed theta]")

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "ModelParams":
        return cls(**data)

# ----------------------------------------------------------------------------
# Version 4 (interventional multi-fault model); see research/RESEARCH_PROTOCOL.md
# ----------------------------------------------------------------------------

#: The Python split of HumanEvalPack as JSON lines (see data/external/README.md).
HUMANEVALPACK_FILE = PROJECT_ROOT / "data" / "external" / "HumanEvalPack" / "humanevalpack_python.jsonl"
#: Architecture of the variant layer, fixed on development data (protocol section 2).
IV_NONREPAIR_KINDS = 5
IV_REPAIR_KINDS = 1
IV_MAX_FAULTS = 3
#: Sampling of held-out cases per program: (two-fault, three-fault, human bug plus one injected fault).
QUIXBUGS_MULTI_PER_PROGRAM = (10, 6, 6)
#: HumanEvalFix: (one, two, three injected faults, human bug plus one injected fault) per problem.
HUMANEVAL_PER_PROGRAM = (8, 8, 4, 4)
HUMANEVAL_FOLDS = 5
#: Wall-clock limit of one runner batch for HumanEval programs. They run in milliseconds; a batch
#: that needs longer contains a runaway program, which is then reported as "no result".
HUMANEVAL_TIMEOUT_S = 20.0
#: Cases compared with one more allowed fault (hypothesis H6), and their size limit.
TRUNCATION_CHECK_CASES = 100
TRUNCATION_CHECK_MAX_ACTIVE = 14

# ----------------------------------------------------------------------------
# Version 5 (confirmatory study on MBPP); see research/RESEARCH_PROTOCOL_V5.md
# ----------------------------------------------------------------------------

MBPP_FILE = PROJECT_ROOT / "data" / "external" / "MBPP" / "mbpp_full.jsonl"
MBPP_MIN_STATEMENTS = 5
#: Exact inference with variants grows quickly with the size of the function (52 s for 28 statements and 49 variants, results/reproducibility/scoring_time.json).
MBPP_MAX_STATEMENTS = 30
MBPP_TIMEOUT_S = 60.0
#: Versions per program with 1, 2 and 3 injected faults.
MBPP_PER_PROGRAM = (4, 4, 2)
#: Draws of the random tie-breaking in the expected average precision.
EXPECTED_AP_DRAWS = 300
