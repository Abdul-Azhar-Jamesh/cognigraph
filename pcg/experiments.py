"""The scripted experiments. Every number in the documentation comes from here.

Experiments (all deterministic given ``config.SEED``):

1. ``first_order``  single-fault localisation, leave-one-program-out (LOPO).
2. ``calibration``  probabilistic quality of the posteriors.
3. ``sensitivity``  how results move when parameters are set by hand.
4. ``two_fault``    programs with two injected faults.
5. ``simulated_llm`` effect of an LLM-confidence signal of controlled quality.
   The signal is SIMULATED and is labelled so in every output.
6. ``repair``       targeted repair search guided by different rankings.

Ground truth (the injected fault line) lives in :class:`GroundTruth` objects.
They are read only by the estimation step for *other* programs and by the
metric code; the inference call for a case never receives its own truth.
"""

from __future__ import annotations

import csv
import hashlib
import json
import platform
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Sequence

import numpy as np

from . import baselines, config, metrics
from .analysis import analyze_run, compute_scopes
from .benchmark_programs import PROGRAMS, BenchmarkProgram
from .config import ModelParams
from .dependence import analyze_dependence
from .estimation import LabelledCase, bin_index, estimate_binned_likelihood, estimate_params
from .execution import SourceRun, Spectrum, build_spectrum, oracle_signatures, run_sources
from .model import FaultModel, apply_likelihood_ratio, infer
from .mutation import Mutant, generate_mutants
from .program import Program
from .repair import candidate_patches, validate_patch
from .static_analysis import Finding, flagged_lines, run_pylint

PCG_VARIANTS = {
    # name: (scope mode, use static evidence, fixed exposure rate)
    "pcg": ("coverage", False, False),
    "pcg_fixed_theta": ("coverage", False, True),
    "pcg_slice": ("slice", False, False),
    "pcg_static": ("coverage", True, False),
}
BASELINE_NAMES = tuple(baselines.BASELINES)
ALL_METHODS = BASELINE_NAMES + tuple(PCG_VARIANTS)


@dataclass(frozen=True)
class GroundTruth:
    """Evaluation-only labels of a faulty program."""

    fault_lines: tuple[int, ...]
    operators: tuple[str, ...]
    categories: tuple[str, ...]
    descriptions: tuple[str, ...]


@dataclass
class Case:
    """A faulty program version with its collected evidence and its labels."""

    program_name: str
    case_id: str
    program: Program
    tests: tuple[tuple, ...]
    expected: list[str]
    run: SourceRun
    spectrum: Spectrum
    scopes: dict[str, np.ndarray]
    findings: list[Finding]
    flags: np.ndarray
    truth: GroundTruth

    @property
    def detected(self) -> bool:
        return self.spectrum.n_failed > 0

    @property
    def faulty_mask(self) -> np.ndarray:
        return np.array([line in self.truth.fault_lines for line in self.program.statements], dtype=bool)


# ----------------------------------------------------------------------------
# Building cases
# ----------------------------------------------------------------------------

def _make_cases(
    name: str,
    tests: tuple[tuple, ...],
    expected: list[str],
    func_name: str,
    items: Sequence[tuple[str, str, GroundTruth]],
) -> tuple[list[Case], list[dict]]:
    """Execute sources and assemble cases. ``items`` are (case_id, source, truth)."""
    runs = run_sources([source for _, source, _ in items], func_name, tests)
    cases, excluded = [], []
    for (case_id, source, truth), run in zip(items, runs):
        if run is None or run.compile_error is not None or len(run.tests) != len(tests):
            excluded.append({"case_id": case_id, "reason": "runner_timeout_or_crash" if run is None else "did_not_compile"})
            continue
        program = Program.from_source(source, func_name)
        spectrum = build_spectrum(program, run, expected)
        dependence = analyze_dependence(program)
        scopes = {mode: compute_scopes(spectrum, dependence, mode) for mode in ("coverage", "slice")}
        cases.append(Case(name, case_id, program, tests, expected, run, spectrum, scopes, [], np.zeros(len(program.statements), dtype=bool), truth))
    return cases, excluded


