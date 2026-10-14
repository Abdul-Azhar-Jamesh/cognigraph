"""Version 4 experiments: the interventional multi-fault model on held-out data.

Protocol: ``research/RESEARCH_PROTOCOL.md``. Everything here follows it; the
places where the implementation had to deviate are listed in its section 11.

Conditions:

* ``development``: D1 (the project's own programs), leave-one-program-out.
* ``transfer``: every learned quantity from D1, applied to QuixBugs and
  HumanEvalFix. This is the condition the hypotheses refer to.
* ``in-suite`` and ``human-fitted``: secondary, HumanEvalFix only.

Raw outputs (``per_case*.csv``, ``probabilities.jsonl``) are written first;
``summary.json`` and the figures are derived from them by ``v4_report``.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Callable, Optional, Sequence

import numpy as np

from . import baselines, config, experiments as ex, metrics
from . import research as rs
from .barinel import barinel
from .execution import run_sources
from .flitsr import flitsr
from .fusion import effective_prior, size_aware_prior
from .humanevalfix import load_humanevalfix
from .interventional import (InterventionParams, enumerate_configurations, estimate_intervention_params,
                             interventional_posterior, summarise, variant_observations)
from .mbfl import LEVEL_PLAUSIBLE, MutationEvidence, hybrid_average
from .mutation import generate_mutants
from .program import Program, ProgramError
from .quixbugs import ExternalProgram, load_quixbugs

V4_DIR = config.RESULTS_DIR / "v4"

BASELINE_METHODS = ("ochiai", "tarantula", "barinel", "flitsr", "flitsr_star", "metallaxis", "muse", "hybrid_avg",
                    "lr_spectrum", "lr_fusion", "pcg_size", "pcg_fused")
ABLATION_METHODS = ("iv_composite", "iv_c1", "iv_c2", "iv_spectrum", "iv_half", "iv_quarter")
METHODS = BASELINE_METHODS + ("iv",) + ABLATION_METHODS
PROB_METHODS = ("lr_fusion", "pcg_size", "pcg_fused", "iv", "iv_composite", "iv_c1")
RANK_KEYS = ("ap", "first_rr", "first_top1", "first_top3", "all_top3", "all_top5", "mean_rank")
H1_BASELINES = ("pcg_fused", "pcg_size", "muse", "flitsr_star", "lr_fusion")


# ----------------------------------------------------------------------------
# Building cases
# ----------------------------------------------------------------------------

def _changed_lines(base: Sequence[str], source: str) -> Optional[tuple[int, ...]]:
    lines = source.splitlines()
    if len(lines) != len(base):
        return None
    return tuple(i for i, (a, b) in enumerate(zip(base, lines), 1) if a != b)


def injected_items(program: Program, name: str, base_truth: tuple[int, ...], n_new: int, limit: int,
                   rng: np.random.Generator, prefix: str) -> list[tuple[str, str, ex.GroundTruth]]:
    """Versions of ``program`` with ``n_new`` injected faults on distinct lines outside ``base_truth``.

    First-order mutants are visited in a seeded random order; each further
    fault is a seeded random mutant of the current version on a fresh line.
    """
    base = program.source.splitlines()
    firsts = [m for m in generate_mutants(program) if m.line not in base_truth]
    items, seen = [], set()
    for index in rng.permutation(len(firsts)):
        if len(items) >= limit:
            break
        current = firsts[int(index)]
        source, lines, operators = current.source, {current.line}, [current.operator]
        for _ in range(n_new - 1):
            try:
                further = [m for m in generate_mutants(Program.from_source(source, program.func_name))
                           if m.line not in lines and m.line not in base_truth]
            except ProgramError:
                further = []
            if not further:
                source = None
                break
            pick = further[int(rng.integers(len(further)))]
            source, lines, operators = pick.source, lines | {pick.line}, operators + [pick.operator]
        if source is None or source in seen:
            continue
        changed = _changed_lines(base, source)
        if changed is None or len(changed) != n_new or set(changed) & set(base_truth):
            continue
        seen.add(source)
        truth = ex.GroundTruth(tuple(sorted(set(base_truth) | set(changed))), tuple(operators),
                               ("injected",) * n_new, tuple(f"line {line}" for line in changed))
        items.append((f"{prefix}:{name}:{'+'.join(f'{line}{op}' for line, op in zip(changed, operators))}:{len(items)}",
                      source, truth))
    return items


def make_cases(prog: ExternalProgram, items: Sequence[tuple[str, str, ex.GroundTruth]],
               timeout: float) -> tuple[list[ex.Case], int]:
    """Execute sources of one program and assemble cases. Returns ``(cases, number unusable)``."""
    function = prog.correct.func_name  # the program identifier can differ from the function name
    runs = run_sources([source for _, source, _ in items], function, prog.tests,
                       step_limit=config.EXTERNAL_STEP_LIMIT, timeout=timeout)
    cases, unusable = [], 0
    for (case_id, source, truth), run in zip(items, runs):
        if run is None or run.compile_error is not None or len(run.tests) != len(prog.tests):
            unusable += 1
            continue
        try:
            program = Program.from_source(source, function)
        except ProgramError:
            unusable += 1
            continue
        cases.append(rs._external_case(prog.name, case_id, program, prog.tests, prog.expected, run, truth))
    return cases, unusable


def build_sets(programs: Sequence[ExternalProgram], prefix: str, per_program: dict[str, int],
               seed_offset: int, timeout: float, with_human: bool = True) -> tuple[dict[str, list[ex.Case]], dict]:
    """Held-out sets of one benchmark. Keys of ``per_program``: ``1``, ``2``, ``3`` (injected faults), ``HM``."""
    sets: dict[str, list[ex.Case]] = ({f"{prefix}H": []} if with_human else {}) | {f"{prefix}{k}": [] for k in per_program}
    unusable = 0
    for index, prog in enumerate(programs):
        if with_human:
            human_truth = ex.GroundTruth(prog.fault_lines, ("human",), (prog.fault_kind,), ("human-written bug",))
            cases, bad = make_cases(prog, [(f"{prefix}H:{prog.name}", prog.buggy.source, human_truth)], timeout)
            sets[f"{prefix}H"] += cases
            unusable += bad
        for key, limit in per_program.items():
            rng = np.random.default_rng([config.SEED, seed_offset, index, {"1": 1, "2": 2, "3": 3, "HM": 9}[key]])
            if key == "HM":
                items = injected_items(prog.buggy, prog.name, prog.fault_lines, 1, limit, rng, f"{prefix}HM")
            else:
                items = injected_items(prog.correct, prog.name, (), int(key), limit, rng, f"{prefix}{key}")
            cases, bad = make_cases(prog, items, timeout)
            sets[f"{prefix}{key}"] += cases
            unusable += bad
    identifiers = [c.case_id for cases in sets.values() for c in cases]
    if len(set(identifiers)) != len(identifiers):
        raise RuntimeError("case identifiers are not unique")
    counts = {name: {"cases": len(cases), "detected": sum(c.detected for c in cases),
                     "programs": len({c.program_name for c in cases if c.detected})}
              for name, cases in sets.items()}
    return sets, {"sets": counts, "unusable_runs": unusable}


# ----------------------------------------------------------------------------
# Evidence, fitting, scoring
# ----------------------------------------------------------------------------

def observe(cases: Sequence[ex.Case], step_limit: int, timeout: float, log: Callable[[str], None]) -> tuple[dict, dict]:
    """Variant observations and version 3 mutation evidence of every case. Returns ``(observed, cost)``."""
    observed, cost = {}, {"variant_texts_run": 0, "seconds": 0.0, "variants_generated": 0, "cases": 0}
    for name in sorted({c.program_name for c in cases}):
        own = [c for c in cases if c.program_name == name]
        variants, store = rs.run_variants(own, step_limit, timeout)
        cost["variant_texts_run"] += store.runs
        cost["seconds"] += store.seconds
        for case in own:
            usable = [(v.line, store.outcomes[v.source]) for v in variants[case.case_id]]
            cost["variants_generated"] += len(usable)
            cost["cases"] += 1
            observed[case.case_id] = (
                variant_observations(case.program.statements, case.spectrum.coverage, case.spectrum.failed,
                                     case.expected, usable),
                rs.evidence_for_case(case, variants[case.case_id], store))
    log(f"    variants: {cost['variant_texts_run']} runs for {cost['cases']} cases in {cost['seconds']:.0f}s")
    return observed, cost


def _no_evidence(n: int) -> MutationEvidence:
    return MutationEvidence(np.zeros(n, dtype=int), np.zeros(n, dtype=int), np.zeros(n), np.zeros(n), 0, 0)


@dataclass
class Fitted:
    """Everything learned from one set of training programs."""

    trained: rs.Trained
    iv: InterventionParams
    iv_composite: InterventionParams
    counts: dict


def fit(valid: Sequence[ex.Case], observed: dict, provenance: str) -> Fitted:
    """Fit all learned quantities on single-fault training cases (``valid`` includes undetected ones)."""
    detected = [c for c in valid if c.detected]
    evidence = {c.case_id: observed[c.case_id][1] if c.case_id in observed else _no_evidence(len(c.program.statements))
                for c in valid}
    trained = rs.train(valid, detected, evidence, provenance)
    training = [(observed[c.case_id][0], c.faulty_mask) for c in detected]
    kinds = dict(n_nonrepair=config.IV_NONREPAIR_KINDS, n_repair=config.IV_REPAIR_KINDS)
    iv, counts = estimate_intervention_params(training, provenance, layer="exclusive", **kinds)
    composite, _ = estimate_intervention_params(training, provenance, layer="composite", **kinds)
    return Fitted(trained, iv, composite, counts)


def score(case: ex.Case, observed: dict, fitted: Fitted, ablations: bool = True) -> tuple[dict[str, np.ndarray], dict]:
    """Scores of every method for one case. Receives no ground truth."""
    observations, evidence = observed[case.case_id]
    coverage, failed = case.spectrum.coverage, case.spectrum.failed
    n = len(case.program.statements)
    params, fusion = fitted.trained.params, fitted.trained.fusion
    spectrum_x, fusion_x = rs.features_of(case, evidence)
    ochiai_scores = baselines.ochiai(coverage, failed)
    scores = {
        "ochiai": ochiai_scores,
        "tarantula": baselines.tarantula(coverage, failed),
        "barinel": barinel(coverage, failed, params.prior_fault),
        "flitsr": flitsr(coverage, failed),
        "flitsr_star": flitsr(coverage, failed, multi_round=True),
        "metallaxis": evidence.metallaxis,
        "muse": evidence.muse,
        "hybrid_avg": hybrid_average(ochiai_scores, evidence.metallaxis),
        "lr_spectrum": fitted.trained.lr_spectrum.predict(spectrum_x),
        "lr_fusion": fitted.trained.lr_fusion.predict(fusion_x),
        "pcg_size": rs.posterior(case, effective_prior(n, params.prior_fault, fusion, size_aware=True), params),
        "pcg_fused": rs.posterior(case, effective_prior(n, params.prior_fault, fusion, evidence, size_aware=True,
                                                        use_mutation=True), params),
    }
    grid, weights = params.exposure_prior()
    prior = np.full(n, size_aware_prior(n, fusion.mu))
    common = (prior, coverage, failed, observations)
    enumeration = enumerate_configurations(*common, fitted.iv, grid, weights, params.leak, config.IV_MAX_FAULTS)
    main = summarise(enumeration)
    scores["iv"] = main.marginals
    if ablations:
        scores["iv_c1"] = summarise(enumeration, max_faults=1).marginals
        scores["iv_c2"] = summarise(enumeration, max_faults=2).marginals
        scores["iv_half"] = summarise(enumeration, odds_scale=0.5).marginals
        scores["iv_quarter"] = summarise(enumeration, odds_scale=0.25).marginals
        scores["iv_composite"] = interventional_posterior(*common, fitted.iv_composite, grid, weights, params.leak,
                                                          config.IV_MAX_FAULTS).marginals
        scores["iv_spectrum"] = interventional_posterior(*common, None, grid, weights, params.leak,
                                                         config.IV_MAX_FAULTS).marginals
    info = {"expected_faults": main.expected_faults, "boundary_mass": main.boundary_mass,
            "configurations": main.n_configurations,
            "p_one_fault": main.size_distribution[1] if len(main.size_distribution) > 1 else 1.0}
    return scores, info


def rank_metrics(scores: np.ndarray, fault_indices: Sequence[int]) -> dict[str, float]:
    multi = metrics.multi_fault_metrics(scores, fault_indices)
    return {"ap": metrics.average_precision(scores, fault_indices), "first_rr": multi["first_reciprocal_rank"],
            "first_top1": multi["first_top1"], "first_top3": multi["first_top3"], "all_top3": multi["all_top3"],
            "all_top5": multi["all_top5"], "mean_rank": multi["mean_rank"]}


def evaluate(dataset: str, condition: str, cases: Sequence[ex.Case], observed: dict,
             fitted_for: Callable[[ex.Case], Fitted], ablations: bool = True) -> tuple[list[dict], list[dict]]:
    """Score the detected cases of one set. Returns per-case rows and per-case probability records."""
    rows, probabilities = [], []
    for case in cases:
        if not case.detected:
            continue
        scores, info = score(case, observed, fitted_for(case), ablations)
        mask = case.faulty_mask
        faults = np.flatnonzero(mask).tolist()
        levels = observed[case.case_id][1].levels
        row = {"dataset": dataset, "condition": condition, "program": case.program_name, "case_id": case.case_id,
               "n_faults": len(faults), "n_statements": len(mask), "n_active": int(case.spectrum.coverage.any(axis=0).sum()),
               "n_tests": case.spectrum.n_tests, "n_failed": case.spectrum.n_failed,
               "faults_with_restoring_variant": int((levels[faults] == LEVEL_PLAUSIBLE).sum()), **info}
        for method, values in scores.items():
            for key, value in rank_metrics(values, faults).items():
                row[f"{method}.{key}"] = value
            row[f"{method}.confidence"] = float(np.max(values))
        rows.append(row)
        probabilities.append({"dataset": dataset, "condition": condition, "program": case.program_name,
                              "case_id": case.case_id, "labels": mask.astype(int).tolist(),
                              **{m: np.round(scores[m], 6).tolist() for m in PROB_METHODS if m in scores}})
    return rows, probabilities


def truncation_check(cases: Sequence[ex.Case], observed: dict, fitted: Fitted) -> list[dict]:
    """Hypothesis H6: marginals with at most 3 faults against at most 4, on sampled small two-fault cases."""
    small = [c for c in cases if c.detected and int(c.spectrum.coverage.any(axis=0).sum()) <= config.TRUNCATION_CHECK_MAX_ACTIVE]
    rng = np.random.default_rng([config.SEED, 46])
    chosen = [small[int(i)] for i in rng.permutation(len(small))[: config.TRUNCATION_CHECK_CASES]]
    params, fusion = fitted.trained.params, fitted.trained.fusion
    grid, weights = params.exposure_prior()
    out = []
    for case in chosen:
        n = len(case.program.statements)
        enumeration = enumerate_configurations(np.full(n, size_aware_prior(n, fusion.mu)), case.spectrum.coverage,
                                               case.spectrum.failed, observed[case.case_id][0], fitted.iv, grid,
                                               weights, params.leak, 4)
        four, three = summarise(enumeration), summarise(enumeration, max_faults=3)
        out.append({"case_id": case.case_id, "program": case.program_name,
                    "max_abs_difference": float(np.max(np.abs(four.marginals - three.marginals))),
                    "mass_on_four_faults": four.size_distribution[-1] if len(four.size_distribution) == 5 else 0.0,
                    "same_top_statement": bool(np.argmax(four.marginals) == np.argmax(three.marginals))})
    return out


# ----------------------------------------------------------------------------
# The whole run
# ----------------------------------------------------------------------------

def run_v4(out_path: Path = V4_DIR, quixbugs_dir: Optional[Path] = None, humaneval_file: Optional[Path] = None,
           log: Callable[[str], None] = print, smoke_programs: Optional[int] = None,
           stage_cache: Optional[Path] = None) -> Path:
    """Run the version 4 experiments and write ``results/v4``.

    ``smoke_programs`` restricts every benchmark to its first few programs; it exists only to
    test that the pipeline runs and must not be used for results. ``stage_cache`` names a file in
    which the built cases and variant observations are kept between runs; it exists so that a
    crash in a late stage does not cost an hour, and is not used for reported runs.
    """
    import pickle
    from . import v4_report

    start = time.time()

    def step(message: str) -> None:
        log(f"[{time.time() - start:6.1f}s] {message}")

    out = ex.OutputDir(out_path)
    rows: list[dict] = []
    probabilities: list[dict] = []
    cost: dict = {}

    step("D1 (development): cases and variants")
    references = ex.load_references()
    if smoke_programs:
        references = dict(list(references.items())[:smoke_programs])
    d1, _ = ex.build_first_order_cases(references)
    d1_two = [c for c in ex.build_two_fault_cases(references)[0] if c.detected]
    limits = (config.STEP_LIMIT, config.SUBPROCESS_TIMEOUT_S)
    observed, cost["D1-1"] = observe([c for c in d1 if c.detected], *limits, log)
    observed_two, cost["D1-2"] = observe(d1_two, *limits, log)
    observed.update(observed_two)

    step("D1 (development): leave-one-program-out")
    folds = {name: fit([c for c in d1 if c.program_name != name], observed, f"D1 without {name}") for name in references}
    for dataset, cases in (("D1-1", d1), ("D1-2", d1_two)):
        r, p = evaluate(dataset, "development", cases, observed, lambda case: folds[case.program_name])
        rows += r
        probabilities += p

    step("fitting on all of D1 (the transfer condition)")
    pooled = fit(d1, observed, f"all of D1 ({len(d1)} valid single-fault mutants)")
    out.write_json("fitted_on_d1.json", {
        "model_params": pooled.trained.params.to_dict(), "fusion_params": pooled.trained.fusion.to_dict(),
        "interventional": pooled.iv.to_dict(), "interventional_composite": pooled.iv_composite.to_dict(),
        "estimation": pooled.counts,
        "model_order_bic": [
            {"non_repair_kinds": k, **{key: estimate_intervention_params(
                [(observed[c.case_id][0], c.faulty_mask) for c in d1 if c.detected], "bic", n_nonrepair=k,
                n_repair=1, iterations=150)[1][key] for key in ("bic_nonrepair",)}} for k in range(2, 8)]})

    cached = None
    if stage_cache is not None and stage_cache.exists():
        with stage_cache.open("rb") as handle:
            cached = pickle.load(handle)
        log(f"    using cached stages from {stage_cache}")
    step("QuixBugs: loading and building held-out sets")
    q_programs, q_report = load_quixbugs(quixbugs_dir)
    q_programs = q_programs[:smoke_programs] if smoke_programs else q_programs
    qh, q1, _ = cached["v3"] if cached else rs.build_external_cases(q_programs)  # version 3 sets D2, D3
    two, three, hybrid = config.QUIXBUGS_MULTI_PER_PROGRAM
    q_sets, q_counts = cached["q"] if cached else build_sets(q_programs, "Q", {"2": two, "3": three, "HM": hybrid}, seed_offset=4000,
                                 timeout=config.EXTERNAL_TIMEOUT_S)
    q_sets["QH"], q_sets["Q1"] = qh, q1
    q_counts["sets"]["QH"] = {"cases": len(qh), "detected": sum(c.detected for c in qh), "programs": len({c.program_name for c in qh})}
    q_counts["sets"]["Q1"] = {"cases": len(q1), "detected": sum(c.detected for c in q1), "programs": len({c.program_name for c in q1})}

    step("HumanEvalFix: loading and building held-out sets")
    e_programs, e_report = load_humanevalfix(humaneval_file, reserved_names=tuple(references))
    e_programs = e_programs[:3 * smoke_programs] if smoke_programs else e_programs
    one, two, three, hybrid = config.HUMANEVAL_PER_PROGRAM
    e_sets, e_counts = cached["e"] if cached else build_sets(e_programs, "E", {"1": one, "2": two, "3": three, "HM": hybrid}, seed_offset=5000,
                                 timeout=config.HUMANEVAL_TIMEOUT_S)
    out.write_json("loading_report.json", {
        "quixbugs": {"programs_used": len(q_programs), **q_counts, "per_program": q_report},
        "humanevalfix": {"problems": len(e_report), "programs_used": len(e_programs),
                         "excluded_by_reason": _count(entry.get("reason") for entry in e_report if entry["status"] != "used"),
                         **e_counts, "per_program": e_report}})

    held_out = {**q_sets, **e_sets}
    all_cases = [c for cases in held_out.values() for c in cases]
    step(f"static analysis of {len(all_cases)} held-out cases")
    for begin in range(0, 0 if cached else len(all_cases), 400):  # in chunks: file names go on the command line
        ex.attach_static_evidence(all_cases[begin:begin + 400])

    step("variants of the held-out cases")
    external_limits = (config.EXTERNAL_STEP_LIMIT, config.EXTERNAL_TIMEOUT_S)
    held_observed, cost["QuixBugs"] = cached["q_observed"] if cached else observe([c for s in q_sets.values() for c in s if c.detected], *external_limits, log)
    e_observed, cost["HumanEvalFix"] = cached["e_observed"] if cached else observe([c for s in e_sets.values() for c in s if c.detected],
                                               config.EXTERNAL_STEP_LIMIT, config.HUMANEVAL_TIMEOUT_S, log)
    if stage_cache is not None and cached is None:
        with stage_cache.open("wb") as handle:
            pickle.dump({"q": (q_sets, q_counts), "v3": (qh, q1, None), "e": (e_sets, e_counts),
                         "q_observed": (dict(held_observed), cost["QuixBugs"]),
                         "e_observed": (e_observed, cost["HumanEvalFix"])}, handle)
    held_observed.update(e_observed)

    step("transfer condition: scoring every held-out set")
    for dataset in sorted(held_out):
        began = time.time()
        r, p = evaluate(dataset, "transfer", held_out[dataset], held_observed, lambda case: pooled)
        rows += r
        probabilities += p
        log(f"    {dataset}: {len(r)} cases in {time.time() - began:.0f}s")

    step("hypothesis H6: three against four allowed faults")
    truncation = truncation_check(q_sets["Q2"] + e_sets["E2"], held_observed, pooled)

    step("secondary conditions on HumanEvalFix")
    names = sorted(p.name for p in e_programs)
    fold_of = {name: i % config.HUMANEVAL_FOLDS for i, name in enumerate(names)}
    in_suite, human_fitted = {}, {}
    kinds = dict(n_nonrepair=config.IV_NONREPAIR_KINDS, n_repair=config.IV_REPAIR_KINDS)
    for fold in range(config.HUMANEVAL_FOLDS):
        train_e1 = [c for c in e_sets["E1"] if fold_of[c.program_name] != fold]
        in_suite[fold] = fit(train_e1, held_observed, f"HumanEval single-fault mutants, fold {fold} held out")
        human = [(held_observed[c.case_id][0], c.faulty_mask) for c in e_sets["EH"]
                 if c.detected and fold_of[c.program_name] != fold]
        iv_human, _ = estimate_intervention_params(human, f"HumanEvalFix human bugs, fold {fold} held out",
                                                   layer="exclusive", **kinds)
        human_fitted[fold] = replace(pooled, iv=iv_human)
    secondary_rows: list[dict] = []
    for dataset in ("EH", "E1", "E2", "E3", "EHM"):
        r, _ = evaluate(dataset, "in-suite", e_sets[dataset], held_observed,
                        lambda case: in_suite[fold_of[case.program_name]], ablations=False)
        secondary_rows += r
    r, _ = evaluate("EH", "human-fitted", e_sets["EH"], held_observed,
                    lambda case: human_fitted[fold_of[case.program_name]], ablations=False)
    secondary_rows += r
    out.write_json("fitted_secondary.json", {
        "in_suite": {str(f): fitted.iv.to_dict() for f, fitted in in_suite.items()},
        "human_fitted": {str(f): fitted.iv.to_dict() for f, fitted in human_fitted.items()}})

    out.write_csv("per_case.csv", rows)
    out.write_csv("per_case_secondary.csv", secondary_rows)
    out.write_jsonl("probabilities.jsonl", probabilities)
    out.write_json("truncation_check.json", truncation)
    out.write_json("cost.json", {**cost, "total_seconds": time.time() - start})

    step("summary, tables and figures")
    v4_report.write_all(out.path)
    out.finish({"counts": {"cases_scored": len(rows), "secondary_cases_scored": len(secondary_rows),
                           "quixbugs_programs": len(q_programs), "humanevalfix_programs": len(e_programs)}})
    step(f"done: {out.path}")
    return out.path


def _count(values) -> dict:
    out: dict = {}
    for value in values:
        out[value] = out.get(value, 0) + 1
    return out
