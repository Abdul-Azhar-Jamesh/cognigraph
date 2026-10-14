"""Experiments of the research phase (version 3). Protocol: research/v3/RESEARCH_PROPOSAL.md.

Datasets
    D1  the project's benchmark, leave-one-program-out.
    D2  QuixBugs: human-written bugs. Parameters come from D1 ("transfer") or
        from mutants of the other QuixBugs programs ("in-suite").
    D3  mutants of the correct QuixBugs programs; parameters from D1.

Every learned quantity (model parameters, mutation tables, regression weights,
recalibration map) is fitted on programs other than the one being analysed.
Ground truth is read only when fitting on *other* programs and when computing
metrics.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional, Sequence

import numpy as np

from . import baselines, config, experiments as ex, metrics
from .barinel import barinel
from .config import ModelParams
from .dependence import analyze_dependence
from .discriminative import (FUSION_FEATURES, SPECTRUM_FEATURES, LogisticModel, Recalibration, fit_logistic,
                             fit_recalibration, statement_features)
from .estimation import LabelledCase, estimate_params
from .execution import build_spectrum, run_sources
from .fusion import FusionCase, FusionParams, effective_prior, estimate_fusion_params
from .mbfl import CONTEXT_NONE, LEVEL_NO_EFFECT, MutationEvidence, hybrid_average, mutation_evidence
from .model import FaultModel, infer
from .mutation import generate_mutants
from .analysis import compute_scopes
from .program import Program
from .quixbugs import ExternalProgram, load_quixbugs
from .static_analysis import flagged_lines, run_pylint

RANK_METHODS = ("ochiai", "tarantula", "barinel", "metallaxis", "muse", "hybrid_avg", "lr_spectrum", "lr_fusion",
                "pcg", "pcg_size", "pcg_fused", "pcg_fused_nocontext", "pcg_fused_const")
PROB_METHODS = ("lr_spectrum", "lr_fusion", "pcg", "pcg_size", "pcg_fused", "pcg_fused_nocontext", "pcg_fused_const")
#: Confidence used for abstention: the largest score of a method, or the Ochiai gap.
CONFIDENCE_METHODS = ("pcg", "pcg_size", "pcg_fused", "lr_spectrum", "lr_fusion", "ochiai", "ochiai_gap",
                      "metallaxis", "hybrid_avg")
PRIMARY_COMPARISONS = (("pcg_fused", "pcg_size"), ("pcg_fused", "lr_fusion"), ("pcg_fused", "hybrid_avg"),
                       ("pcg_fused", "metallaxis"), ("pcg_fused", "ochiai"), ("pcg_fused", "pcg_fused_nocontext"),
                       ("pcg_size", "pcg"))
RANK_KEYS = ("top1", "top3", "reciprocal_rank", "exam")


# ----------------------------------------------------------------------------
# Mutation analysis
# ----------------------------------------------------------------------------

@dataclass
class VariantStore:
    """Outcomes of analysis variants, shared by all cases of one program.

    The behaviour of a source text on a test suite does not depend on which
    faulty program it was generated from, so each distinct text is run once.
    """

    outcomes: dict[str, Optional[tuple[str, ...]]]
    runs: int
    seconds: float


def run_variants(cases: Sequence[ex.Case], step_limit: int, timeout: float) -> tuple[dict[str, list], VariantStore]:
    """Generate and execute the analysis variants of the given cases (one program)."""
    variants = {case.case_id: generate_mutants(case.program) for case in cases}
    texts = sorted({v.source for vs in variants.values() for v in vs})
    start = time.time()
    case = cases[0]
    runs = run_sources(texts, case.program.func_name, case.tests, step_limit=step_limit, timeout=timeout)
    outcomes = {}
    for text, run in zip(texts, runs):
        usable = run is not None and run.compile_error is None and len(run.tests) == len(case.tests)
        outcomes[text] = tuple(t.signature for t in run.tests) if usable else None
    return variants, VariantStore(outcomes, len(texts), time.time() - start)


def evidence_for_case(case: ex.Case, variants: Sequence, store: VariantStore,
                      exclude_text: Optional[str] = None) -> MutationEvidence:
    """Mutation evidence of one case. ``exclude_text`` drops one variant (stress test only)."""
    usable = [(v.line, store.outcomes[v.source]) for v in variants if v.source != exclude_text]
    return mutation_evidence(case.program.statements, case.spectrum.coverage, case.spectrum.failed,
                             [t.signature for t in case.run.tests], case.expected, usable)


def collect_evidence(cases: Sequence[ex.Case], step_limit: int, timeout: float,
                     reference_source: Optional[dict[str, str]] = None, log: Callable[[str], None] = print):
    """Mutation evidence for all cases, program by program.

    Returns ``(evidence, stress_evidence, cost)``. ``stress_evidence`` (only if
    ``reference_source`` is given) is computed without the variant whose text
    equals the reference program.
    """
    evidence, stress = {}, {}
    cost = {"variant_texts_run": 0, "seconds": 0.0, "variants_generated": 0, "cases": 0}
    for name in sorted({c.program_name for c in cases}):
        own = [c for c in cases if c.program_name == name]
        variants, store = run_variants(own, step_limit, timeout)
        cost["variant_texts_run"] += store.runs
        cost["seconds"] += store.seconds
        for case in own:
            cost["variants_generated"] += len(variants[case.case_id])
            cost["cases"] += 1
            evidence[case.case_id] = evidence_for_case(case, variants[case.case_id], store)
            if reference_source is not None:
                stress[case.case_id] = evidence_for_case(case, variants[case.case_id], store, reference_source[name])
            ev = evidence[case.case_id]
            # A statement that no failing test executes cannot be affected by its variants.
            assert np.all(ev.levels[ev.contexts == CONTEXT_NONE] <= LEVEL_NO_EFFECT), case.case_id
    log(f"    mutation analysis: {cost['variant_texts_run']} variant runs for {cost['cases']} cases "
        f"in {cost['seconds']:.0f}s")
    return evidence, stress, cost


# ----------------------------------------------------------------------------
# Scoring one case with every method
# ----------------------------------------------------------------------------

@dataclass
class Trained:
    """Everything fitted on the training programs of one fold."""

    params: ModelParams
    fusion: FusionParams
    lr_spectrum: LogisticModel
    lr_fusion: LogisticModel


def posterior(case: ex.Case, prior: np.ndarray, params: ModelParams) -> np.ndarray:
    grid, weights = params.exposure_prior()
    return infer(FaultModel(prior, case.scopes["coverage"], case.spectrum.failed, grid, params.leak, weights)).marginals


def features_of(case: ex.Case, evidence: MutationEvidence) -> tuple[np.ndarray, np.ndarray]:
    spectrum = statement_features(case.spectrum.coverage, case.spectrum.failed)
    fusion = statement_features(case.spectrum.coverage, case.spectrum.failed, evidence, case.flags)
    return spectrum, fusion


def train(valid_cases: Sequence[ex.Case], detected: Sequence[ex.Case], evidence: dict, provenance: str) -> Trained:
    """Fit all learned quantities on the given (training) cases."""
    labelled = [LabelledCase(c.scopes["coverage"], c.spectrum.failed, c.faulty_mask, c.flags) for c in valid_cases]
    params, _ = estimate_params(labelled, provenance)
    fusion, _ = estimate_fusion_params([FusionCase(evidence[c.case_id], c.faulty_mask) for c in detected], provenance)
    spectrum_x, fusion_x, y = [], [], []
    for c in detected:
        s, f = features_of(c, evidence[c.case_id])
        spectrum_x.append(s)
        fusion_x.append(f)
        y.append(c.faulty_mask.astype(float))
    return Trained(params, fusion, fit_logistic(np.vstack(spectrum_x), np.concatenate(y)),
                   fit_logistic(np.vstack(fusion_x), np.concatenate(y)))


def score_case(case: ex.Case, evidence: MutationEvidence, trained: Trained) -> dict[str, np.ndarray]:
    """Scores of every method for one case. Receives no ground truth."""
    coverage, failed = case.spectrum.coverage, case.spectrum.failed
    n = len(case.program.statements)
    params, fusion = trained.params, trained.fusion
    spectrum_x, fusion_x = features_of(case, evidence)
    ochiai_scores = baselines.ochiai(coverage, failed)
    scores = {
        "ochiai": ochiai_scores,
        "tarantula": baselines.tarantula(coverage, failed),
        "barinel": barinel(coverage, failed, params.prior_fault),
        "metallaxis": evidence.metallaxis,
        "muse": evidence.muse,
        "hybrid_avg": hybrid_average(ochiai_scores, evidence.metallaxis),
        "lr_spectrum": trained.lr_spectrum.predict(spectrum_x),
        "lr_fusion": trained.lr_fusion.predict(fusion_x),
        "pcg": posterior(case, effective_prior(n, params.prior_fault), params),
        "pcg_size": posterior(case, effective_prior(n, params.prior_fault, fusion, size_aware=True), params),
        "pcg_fused": posterior(case, effective_prior(n, params.prior_fault, fusion, evidence, size_aware=True,
                                                     use_mutation=True), params),
        "pcg_fused_nocontext": posterior(case, effective_prior(n, params.prior_fault, fusion, evidence,
                                                               size_aware=True, use_mutation=True, use_context=False), params),
        "pcg_fused_const": posterior(case, effective_prior(n, params.prior_fault, fusion, evidence,
                                                           use_mutation=True), params),
    }
    return scores


def best_fault_metrics(scores: np.ndarray, fault_indices: Sequence[int]) -> metrics.RankMetrics:
    """Rank metrics for the best-ranked of the ground-truth statements."""
    candidates = [metrics.rank_metrics(scores, i) for i in fault_indices]
    return min(candidates, key=lambda m: (m.expected_rank, -m.reciprocal_rank))


def case_row(case: ex.Case, scores: dict[str, np.ndarray], evidence: MutationEvidence) -> dict:
    """Metrics of all methods for one case (this is where ground truth is used)."""
    fault_indices = np.flatnonzero(case.faulty_mask).tolist()
    row = {
        "case_id": case.case_id, "program": case.program_name, "category": case.truth.categories[0],
        "operator": case.truth.operators[0], "fault_line": case.truth.fault_lines[0],
        "n_statements": len(case.program.statements), "n_tests": case.spectrum.n_tests,
        "n_failed": case.spectrum.n_failed,
        "fault_level": int(max(evidence.levels[i] for i in fault_indices)),
        "statements_at_top_level": int((evidence.levels == evidence.levels.max()).sum()),
    }
    for method in RANK_METHODS:
        m = best_fault_metrics(scores[method], fault_indices)
        row.update({f"{method}.top1": m.top1, f"{method}.top3": m.top3,
                    f"{method}.reciprocal_rank": m.reciprocal_rank, f"{method}.exam": m.exam})
    for method in CONFIDENCE_METHODS:
        if method == "ochiai_gap":
            ordered = np.sort(scores["ochiai"])[::-1]
            confidence = float(ordered[0] - ordered[1]) if ordered.size > 1 else float(ordered[0])
        else:
            confidence = float(np.max(scores[method]))
        row[f"{method}.confidence"] = confidence
    return row


# ----------------------------------------------------------------------------
# Aggregation
# ----------------------------------------------------------------------------

def aggregate(rows: Sequence[dict], methods: Sequence[str] = RANK_METHODS) -> dict:
    return ex._aggregate(rows, methods, RANK_KEYS)


def comparisons(rows: Sequence[dict], pairs: Sequence[tuple[str, str]] = PRIMARY_COMPARISONS) -> list[dict]:
    return [ex._paired(rows, a, b, key) for a, b in pairs for key in ("top1", "reciprocal_rank")]


def probabilistic_quality(prob: dict[str, list], labels: Sequence[int], sizes: Sequence[int],
                          programs: Sequence[str]) -> dict:
    """Brier, skill, log loss, ECE for every probabilistic method, with program-level intervals."""
    y = np.asarray(labels, dtype=float)
    n = np.asarray(sizes, dtype=float)
    base_size = 1.0 / n
    base_pooled = np.full(y.size, y.mean())  # the in-sample base rate: an optimistic reference
    out = {"n_statements": int(y.size), "n_faulty": int(y.sum()), "methods": {}}
    references = {"base_rate_1_over_n": base_size, "base_rate_pooled_in_sample": base_pooled}
    for name, p in list(references.items()) + [(k, np.asarray(v)) for k, v in prob.items()]:
        squared = (p - y) ** 2
        low, high = metrics.cluster_bootstrap_ci(squared, programs)
        out["methods"][name] = {
            "brier": float(squared.mean()), "brier_ci_low": low, "brier_ci_high": high,
            "skill_vs_1_over_n": metrics.brier_skill(p, y, base_size),
            "log_loss": metrics.log_loss(p, y),
            "ece": metrics.expected_calibration_error(p, y),
            "reliability": metrics.reliability_table(p, y),
        }
    return out


def paired_brier(prob: dict[str, list], labels: Sequence[int], programs: Sequence[str],
                 pairs: Sequence[tuple[str, str]]) -> list[dict]:
    """Paired difference of per-statement squared error, programs as the unit."""
    y = np.asarray(labels, dtype=float)
    out = []
    for a, b in pairs:
        diff = (np.asarray(prob[a]) - y) ** 2 - (np.asarray(prob[b]) - y) ** 2
        sums, counts, _ = metrics.cluster_means(diff, programs)
        low, high = metrics.cluster_bootstrap_ci(diff, programs)
        out.append({"comparison": f"{a} - {b}", "metric": "brier (lower is better)",
                    "mean_difference": float(diff.mean()), "ci_low": low, "ci_high": high,
                    "sign_flip_p_value": metrics.paired_sign_flip_test(sums / counts)})
    return out


def selective(rows: Sequence[dict]) -> dict:
    """Risk-coverage analysis: does a method's confidence identify its correct answers?

    The confidence of method X is paired with the Top-1 correctness of method X
    (for ``ochiai_gap`` with the correctness of Ochiai). The returned
    dictionary has one entry per confidence and an entry ``comparisons`` with
    bootstrap intervals for selected pairs.
    """
    out = {}
    for method in CONFIDENCE_METHODS:
        answer = "ochiai" if method == "ochiai_gap" else method
        correct = np.array([row[f"{answer}.top1"] for row in rows])
        confidence = np.array([row[f"{method}.confidence"] for row in rows])
        coverage, risk = metrics.risk_coverage(confidence, correct)
        reference = metrics.aurc_reference_values(correct)
        span = reference["uninformative"] - reference["oracle"]
        picks = {f"risk_at_coverage_{int(c * 100)}": float(risk[max(int(np.ceil(c * len(rows))) - 1, 0)])
                 for c in (0.25, 0.5, 0.75, 1.0)}
        out[method] = {
            "answers_scored": answer, "aurc": metrics.aurc(confidence, correct),
            "aurc_uninformative": reference["uninformative"], "aurc_oracle": reference["oracle"],
            # 1 = as good as an oracle confidence, 0 = no better than no confidence at all.
            "normalised_gain": float((reference["uninformative"] - metrics.aurc(confidence, correct)) / span) if span > 0 else 0.0,
            **picks,
            "curve": [{"coverage": float(c), "risk": float(r)} for c, r in zip(coverage, risk)],
        }
    out["comparisons"] = [selective_comparison(rows, a, b) for a, b in SELECTIVE_COMPARISONS]
    return out


#: Pairs of confidences compared with uncertainty (first minus second).
SELECTIVE_COMPARISONS = (("pcg_size", "ochiai_gap"), ("pcg_size", "ochiai"), ("pcg_fused", "lr_fusion"))


def _selective_summary(rows: Sequence[dict], method: str) -> tuple[float, float]:
    """(AURC, normalised gain) of one confidence on a set of cases."""
    answer = "ochiai" if method == "ochiai_gap" else method
    correct = np.array([row[f"{answer}.top1"] for row in rows])
    confidence = np.array([row[f"{method}.confidence"] for row in rows])
    value = metrics.aurc(confidence, correct)
    reference = metrics.aurc_reference_values(correct)
    span = reference["uninformative"] - reference["oracle"]
    return value, (reference["uninformative"] - value) / span if span > 0 else 0.0


def selective_comparison(rows: Sequence[dict], a: str, b: str, resamples: int = 2000,
                         seed: int = config.SEED) -> dict:
    """Difference of AURC and of normalised gain between two confidences, with bootstrap intervals.

    Whole programs are resampled. A negative AURC difference and a positive
    gain difference favour the first confidence.
    """
    by_program: dict[str, list[dict]] = {}
    for row in rows:
        by_program.setdefault(row["program"], []).append(row)
    names = sorted(by_program)
    rng = np.random.default_rng(seed)
    aurc_a, gain_a = _selective_summary(rows, a)
    aurc_b, gain_b = _selective_summary(rows, b)
    d_aurc, d_gain = [], []
    for _ in range(resamples):
        sample = [row for i in rng.integers(0, len(names), len(names)) for row in by_program[names[int(i)]]]
        sa, sb = _selective_summary(sample, a), _selective_summary(sample, b)
        d_aurc.append(sa[0] - sb[0])
        d_gain.append(sa[1] - sb[1])
    return {
        "comparison": f"{a} - {b}",
        "aurc_difference": aurc_a - aurc_b,
        "aurc_ci_low": float(np.quantile(d_aurc, 0.025)), "aurc_ci_high": float(np.quantile(d_aurc, 0.975)),
        "gain_difference": gain_a - gain_b,
        "gain_ci_low": float(np.quantile(d_gain, 0.025)), "gain_ci_high": float(np.quantile(d_gain, 0.975)),
    }


# ----------------------------------------------------------------------------
# D1: leave-one-program-out on the project's benchmark
# ----------------------------------------------------------------------------

def run_d1(cases: Sequence[ex.Case], evidence: dict, names: Sequence[str], log: Callable[[str], None] = print) -> dict:
    """All methods on D1, every learned quantity fitted without the held-out program."""
    detected = [c for c in cases if c.detected]
    rows, posteriors = [], {}
    prob = {m: [] for m in PROB_METHODS}
    labels, sizes, programs = [], [], []
    trained_by_fold = {}
    for held_out in names:
        fold = train([c for c in cases if c.program_name != held_out],
                     [c for c in detected if c.program_name != held_out], evidence,
                     f"D1 leave-one-program-out, {held_out} held out")
        trained_by_fold[held_out] = fold
        for case in (c for c in detected if c.program_name == held_out):
            scores = score_case(case, evidence[case.case_id], fold)
            rows.append(case_row(case, scores, evidence[case.case_id]))
            posteriors[case.case_id] = scores["pcg_fused"]
            for m in PROB_METHODS:
                prob[m].extend(scores[m].tolist())
            labels.extend(case.faulty_mask.astype(int).tolist())
            sizes.extend([len(case.program.statements)] * len(case.program.statements))
            programs.extend([case.program_name] * len(case.program.statements))
    log(f"    D1: {len(rows)} detected cases scored with {len(RANK_METHODS)} methods")
    by_category = {}
    for category in sorted({r["category"] for r in rows}):
        subset = [r for r in rows if r["category"] == category]
        by_category[category] = {"n": len(subset), **{
            m: {k: float(np.mean([r[f"{m}.{k}"] for r in subset])) for k in ("top1", "reciprocal_rank")}
            for m in ("ochiai", "metallaxis", "hybrid_avg", "lr_fusion", "pcg_size", "pcg_fused")}}
    return {"rows": rows, "overall": aggregate(rows), "comparisons": comparisons(rows), "by_category": by_category,
            "prob": prob, "labels": labels, "sizes": sizes, "programs": programs,
            "posteriors": posteriors, "trained": trained_by_fold}


def run_stress(cases: Sequence[ex.Case], stress_evidence: dict, names: Sequence[str]) -> dict:
    """D1 again, with the reference-restoring variant removed from every mutation analysis."""
    detected = [c for c in cases if c.detected]
    rows = []
    for held_out in names:
        fold = train([c for c in cases if c.program_name != held_out],
                     [c for c in detected if c.program_name != held_out], stress_evidence,
                     f"D1 stress test, {held_out} held out")
        for case in (c for c in detected if c.program_name == held_out):
            rows.append(case_row(case, score_case(case, stress_evidence[case.case_id], fold),
                                 stress_evidence[case.case_id]))
    methods = ("ochiai", "metallaxis", "muse", "hybrid_avg", "lr_fusion", "pcg_size", "pcg_fused")
    return {"overall": aggregate(rows, methods),
            "comparisons": comparisons(rows, (("pcg_fused", "pcg_size"), ("pcg_fused", "lr_fusion"),
                                              ("pcg_fused", "hybrid_avg"), ("pcg_fused", "metallaxis")))}


def run_recalibration(cases: Sequence[ex.Case], evidence: dict, names: Sequence[str], d1: dict,
                      log: Callable[[str], None] = print) -> tuple[dict, Recalibration]:
    """Nested leave-one-program-out recalibration of ``pcg_fused``.

    The map applied to program X is fitted on posteriors of programs Y != X
    that were computed with parameters from programs other than X and Y.
    Returns the recalibrated probabilities (aligned with ``d1['labels']``) and
    the map fitted on all out-of-fold D1 posteriors, for use on other benchmarks.
    """
    detected = [c for c in cases if c.detected]
    by_program = {name: [c for c in detected if c.program_name == name] for name in names}
    pair_posteriors: dict[tuple[str, str], dict[str, np.ndarray]] = {}
    for i, x in enumerate(names):
        for y_name in names[i + 1:]:
            keep = lambda c: c.program_name not in (x, y_name)  # noqa: E731
            labelled = [LabelledCase(c.scopes["coverage"], c.spectrum.failed, c.faulty_mask, c.flags)
                        for c in cases if keep(c)]
            params, _ = estimate_params(labelled, "nested")
            fusion, _ = estimate_fusion_params(
                [FusionCase(evidence[c.case_id], c.faulty_mask) for c in detected if keep(c)], "nested")
            store = {}
            for case in by_program[x] + by_program[y_name]:
                n = len(case.program.statements)
                store[case.case_id] = posterior(case, effective_prior(
                    n, params.prior_fault, fusion, evidence[case.case_id], size_aware=True, use_mutation=True), params)
            pair_posteriors[(x, y_name)] = store
    maps, recalibrated = {}, []
    for x in names:
        p_train, y_train = [], []
        for y_name in names:
            if y_name == x:
                continue
            store = pair_posteriors[(x, y_name) if (x, y_name) in pair_posteriors else (y_name, x)]
            for case in by_program[y_name]:
                p_train.extend(store[case.case_id].tolist())
                y_train.extend(case.faulty_mask.astype(int).tolist())
        maps[x] = fit_recalibration(np.array(p_train), np.array(y_train))
    for row in d1["rows"]:  # same order as d1["labels"]
        recalibrated.extend(maps[row["program"]].apply(d1["posteriors"][row["case_id"]]).tolist())
    all_p = np.concatenate([d1["posteriors"][row["case_id"]] for row in d1["rows"]])
    transfer_map = fit_recalibration(all_p, np.array(d1["labels"]))
    log(f"    recalibration: nested maps fitted for {len(maps)} programs; "
        f"slope range {min(m.a for m in maps.values()):.3f} to {max(m.a for m in maps.values()):.3f}")
    return ({"recalibrated": recalibrated,
             "maps": {name: {"a": m.a, "b": m.b} for name, m in maps.items()},
             "transfer_map": {"a": transfer_map.a, "b": transfer_map.b}}, transfer_map)


def run_size_prior(cases: Sequence[ex.Case], d1: dict) -> dict:
    """Constant prior versus size-aware prior, spectrum evidence only, all valid mutants."""
    p_const, p_size, labels, sizes, programs = [], [], [], [], []
    for case in cases:
        fold = d1["trained"][case.program_name]
        n = len(case.program.statements)
        p_const.extend(posterior(case, effective_prior(n, fold.params.prior_fault), fold.params).tolist())
        p_size.extend(posterior(case, effective_prior(n, fold.params.prior_fault, fold.fusion, size_aware=True),
                                fold.params).tolist())
        labels.extend(case.faulty_mask.astype(int).tolist())
        sizes.extend([n] * n)
        programs.extend([case.program_name] * n)
    p_const, p_size, y, n_arr = np.array(p_const), np.array(p_size), np.array(labels, dtype=float), np.array(sizes)
    strata = {"4 to 5 statements": n_arr <= 5, "6 to 8 statements": (n_arr >= 6) & (n_arr <= 8),
              "9 to 16 statements": n_arr >= 9}

    def quality(p, mask):
        return {"statements": int(mask.sum()), "observed_fault_rate": float(y[mask].mean()),
                "mean_predicted": float(p[mask].mean()), "brier": metrics.brier_score(p[mask], y[mask]),
                "log_loss": metrics.log_loss(p[mask], y[mask]), "ece": metrics.expected_calibration_error(p[mask], y[mask])}

    everything = np.ones(y.size, dtype=bool)
    diff = (p_size - y) ** 2 - (p_const - y) ** 2
    sums, counts, _ = metrics.cluster_means(diff, programs)
    low, high = metrics.cluster_bootstrap_ci(diff, programs)
    return {
        "overall": {"pcg": quality(p_const, everything), "pcg_size": quality(p_size, everything)},
        "by_program_size": {name: {"pcg": quality(p_const, mask), "pcg_size": quality(p_size, mask)}
                            for name, mask in strata.items()},
        "paired_brier_difference_size_minus_const": {
            "mean_difference": float(diff.mean()), "ci_low": low, "ci_high": high,
            "sign_flip_p_value": metrics.paired_sign_flip_test(sums / counts)},
    }


def run_two_fault(two_fault_cases: Sequence[ex.Case], evidence: dict, d1: dict) -> dict:
    """POST HOC analysis (added after the context hypothesis was refuted on single faults).

    Two-fault programs, scored with the folds trained on single-fault mutants.
    With two faults a faulty statement need not be executed by every failing
    test, which is the situation the coverage context was designed for.
    """
    methods = ("ochiai", "metallaxis", "hybrid_avg", "lr_fusion", "pcg_size", "pcg_fused", "pcg_fused_nocontext")
    keys = ("first_top1", "first_reciprocal_rank", "all_top3", "all_top5", "mean_rank")
    rows = []
    context_of_faults = {"all": 0, "part": 0, "none": 0}
    for case in (c for c in two_fault_cases if c.detected):
        scores = score_case(case, evidence[case.case_id], d1["trained"][case.program_name])
        fault_indices = np.flatnonzero(case.faulty_mask).tolist()
        for i in fault_indices:
            context_of_faults[("none", "part", "all")[int(evidence[case.case_id].contexts[i])]] += 1
        row = {"case_id": case.case_id, "program": case.program_name}
        for method in methods:
            for key, value in metrics.multi_fault_metrics(scores[method], fault_indices).items():
                row[f"{method}.{key}"] = value
        rows.append(row)
    return {"n": len(rows), "context_of_faulty_statements": context_of_faults,
            "overall": ex._aggregate(rows, methods, keys),
            "comparisons": [ex._paired(rows, a, b, key)
                            for a, b in (("pcg_fused", "pcg_fused_nocontext"), ("pcg_fused", "lr_fusion"),
                                         ("pcg_fused", "pcg_size"))
                            for key in ("first_top1", "all_top3", "mean_rank")]}


def symptoms(cases: Sequence[ex.Case]) -> dict:
    """Which detected faults show a symptom a compiler, type checker or analyser could see?"""
    detected = [c for c in cases if c.detected]
    type_like = {"raise:TypeError", "raise:NameError", "raise:UnboundLocalError", "raise:AttributeError"}
    counts = {"detected_faults": len(detected), "compile_error": 0, "any_failing_test_raises_type_or_name_error": 0,
              "any_failing_test_raises_other_exception": 0, "any_failing_test_does_not_terminate": 0,
              "only_wrong_return_values": 0, "analyser_flags_some_line": 0, "analyser_flags_the_faulty_line": 0}
    for case in detected:
        failing = [t.signature for t, f in zip(case.run.tests, case.spectrum.failed) if f]
        kinds = set()
        for signature in failing:
            if signature in type_like:
                kinds.add("type")
            elif signature.startswith("raise:"):
                kinds.add("exception")
            elif signature == "step_limit":
                kinds.add("loop")
            else:
                kinds.add("value")
        counts["any_failing_test_raises_type_or_name_error"] += "type" in kinds
        counts["any_failing_test_raises_other_exception"] += "exception" in kinds
        counts["any_failing_test_does_not_terminate"] += "loop" in kinds
        counts["only_wrong_return_values"] += kinds == {"value"}
        counts["analyser_flags_some_line"] += bool(case.flags.any())
        counts["analyser_flags_the_faulty_line"] += bool((case.flags & case.faulty_mask).any())
    return counts


# ----------------------------------------------------------------------------
# D2 and D3: QuixBugs
# ----------------------------------------------------------------------------

def _external_case(name: str, case_id: str, program: Program, tests, expected, run, truth: ex.GroundTruth) -> ex.Case:
    spectrum = build_spectrum(program, run, list(expected))
    scopes = {"coverage": compute_scopes(spectrum, analyze_dependence(program), "coverage")}
    return ex.Case(name, case_id, program, tuple(tests), list(expected), run, spectrum, scopes, [],
                   np.zeros(len(program.statements), dtype=bool), truth)


def build_external_cases(programs: Sequence[ExternalProgram], seed: int = config.SEED):
    """D2 (the human-written bugs) and D3 (sampled mutants of the correct programs)."""
    d2, d3, excluded = [], [], []
    limits = dict(step_limit=config.EXTERNAL_STEP_LIMIT, timeout=config.EXTERNAL_TIMEOUT_S)
    for index, prog in enumerate(programs):
        (run,) = run_sources([prog.buggy.source], prog.name, prog.tests, **limits)
        if run is None or run.compile_error is not None:
            excluded.append({"case_id": f"quixbugs:{prog.name}", "reason": "runner limit or crash"})
        else:
            truth = ex.GroundTruth(prog.fault_lines, ("human",), (prog.fault_kind,), ("QuixBugs bug",))
            d2.append(_external_case(prog.name, f"quixbugs:{prog.name}", prog.buggy, prog.tests, prog.expected, run, truth))
        mutants = generate_mutants(prog.correct)
        rng = np.random.default_rng([seed, 1000 + index])
        chosen = [mutants[int(i)] for i in rng.permutation(len(mutants))[: config.EXTERNAL_MUTANTS_PER_PROGRAM]]
        runs = run_sources([m.source for m in chosen], prog.name, prog.tests, **limits)
        for mutant, mutant_run in zip(chosen, runs):
            case_id = f"quixbugs-mutant:{prog.name}:{mutant.mutant_id}"
            if mutant_run is None or mutant_run.compile_error is not None or len(mutant_run.tests) != len(prog.tests):
                excluded.append({"case_id": case_id, "reason": "runner limit or crash"})
                continue
            truth = ex.GroundTruth((mutant.line,), (mutant.operator,), (mutant.category,), (mutant.description,))
            d3.append(_external_case(prog.name, case_id, Program.from_source(mutant.source, prog.name),
                                     prog.tests, prog.expected, mutant_run, truth))
    ex.attach_static_evidence(d2 + d3)
    return d2, d3, excluded


def run_external(cases: Sequence[ex.Case], evidence: dict, trained_for: Callable[[ex.Case], Trained],
                 recalibration: Optional[Recalibration]) -> dict:
    """Score external cases with parameters chosen by ``trained_for`` (never fitted on the case itself)."""
    rows = []
    prob = {m: [] for m in PROB_METHODS}
    labels, sizes, programs = [], [], []
    for case in (c for c in cases if c.detected):
        scores = score_case(case, evidence[case.case_id], trained_for(case))
        rows.append(case_row(case, scores, evidence[case.case_id]))
        for m in PROB_METHODS:
            prob[m].extend(scores[m].tolist())
        labels.extend(case.faulty_mask.astype(int).tolist())
        n = len(case.program.statements)
        sizes.extend([n] * n)
        programs.extend([case.program_name] * n)
    if recalibration is not None:
        prob["pcg_fused_recal"] = recalibration.apply(np.array(prob["pcg_fused"])).tolist()
    quality = probabilistic_quality(prob, labels, sizes, programs)
    return {"rows": rows, "overall": aggregate(rows), "comparisons": comparisons(rows),
            "probabilistic": quality,
            "paired_brier": paired_brier(prob, labels, programs, (("pcg_fused", "lr_fusion"), ("pcg_fused", "pcg_size"),
                                                                    ("pcg_fused", "pcg_fused_nocontext"))),
            "selective": selective(rows)}


# ----------------------------------------------------------------------------
# Orchestration
# ----------------------------------------------------------------------------

RESEARCH_DIR = config.RESULTS_DIR / "research"


def run_research(out_path: Path = RESEARCH_DIR, quixbugs_dir: Optional[Path] = None,
                 log: Callable[[str], None] = print) -> Path:
    """Run every experiment of the research phase and write ``results/research``."""
    from . import research_report

    start = time.time()

    def step(message: str) -> None:
        log(f"[{time.time() - start:6.1f}s] {message}")

    out = ex.OutputDir(out_path)
    step("D1: building cases (tests, coverage, pylint)")
    references = ex.load_references()
    names = list(references)
    cases, excluded = ex.build_first_order_cases(references)
    detected = [c for c in cases if c.detected]

    step("D1: mutation analysis of every faulty program")
    evidence, stress_evidence, cost = collect_evidence(
        detected, config.STEP_LIMIT, config.SUBPROCESS_TIMEOUT_S,
        {name: ref.program.source for name, ref in references.items()}, log)
    for case in cases:  # undetected mutants: nothing fails, the evidence variable is undefined
        if case.case_id not in evidence:
            n = len(case.program.statements)
            evidence[case.case_id] = MutationEvidence(np.zeros(n, dtype=int), np.zeros(n, dtype=int),
                                                      np.zeros(n), np.zeros(n), 0, 0)
            stress_evidence[case.case_id] = evidence[case.case_id]
    out.write_jsonl("d1_mutation_evidence.jsonl", [
        {"case_id": c.case_id, "statements": list(c.program.statements),
         "levels": evidence[c.case_id].levels.tolist(), "contexts": evidence[c.case_id].contexts.tolist(),
         "metallaxis": evidence[c.case_id].metallaxis.tolist(), "muse": evidence[c.case_id].muse.tolist(),
         "variants": evidence[c.case_id].n_variants, "usable_variants": evidence[c.case_id].n_usable}
        for c in detected])

    step("D1: leave-one-program-out, all methods")
    d1 = run_d1(cases, evidence, names, log)
    out.write_csv("d1_per_case.csv", d1["rows"])
    out.write_json("d1_ranking.json", {k: d1[k] for k in ("overall", "comparisons", "by_category")})
    pooled = train(cases, detected, evidence, f"pooled over all D1 programs ({len(cases)} valid, {len(detected)} detected mutants)")
    _, fusion_counts = estimate_fusion_params([FusionCase(evidence[c.case_id], c.faulty_mask) for c in detected], "pooled")
    out.write_json("fusion_params_pooled.json", {
        "model_params": pooled.params.to_dict(), "fusion_params": pooled.fusion.to_dict(), "counts": fusion_counts,
        "lr_spectrum": dict(zip(SPECTRUM_FEATURES, pooled.lr_spectrum.weights.tolist()), intercept=pooled.lr_spectrum.intercept),
        "lr_fusion": dict(zip(FUSION_FEATURES, pooled.lr_fusion.weights.tolist()), intercept=pooled.lr_fusion.intercept),
    })

    # Per-program tables that exclude the program's own mutants (used by the demonstration).
    out.write_json("fusion_params_lopo.json", {name: fold.fusion.to_dict() for name, fold in d1["trained"].items()})

    step("D1: nested recalibration of the fused model")
    recal, transfer_map = run_recalibration(cases, evidence, names, d1, log)
    prob = dict(d1["prob"])
    prob["pcg_fused_recal"] = recal["recalibrated"]
    out.write_json("d1_probabilistic.json", {
        "quality": probabilistic_quality(prob, d1["labels"], d1["sizes"], d1["programs"]),
        "paired_brier": paired_brier(prob, d1["labels"], d1["programs"], (
            ("pcg_fused", "lr_fusion"), ("pcg_fused", "pcg_size"), ("pcg_fused", "pcg_fused_nocontext"),
            ("pcg_fused_recal", "pcg_fused"), ("pcg_size", "pcg"))),
        "recalibration_maps": recal["maps"], "transfer_map": recal["transfer_map"]})
    out.write_json("d1_selective.json", selective(d1["rows"]))

    step("D1: stress test without the reference-restoring variant")
    out.write_json("d1_stress_no_inverse.json", run_stress(cases, stress_evidence, names))

    step("D1: two-fault programs (post hoc analysis)")
    two_cases, _ = ex.build_two_fault_cases(references)
    two_detected = [c for c in two_cases if c.detected]
    two_evidence, _, two_cost = collect_evidence(two_detected, config.STEP_LIMIT, config.SUBPROCESS_TIMEOUT_S, None, log)
    out.write_json("d1_two_fault_post_hoc.json", run_two_fault(two_cases, two_evidence, d1))

    step("D1: constant versus size-aware prior; fault symptoms")
    out.write_json("d1_size_prior.json", run_size_prior(cases, d1))
    symptom_report = {"D1": symptoms(cases)}

    step("QuixBugs: loading, oracle check, building D2 and D3")
    programs, loading_report = load_quixbugs(quixbugs_dir)
    d2, d3, external_excluded = build_external_cases(programs)
    out.write_json("external_loading_report.json", {
        "programs_with_json_tests": len(loading_report), "programs_used": len(programs),
        "d2_cases": len(d2), "d2_detected": sum(c.detected for c in d2),
        "d3_cases": len(d3), "d3_detected": sum(c.detected for c in d3),
        "excluded_runs": external_excluded, "per_program": loading_report})
    out.write_jsonl("external_cases.jsonl", [ex.case_record(c) for c in d2 + d3])

    step("QuixBugs: mutation analysis of D2 and D3")
    external_detected = [c for c in d2 + d3 if c.detected]
    external_evidence, _, external_cost = collect_evidence(
        external_detected, config.EXTERNAL_STEP_LIMIT, config.EXTERNAL_TIMEOUT_S, None, log)

    step("D2 and D3 with parameters transferred from D1")
    d2_transfer = run_external(d2, external_evidence, lambda case: pooled, transfer_map)
    d3_transfer = run_external(d3, external_evidence, lambda case: pooled, transfer_map)

    step("D2 with parameters from mutants of the other QuixBugs programs (in-suite)")
    d3_detected = [c for c in d3 if c.detected]
    in_suite = {}
    for prog in programs:
        others_valid = [c for c in d3 if c.program_name != prog.name]
        others_detected = [c for c in d3_detected if c.program_name != prog.name]
        for c in others_valid:
            if c.case_id not in external_evidence:
                n = len(c.program.statements)
                external_evidence[c.case_id] = MutationEvidence(np.zeros(n, dtype=int), np.zeros(n, dtype=int),
                                                                np.zeros(n), np.zeros(n), 0, 0)
        in_suite[prog.name] = train(others_valid, others_detected, external_evidence,
                                    f"mutants of the other QuixBugs programs, {prog.name} held out")
    d2_in_suite = run_external(d2, external_evidence, lambda case: in_suite[case.program_name], None)

    for label, result in (("d2_transfer", d2_transfer), ("d3_transfer", d3_transfer), ("d2_in_suite", d2_in_suite)):
        out.write_csv(f"{label}_per_case.csv", result["rows"])
        out.write_json(f"{label}_summary.json", {k: result[k] for k in ("overall", "comparisons", "probabilistic",
                                                                         "paired_brier", "selective")})
    symptom_report["D2"] = symptoms(d2)
    out.write_json("symptoms.json", symptom_report)
    out.write_json("cost.json", {"D1": cost, "D1_two_fault": two_cost, "external": external_cost,
                                 "D1_first_order_excluded": excluded})

    step("figures and SUMMARY.md")
    research_report.write_figures(out.path)
    (out.path / "SUMMARY.md").write_text(research_report.build_summary(out.path), encoding="utf-8")
    out.finish({"counts": {"d1_valid": len(cases), "d1_detected": len(detected), "quixbugs_programs": len(programs),
                           "d2_detected": sum(c.detected for c in d2), "d3_valid": len(d3),
                           "d3_detected": len(d3_detected)}})
    step(f"done: {out.path}")
    return out.path