def attach_static_evidence(cases: Sequence[Case]) -> None:
    """Run pylint once over all case sources and store findings and flags."""
    all_findings = run_pylint([case.program.source for case in cases])
    for case, findings in zip(cases, all_findings):
        case.findings = findings
        flagged = flagged_lines(findings)
        case.flags = np.array([line in flagged for line in case.program.statements], dtype=bool)


@dataclass
class Reference:
    """A fault-free benchmark program with its oracle."""

    bench: BenchmarkProgram
    program: Program
    expected: list[str]
    mutants: list[Mutant]


def load_references(programs: Sequence[BenchmarkProgram] = PROGRAMS) -> dict[str, Reference]:
    out = {}
    for bench in programs:
        program = Program.from_source(bench.source, bench.name)
        expected = oracle_signatures(program.source, program.func_name, bench.tests)
        out[bench.name] = Reference(bench, program, expected, generate_mutants(program))
    return out


def build_first_order_cases(references: dict[str, Reference]) -> tuple[list[Case], list[dict]]:
    """One case per single-edit mutant of every benchmark program."""
    cases: list[Case] = []
    excluded: list[dict] = []
    for name, ref in references.items():
        items = [
            (f"{name}:{m.mutant_id}", m.source, GroundTruth((m.line,), (m.operator,), (m.category,), (m.description,)))
            for m in ref.mutants
        ]
        new_cases, new_excluded = _make_cases(name, ref.bench.tests, ref.expected, ref.program.func_name, items)
        cases.extend(new_cases)
        excluded.extend(new_excluded)
    attach_static_evidence(cases)
    return cases, excluded


def build_two_fault_cases(references: dict[str, Reference], seed: int = config.SEED) -> tuple[list[Case], list[dict]]:
    """Sample programs with two faults on two different lines.

    For each program, first-order mutants are visited in a seeded random order;
    each is mutated once more on a different line (seeded choice). Sampling
    stops at ``config.TWO_FAULT_PER_PROGRAM`` distinct programs.
    """
    cases: list[Case] = []
    excluded: list[dict] = []
    for index, (name, ref) in enumerate(references.items()):
        rng = np.random.default_rng([seed, index])
        items, seen = [], set()
        for first_index in rng.permutation(len(ref.mutants)):
            if len(items) >= config.TWO_FAULT_PER_PROGRAM:
                break
            first = ref.mutants[int(first_index)]
            seconds = [m for m in generate_mutants(Program.from_source(first.source, name)) if m.line != first.line]
            if not seconds:
                continue
            second = seconds[int(rng.integers(len(seconds)))]
            reference_lines = ref.program.source.splitlines()
            changed = tuple(i for i, (a, b) in enumerate(zip(reference_lines, second.source.splitlines()), 1) if a != b)
            if len(changed) != 2 or second.source in seen:
                continue
            seen.add(second.source)
            truth = GroundTruth(changed, (first.operator, second.operator), (first.category, second.category),
                                (first.description, second.description))
            items.append((f"{name}:{first.mutant_id}+{second.mutant_id}", second.source, truth))
        new_cases, new_excluded = _make_cases(name, ref.bench.tests, ref.expected, name, items)
        cases.extend(new_cases)
        excluded.extend(new_excluded)
    return cases, excluded


# ----------------------------------------------------------------------------
# Parameter estimation (leave-one-program-out)
# ----------------------------------------------------------------------------

def lopo_params(cases: Sequence[Case], program_names: Sequence[str]) -> tuple[dict, dict]:
    """For every program, parameters estimated from all *other* programs.

    Returns ``params[program][mode]`` and the matching raw counts.
    """
    params: dict[str, dict[str, ModelParams]] = {}
    counts: dict[str, dict[str, dict]] = {}
    for held_out in program_names:
        params[held_out], counts[held_out] = {}, {}
        for mode in ("coverage", "slice"):
            training = [
                LabelledCase(c.scopes[mode], c.spectrum.failed, c.faulty_mask, c.flags)
                for c in cases if c.program_name != held_out
            ]
            p, n = estimate_params(training, f"LOPO estimate, {held_out} held out, scope={mode}")
            params[held_out][mode], counts[held_out][mode] = p, n
    return params, counts


