"""Version 5: confirmatory study of the interventional model on fresh programs (MBPP).

Protocol: ``research/RESEARCH_PROTOCOL_V5.md``. Nothing about the model changes: parameters are estimated on D1 and
applied unchanged (the "transfer" condition of version 4). Raw outputs (``per_case.csv``, ``probabilities.jsonl``) are
written first; ``pcg.v5_report`` derives the tables and figures from them.
"""

from __future__ import annotations

import time
import zlib
from pathlib import Path
from typing import Callable, Optional

import numpy as np

from . import config, experiments as ex
from . import v4
from .mbpp import load_mbpp
from .v4_sensitivity import expected_average_precision

V5_DIR = config.RESULTS_DIR / "v5"
METHODS = v4.BASELINE_METHODS + ("iv",)
PROB_METHODS = ("lr_fusion", "pcg_size", "pcg_fused", "iv")


def evaluate(dataset: str, cases, observed: dict, fitted: v4.Fitted) -> tuple[list[dict], list[dict]]:
    """Per-case rows (mid-rank and expected average precision for every method) and probability records."""
    rows, records = [], []
    for case in (c for c in cases if c.detected):
        scores, info = v4.score(case, observed, fitted, ablations=False)
        mask = case.faulty_mask
        faults = np.flatnonzero(mask).tolist()
        # seeded by the case identifier, not by its position in the run, so that a missing case cannot shift other cases' draws
        rng = np.random.default_rng([config.SEED, 91, zlib.crc32(case.case_id.encode())])
        row = {"dataset": dataset, "program": case.program_name, "case_id": case.case_id, "n_faults": len(faults),
               "n_statements": len(mask), "n_tests": case.spectrum.n_tests, "n_failed": case.spectrum.n_failed, **info}
        for method, values in scores.items():
            for key, value in v4.rank_metrics(values, faults).items():
                row[f"{method}.{key}"] = value
            row[f"{method}.ap_exp"] = expected_average_precision(values, faults, rng, config.EXPECTED_AP_DRAWS)
            row[f"{method}.confidence"] = float(np.max(values))
        rows.append(row)
        records.append({"dataset": dataset, "program": case.program_name, "case_id": case.case_id,
                        "labels": mask.astype(int).tolist(),
                        **{m: np.round(scores[m], 6).tolist() for m in PROB_METHODS}})
    return rows, records


def run_v5(out_path: Path = V5_DIR, mbpp_file: Optional[Path] = None, log: Callable[[str], None] = print,
           smoke_programs: Optional[int] = None) -> Path:
    """Run the confirmatory study and write ``results/v5``. ``smoke_programs`` is for pipeline tests only."""
    from . import v5_report

    start = time.time()

    def step(message: str) -> None:
        log(f"[{time.time() - start:6.1f}s] {message}")

    out = ex.OutputDir(out_path)
    step("D1: cases and variants (training programs)")
    references = ex.load_references()
    if smoke_programs:
        references = dict(list(references.items())[:smoke_programs])
    d1, _ = ex.build_first_order_cases(references)
    observed, cost_d1 = v4.observe([c for c in d1 if c.detected], config.STEP_LIMIT, config.SUBPROCESS_TIMEOUT_S, log)
    fitted = v4.fit(d1, observed, f"all of D1 ({len(d1)} valid single-fault mutants)")
    out.write_json("fitted_on_d1.json", {"model_params": fitted.trained.params.to_dict(),
                                         "fusion_params": fitted.trained.fusion.to_dict(),
                                         "interventional": fitted.iv.to_dict(), "estimation": fitted.counts})

    step("MBPP: loading, amplifying tests, reference runs")
    programs, report = load_mbpp(mbpp_file, reserved_names=tuple(references))
    threshold = config.MBPP_MIN_STATEMENTS
    if len(programs) < 100:  # protocol section 4, rule 5
        threshold -= 1
        programs, report = load_mbpp(mbpp_file, reserved_names=tuple(references), min_statements=threshold)
    if smoke_programs:
        programs = programs[:3 * smoke_programs]
    step(f"MBPP: {len(programs)} programs (minimum {threshold} statements); building fault-injected sets")
    one, two, three = config.MBPP_PER_PROGRAM
    sets, counts = v4.build_sets(programs, "M", {"1": one, "2": two, "3": three}, seed_offset=6000,
                                 timeout=config.MBPP_TIMEOUT_S, with_human=False)
    reasons: dict = {}
    for entry in report:
        if entry["status"] != "used":
            reasons[entry["reason"]] = reasons.get(entry["reason"], 0) + 1
    out.write_json("loading_report.json", {"problems": len(report), "programs_used": len(programs),
                                           "minimum_statements": threshold, "excluded_by_reason": reasons,
                                           **counts, "per_problem": report})

    all_cases = [c for cases in sets.values() for c in cases]
    step(f"static analysis of {len(all_cases)} cases")
    for begin in range(0, len(all_cases), 400):
        ex.attach_static_evidence(all_cases[begin:begin + 400])
    step("variants of the fault-injected cases")
    held_observed, cost_m = v4.observe([c for c in all_cases if c.detected], config.EXTERNAL_STEP_LIMIT,
                                       config.MBPP_TIMEOUT_S, log)

    rows, records = [], []
    for dataset in sorted(sets):
        began = time.time()
        r, p = evaluate(dataset, sets[dataset], held_observed, fitted)
        rows += r
        records += p
        step(f"{dataset}: {len(r)} cases scored in {time.time() - began:.0f}s")

    out.write_csv("per_case.csv", rows)
    out.write_jsonl("probabilities.jsonl", records)
    out.write_json("cost.json", {"D1": cost_d1, "MBPP": cost_m, "total_seconds": time.time() - start})
    step("summary, tables and figures")
    v5_report.write_all(out.path)
    out.finish({"counts": {"programs": len(programs), "cases_scored": len(rows)}})
    step(f"done: {out.path}")
    return out.path