def pooled_params(cases: Sequence[Case], mode: str = "coverage") -> ModelParams:
    """Parameters from every case (for analysing code outside the benchmark)."""
    training = [LabelledCase(c.scopes[mode], c.spectrum.failed, c.faulty_mask, c.flags) for c in cases]
    return estimate_params(training, f"pooled estimate from all {len(training)} benchmark mutants, scope={mode}")[0]


# ----------------------------------------------------------------------------
# Scoring
# ----------------------------------------------------------------------------

def pcg_scores(case: Case, params: dict[str, ModelParams], variant: str) -> np.ndarray:
    """Posterior fault probabilities for one case. No ground truth is passed."""
    mode, use_static, fixed_theta = PCG_VARIANTS[variant]
    p = params[mode].with_fixed_theta() if fixed_theta else params[mode]
    result = analyze_run(case.program, case.run, case.expected, p, scope=mode,
                         findings=case.findings, use_static=use_static)
    return result.posterior.marginals


def score_all_methods(case: Case, params: dict[str, ModelParams]) -> dict[str, np.ndarray]:
    scores = {name: fn(case.spectrum.coverage, case.spectrum.failed) for name, fn in baselines.BASELINES.items()}
    for variant in PCG_VARIANTS:
        scores[variant] = pcg_scores(case, params, variant)
    return scores


# ----------------------------------------------------------------------------
# Experiment 1 + 2: first-order localisation and calibration
# ----------------------------------------------------------------------------

def _aggregate(rows: Sequence[dict], methods: Sequence[str], keys: Sequence[str]) -> dict:
    clusters = [row["program"] for row in rows]
    return {
        method: {key: metrics.summarize(np.array([row[f"{method}.{key}"] for row in rows]), clusters) for key in keys}
        for method in methods
    }


def _paired(rows: Sequence[dict], a: str, b: str, key: str) -> dict:
    """Paired comparison ``a - b`` on one metric, with the program as the unit."""
    diffs = np.array([row[f"{a}.{key}"] - row[f"{b}.{key}"] for row in rows])
    clusters = [row["program"] for row in rows]
    sums, counts, names = metrics.cluster_means(diffs, clusters)
    per_program = sums / counts
    low, high = metrics.cluster_bootstrap_ci(diffs, clusters)
    return {
        "comparison": f"{a} - {b}",
        "metric": key,
        "mean_difference": float(diffs.mean()),
        "ci_low": low,
        "ci_high": high,
        "programs_a_better": int((per_program > 1e-12).sum()),
        "programs_b_better": int((per_program < -1e-12).sum()),
        "programs_equal": int((np.abs(per_program) <= 1e-12).sum()),
        "cases_a_better": int((diffs > 1e-12).sum()),
        "cases_b_better": int((diffs < -1e-12).sum()),
        "sign_flip_p_value": metrics.paired_sign_flip_test(per_program),
    }


RANK_KEYS = ("top1", "top3", "reciprocal_rank", "exam")


def run_first_order(cases: Sequence[Case], params: dict) -> dict:
    """Localisation metrics on detected single-fault mutants, plus calibration."""
    rows: list[dict] = []
    calibration_data = {variant: {"p": [], "y": [], "detected": []} for variant in PCG_VARIANTS}
    base_rate = {"p": [], "y": []}
    for case in cases:
        scores = score_all_methods(case, params[case.program_name])
        labels = case.faulty_mask
        for variant in PCG_VARIANTS:
            calibration_data[variant]["p"].extend(scores[variant].tolist())
            calibration_data[variant]["y"].extend(labels.astype(int).tolist())
            calibration_data[variant]["detected"].extend([case.detected] * labels.size)
        base_rate["p"].extend([params[case.program_name]["coverage"].prior_fault] * labels.size)
        base_rate["y"].extend(labels.astype(int).tolist())
        if not case.detected:
            continue
        fault_index = int(np.flatnonzero(labels)[0])
        row = {
            "case_id": case.case_id,
            "program": case.program_name,
            "category": case.truth.categories[0],
            "operator": case.truth.operators[0],
            "fault_line": case.truth.fault_lines[0],
            "n_statements": len(case.program.statements),
            "n_tests": case.spectrum.n_tests,
            "n_failed": case.spectrum.n_failed,
            "fault_in_slice_scope_of_all_failing": bool(case.scopes["slice"][case.spectrum.failed][:, fault_index].all()),
        }
        for method in ALL_METHODS:
            m = metrics.rank_metrics(scores[method], fault_index)
            row.update({f"{method}.top1": m.top1, f"{method}.top3": m.top3,
                        f"{method}.reciprocal_rank": m.reciprocal_rank, f"{method}.exam": m.exam,
                        f"{method}.tie_size": m.tie_size})
        row["pcg.posterior_of_fault"] = float(scores["pcg"][fault_index])
        rows.append(row)

    overall = _aggregate(rows, ALL_METHODS, RANK_KEYS)
    by_category = {}
    for category in sorted({row["category"] for row in rows}):
        subset = [row for row in rows if row["category"] == category]
        by_category[category] = {
            "n": len(subset),
            **{method: {key: float(np.mean([r[f"{method}.{key}"] for r in subset])) for key in ("top1", "reciprocal_rank")}
               for method in ("ochiai", "pcg", "pcg_fixed_theta", "pcg_slice", "pcg_static")},
        }
    comparisons = [
        _paired(rows, a, b, key)
        for a, b in (("pcg", "ochiai"), ("pcg", "tarantula"), ("pcg", "pcg_fixed_theta"),
                     ("pcg_slice", "pcg"), ("pcg_static", "pcg"))
        for key in ("top1", "reciprocal_rank", "exam")
    ]

    calibration = {}
    for variant, data in calibration_data.items():
        p, y, det = np.array(data["p"]), np.array(data["y"]), np.array(data["detected"])
        calibration[variant] = {
            "all_valid_mutants": _probabilistic_quality(p, y),
            "detected_mutants_only": _probabilistic_quality(p[det], y[det]),
        }
    calibration["base_rate_reference"] = {
        "all_valid_mutants": _probabilistic_quality(np.array(base_rate["p"]), np.array(base_rate["y"])),
    }
    return {"rows": rows, "overall": overall, "by_category": by_category, "comparisons": comparisons,
            "calibration": calibration}


def _probabilistic_quality(p: np.ndarray, y: np.ndarray) -> dict:
    return {
        "n_statements": int(p.size),
        "n_faulty": int(y.sum()),
        "brier": metrics.brier_score(p, y),
        "log_loss": metrics.log_loss(p, y),
        "ece": metrics.expected_calibration_error(p, y),
        "reliability": metrics.reliability_table(p, y),
    }


def run_fault_free(references: dict[str, Reference], params: dict) -> list[dict]:
    """Posterior P(no fault) for the fault-free references (all tests pass)."""
    rows = []
    for name, ref in references.items():
        (run,) = run_sources([ref.program.source], name, ref.bench.tests)
        result = analyze_run(ref.program, run, ref.expected, params[name]["coverage"])
        n = len(ref.program.statements)
        rows.append({
            "program": name,
            "n_statements": n,
            "tests_failed": result.spectrum.n_failed,
            "prior_p_no_fault": float((1.0 - params[name]["coverage"].prior_fault) ** n),
            "posterior_p_no_fault": result.posterior.p_no_fault,
            "max_statement_posterior": float(result.posterior.marginals.max()),
        })
    return rows


# ----------------------------------------------------------------------------
# Experiment 3: sensitivity to hand-set parameters
# ----------------------------------------------------------------------------

def _direct_posterior(case: Case, prior: np.ndarray, theta, leak: float, theta_weights=None,
                      mode: str = "coverage") -> np.ndarray:
    """Same model as the graph route, built straight from the scope matrix."""
    return infer(FaultModel(prior, case.scopes[mode], case.spectrum.failed, theta, leak, theta_weights)).marginals


def run_sensitivity(cases: Sequence[Case], reference: ModelParams) -> list[dict]:
    """Fix the parameters by hand over a grid and re-evaluate everything."""
    grid = [(theta, reference.leak, prior) for theta in config.SENSITIVITY_THETA for prior in config.SENSITIVITY_PRIOR]
    grid += [(reference.theta, leak, reference.prior_fault) for leak in config.SENSITIVITY_LEAK]
    rows = []
    for theta, leak, prior in grid:
        top1, rr, p_all, y_all = [], [], [], []
        for case in cases:
            marginals = _direct_posterior(case, np.full(len(case.program.statements), prior), theta, leak)
            p_all.extend(marginals.tolist())
            y_all.extend(case.faulty_mask.astype(int).tolist())
            if case.detected:
                m = metrics.rank_metrics(marginals, int(np.flatnonzero(case.faulty_mask)[0]))
                top1.append(m.top1)
                rr.append(m.reciprocal_rank)
        rows.append({
            "theta": theta, "leak": leak, "prior_fault": prior,
            "top1": float(np.mean(top1)), "mrr": float(np.mean(rr)),
            "brier": metrics.brier_score(np.array(p_all), np.array(y_all)),
            "ece": metrics.expected_calibration_error(np.array(p_all), np.array(y_all)),
        })
    return rows


# ----------------------------------------------------------------------------
# Experiment 4: two faults
# ----------------------------------------------------------------------------

def run_two_fault(cases: Sequence[Case], params: dict) -> dict:
    """Localisation when two statements are faulty (parameters from first-order LOPO)."""
    methods = BASELINE_NAMES + ("pcg",)
    rows = []
    for case in cases:
        if not case.detected:
            continue
        scores = {name: fn(case.spectrum.coverage, case.spectrum.failed) for name, fn in baselines.BASELINES.items()}
        scores["pcg"] = pcg_scores(case, params[case.program_name], "pcg")
        fault_indices = np.flatnonzero(case.faulty_mask).tolist()
        row = {"case_id": case.case_id, "program": case.program_name, "n_failed": case.spectrum.n_failed}
        for method in methods:
            for key, value in metrics.multi_fault_metrics(scores[method], fault_indices).items():
                row[f"{method}.{key}"] = value
        rows.append(row)
    keys = ("first_top1", "first_top3", "first_reciprocal_rank", "all_top3", "all_top5", "mean_rank")
    return {
        "rows": rows,
        "overall": _aggregate(rows, methods, keys),
        "comparisons": [_paired(rows, "pcg", "ochiai", key) for key in ("first_top1", "first_reciprocal_rank", "all_top3", "mean_rank")],
    }


# ----------------------------------------------------------------------------
# Experiment 5: SIMULATED LLM confidence
# ----------------------------------------------------------------------------

#: Beta parameters of the simulated "confidence that this line is correct".
#: Fault-free lines always draw from Beta(8, 2). Only the distribution for
#: faulty lines changes, which sets how informative the signal is.
SIMULATED_LLM_LEVELS = {
    "uninformative": (8.0, 2.0),
    "weak": (6.0, 4.0),
    "strong": (3.0, 7.0),
}
SIMULATED_LLM_CLEAN = (8.0, 2.0)
SIMULATED_LLM_BINS = 5
SIMULATED_LLM_REPLICATES = 10


def run_simulated_llm(cases: Sequence[Case], params: dict, seed: int = config.SEED) -> dict:
    """How would an LLM-confidence signal of known quality change the results?

    THIS EXPERIMENT USES SYNTHETIC CONFIDENCE VALUES drawn from Beta
    distributions that depend on the ground truth. It measures the model's
    ability to exploit such a signal; it says nothing about any real LLM.
    The signal's likelihoods are learned on the other programs (LOPO), exactly
    as they would be for real confidence data.
    """
    summary = {}
    programs = sorted({case.program_name for case in cases})
    replicates = range(SIMULATED_LLM_REPLICATES)
    labels_all = np.concatenate([case.faulty_mask for case in cases]).astype(int)

    # The posterior without the signal does not depend on the simulation.
    plain = {}
    for case in cases:
        p = params[case.program_name]["coverage"]
        grid, weights = p.exposure_prior()
        plain[case.case_id] = _direct_posterior(case, np.full(len(case.program.statements), p.prior_fault), grid, p.leak, weights)

    for level_index, (level, (a_fault, b_fault)) in enumerate(SIMULATED_LLM_LEVELS.items()):
        # 1. Draw the synthetic confidences and learn their likelihoods, per replicate.
        confidence, fold_likelihood = [], []
        for replicate in replicates:
            rng = np.random.default_rng([seed, level_index, replicate])
            drawn = {}
            for case in cases:  # fixed iteration order keeps the draws reproducible
                mask = case.faulty_mask
                clean = rng.beta(*SIMULATED_LLM_CLEAN, size=mask.size)
                faulty = rng.beta(a_fault, b_fault, size=mask.size)
                drawn[case.case_id] = np.where(mask, faulty, clean)
            folds = {}
            for held_out in programs:
                train = [c for c in cases if c.program_name != held_out]
                values = np.concatenate([drawn[c.case_id] for c in train])
                labels = np.concatenate([c.faulty_mask for c in train])
                folds[held_out] = estimate_binned_likelihood(values, labels, SIMULATED_LLM_BINS)
            confidence.append(drawn)
            fold_likelihood.append(folds)

        # 2. Inference. Cases are the outer loop so each case's likelihood table is reused.
        acc = [{name: {"top1": [], "mrr": []} for name in ("pcg", "llm_only", "pcg_plus_llm")} for _ in replicates]
        fused_all = [[] for _ in replicates]
        for case in cases:
            p = params[case.program_name]["coverage"]
            grid, weights = p.exposure_prior()
            base = np.full(len(case.program.statements), p.prior_fault)
            fault_index = int(np.flatnonzero(case.faulty_mask)[0])
            for replicate in replicates:
                conf = confidence[replicate][case.case_id]
                p_fault, p_clean = fold_likelihood[replicate][case.program_name]
                bins = bin_index(conf, SIMULATED_LLM_BINS)
                fused = _direct_posterior(case, apply_likelihood_ratio(base, p_fault[bins] / p_clean[bins]), grid, p.leak, weights)
                fused_all[replicate].extend(fused.tolist())
                if case.detected:
                    for name, scores in (("pcg", plain[case.case_id]), ("llm_only", 1.0 - conf), ("pcg_plus_llm", fused)):
                        m = metrics.rank_metrics(scores, fault_index)
                        acc[replicate][name]["top1"].append(m.top1)
                        acc[replicate][name]["mrr"].append(m.reciprocal_rank)

        def spread(values: list[float]) -> dict:
            return {"mean": float(np.mean(values)), "sd": float(np.std(values, ddof=1))}

        plain_brier = metrics.brier_score(np.concatenate([plain[c.case_id] for c in cases]), labels_all)
        summary[level] = {
            "SIMULATED": True,
            "faulty_line_confidence_distribution": f"Beta({a_fault:g}, {b_fault:g})",
            "fault_free_line_confidence_distribution": "Beta(%g, %g)" % SIMULATED_LLM_CLEAN,
            "replicates": SIMULATED_LLM_REPLICATES,
            **{name: {key: spread([float(np.mean(acc[r][name][key])) for r in replicates]) for key in ("top1", "mrr")}
               for name in ("pcg", "llm_only", "pcg_plus_llm")},
            "brier": {
                "pcg": {"mean": plain_brier, "sd": 0.0},
                "pcg_plus_llm": spread([metrics.brier_score(np.array(fused_all[r]), labels_all) for r in replicates]),
            },
        }
    return summary


# ----------------------------------------------------------------------------
# Experiment 6: targeted repair
# ----------------------------------------------------------------------------

def run_repair(cases: Sequence[Case], references: dict[str, Reference], params: dict) -> dict:
    """Search-based repair restricted to the most suspicious statements.

    Every candidate patch of every detected mutant is validated once (compile +
    full test suite in a child process). Each strategy then walks the
    candidates in its own order and stops at the first one that passes all
    tests; the walk is a replay of real validation results, not a simulation
    of outcomes.

    Strategies:
      * ``pcg_top3`` / ``ochiai_top3``: only the three most suspicious
        statements (ties broken by line number) may be edited.
      * ``unguided_all``: every statement, in source order. This is the upper
        bound on what this patch space can fix, at the highest search cost.
    """
    detected = [case for case in cases if case.detected]
    attempts_log, rows = [], []
    # Validate every distinct candidate text once per program. Two faulty
    # versions of a program often share candidates; the verdict for a given
    # text under a given test suite is the same, so it is computed once.
    all_candidates = {case.case_id: candidate_patches(case.program) for case in detected}
    verdict_of: dict[tuple[str, str], dict] = {}
    for name in sorted({case.program_name for case in detected}):
        own = [case for case in detected if case.program_name == name]
        texts = sorted({c.source for case in own for c in all_candidates[case.case_id]})
        for text, verdict in zip(texts, validate_patch(texts, name, own[0].tests, own[0].expected)):
            verdict_of[(name, text)] = verdict
    for case in detected:
        candidates = all_candidates[case.case_id]
        verdicts = [verdict_of[(case.program_name, c.source)] for c in candidates]
        by_line: dict[int, list[int]] = {}
        for index, candidate in enumerate(candidates):
            by_line.setdefault(candidate.line, []).append(index)
        reference_source = references[case.program_name].program.source
        scores = {
            "pcg": pcg_scores(case, params[case.program_name], "pcg"),
            "ochiai": baselines.ochiai(case.spectrum.coverage, case.spectrum.failed),
        }
        statements = case.program.statements

        def top_lines(values: np.ndarray, k: int) -> list[int]:
            rounded = np.round(values, config.RANK_DECIMALS)
            order = sorted(range(len(statements)), key=lambda i: (-rounded[i], statements[i]))
            return [statements[i] for i in order[:k]]

        strategies = {
            "pcg_top3": top_lines(scores["pcg"], config.REPAIR_TOP_K),
            "ochiai_top3": top_lines(scores["ochiai"], config.REPAIR_TOP_K),
            "unguided_all": list(statements),
        }
        row = {"case_id": case.case_id, "program": case.program_name, "category": case.truth.categories[0],
               "fault_line": case.truth.fault_lines[0], "n_candidates_total": len(candidates)}
        for strategy, lines in strategies.items():
            tried, accepted = 0, None
            for line in lines:
                for index in by_line.get(line, []):
                    tried += 1
                    if verdicts[index]["accepted"]:
                        accepted = index
                        break
                if accepted is not None:
                    break
            exact = accepted is not None and candidates[accepted].source == reference_source
            row[f"{strategy}.repaired"] = float(accepted is not None)
            row[f"{strategy}.exact"] = float(exact)
            row[f"{strategy}.candidates_tried"] = tried
            row[f"{strategy}.fault_line_in_region"] = float(case.truth.fault_lines[0] in lines)
            attempts_log.append({
                "case_id": case.case_id, "strategy": strategy, "region_lines": lines,
                "candidates_tried": tried,
                "accepted_patch": candidates[accepted].description if accepted is not None else None,
                "accepted_patch_equals_reference": exact if accepted is not None else None,
                "outcome": "plausible_patch_found" if accepted is not None else "no_patch_in_region",
            })
        row["candidates_passing_all_tests"] = int(sum(v["accepted"] for v in verdicts))
        rows.append(row)
    keys = ("repaired", "exact", "candidates_tried", "fault_line_in_region")
    return {
        "rows": rows,
        "attempts": attempts_log,
        "overall": _aggregate(rows, ("pcg_top3", "ochiai_top3", "unguided_all"), keys),
        "comparisons": [_paired(rows, "pcg_top3", "ochiai_top3", key) for key in ("repaired", "candidates_tried")],
    }


# ----------------------------------------------------------------------------
# Output handling
# ----------------------------------------------------------------------------

class OutputDir:
    """A results directory that cannot be mistaken for complete when it is not.

    The directory is emptied when the run starts and ``MANIFEST.json`` (with a
    SHA-256 of every file) is written only when the run finishes. Readers must
    call :func:`require_complete`; a crashed run therefore leaves no manifest
    and no stale numbers.
    """

    def __init__(self, path: Path) -> None:
        self.path = path
        if path.exists():
            shutil.rmtree(path)
        path.mkdir(parents=True)

    def write_json(self, name: str, data) -> None:
        (self.path / name).write_text(json.dumps(data, indent=2, sort_keys=True, default=_jsonable), encoding="utf-8")

    def write_csv(self, name: str, rows: Sequence[dict]) -> None:
        if not rows:
            (self.path / name).write_text("", encoding="utf-8")
            return
        with open(self.path / name, "w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
            writer.writeheader()
            writer.writerows(rows)

    def write_jsonl(self, name: str, rows: Sequence[dict]) -> None:
        with open(self.path / name, "w", encoding="utf-8") as handle:
            for row in rows:
                handle.write(json.dumps(row, sort_keys=True, default=_jsonable) + "\n")

    def finish(self, extra: Optional[dict] = None) -> None:
        files = {}
        for file in sorted(self.path.rglob("*")):
            if file.is_file() and file.name != "MANIFEST.json":
                # Hash with normalised line endings so the value is the same on every OS.
                data = file.read_bytes()
                if file.suffix in {".json", ".jsonl", ".csv", ".md", ".txt", ".py"}:
                    data = data.replace(b"\r\n", b"\n")
                files[file.relative_to(self.path).as_posix()] = hashlib.sha256(data).hexdigest()
        manifest = {"status": "complete", "environment": environment_info(), "files": files, **(extra or {})}
        (self.path / "MANIFEST.json").write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")


def require_complete(path: Path) -> dict:
    """Return the manifest of a finished run or raise if there is none."""
    manifest = path / "MANIFEST.json"
    if not manifest.exists():
        raise FileNotFoundError(
            f"{path} has no MANIFEST.json: the run that should have produced it did not finish. "
            "Run `python -m pcg benchmark` first."
        )
    return json.loads(manifest.read_text(encoding="utf-8"))


def _jsonable(value):
    if isinstance(value, (np.floating, np.integer)):
        return value.item()
    if isinstance(value, np.bool_):
        return bool(value)
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, (set, frozenset, tuple)):
        return sorted(value) if isinstance(value, (set, frozenset)) else list(value)
    raise TypeError(f"cannot serialise {type(value).__name__}")


def environment_info() -> dict:
    import matplotlib
    import networkx
    import pylint

    return {
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "numpy": np.__version__,
        "networkx": networkx.__version__,
        "matplotlib": matplotlib.__version__,
        "pylint": pylint.__version__,
        "seed": config.SEED,
        "step_limit": config.STEP_LIMIT,
    }


def case_record(case: Case) -> dict:
    """Full provenance of one case: source, transformation, tests, coverage."""
    return {
        "case_id": case.case_id,
        "program": case.program_name,
        "mutated_source": case.program.source,
        "statements": list(case.program.statements),
        "tests": [list(t) for t in case.tests],
        "expected_signatures": case.expected,
        "observed_signatures": [t.signature for t in case.run.tests],
        "test_failed": case.spectrum.failed.tolist(),
        "coverage_lines_per_test": [sorted(set(t.lines) & set(case.program.statements)) for t in case.run.tests],
        "exit_lines": list(case.spectrum.exit_lines),
        "exit_kinds": list(case.spectrum.exit_kinds),
        "static_findings": [f.to_dict() for f in case.findings],
        "classification": "detected" if case.detected else "not_detected_by_tests",
        "ground_truth_EVALUATION_ONLY": {
            "fault_lines": list(case.truth.fault_lines),
            "operators": list(case.truth.operators),
            "categories": list(case.truth.categories),
            "transformations": list(case.truth.descriptions),
        },
    }
