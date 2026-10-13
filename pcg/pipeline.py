"""Runs every experiment and writes ``results/benchmark``.

This is what ``python -m pcg benchmark`` executes. It is one pass, with no
manual step, and it leaves a ``MANIFEST.json`` only if everything finished.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path
from typing import Callable, Optional

from . import config, experiments as ex, reporting, visualize
from .config import ModelParams

BENCHMARK_DIR = config.RESULTS_DIR / "benchmark"


def run_benchmark(out_path: Path = BENCHMARK_DIR, log: Callable[[str], None] = print) -> Path:
    """Run all experiments. Returns the output directory."""
    start = time.time()

    def step(message: str) -> None:
        log(f"[{time.time() - start:6.1f}s] {message}")
        sys.stdout.flush()

    out = ex.OutputDir(out_path)

    step("running reference programs and generating mutants")
    references = ex.load_references()
    out.write_json("programs.json", [
        {"name": name, "source": ref.program.source, "statements": list(ref.program.statements),
         "tests": [list(t) for t in ref.bench.tests], "expected_signatures": ref.expected,
         "oracle": "reference implementation", "mutants_generated": len(ref.mutants)}
        for name, ref in references.items()
    ])

    step("executing single-fault mutants with per-test coverage; running pylint")
    cases, excluded = ex.build_first_order_cases(references)
    out.write_jsonl("cases.jsonl", [ex.case_record(case) for case in cases])
    out.write_json("excluded_mutants.json", excluded)

    step("estimating parameters (leave-one-program-out)")
    names = list(references)
    params, counts = ex.lopo_params(cases, names)
    out.write_json("params_lopo.json", {
        name: {mode: {"params": params[name][mode].to_dict(), "counts": counts[name][mode]} for mode in params[name]}
        for name in names
    })
    pooled = ex.pooled_params(cases)
    out.write_json("params_pooled.json", pooled.to_dict())

    step("experiment 1+2: single-fault localisation and calibration")
    first = ex.run_first_order(cases, params)
    out.write_csv("first_order_per_case.csv", first["rows"])
    out.write_json("first_order_summary.json", {k: first[k] for k in ("overall", "by_category", "comparisons")})
    out.write_json("calibration.json", first["calibration"])
    fault_free = ex.run_fault_free(references, params)
    out.write_csv("fault_free_programs.csv", fault_free)

    step("ablation: dependence slicing without deletion (SDL) mutants")
    no_sdl = [case for case in cases if case.truth.operators[0] != "SDL"]
    params_no_sdl, _ = ex.lopo_params(no_sdl, names)
    first_no_sdl = ex.run_first_order(no_sdl, params_no_sdl)
    out.write_json("slice_ablation_without_sdl.json", {
        "n_detected": len(first_no_sdl["rows"]),
        "overall": {m: first_no_sdl["overall"][m] for m in ("ochiai", "pcg", "pcg_slice")},
        "comparisons": [c for c in first_no_sdl["comparisons"] if c["comparison"] == "pcg_slice - pcg"],
    })

    step("experiment 3: sensitivity to hand-set parameters")
    sensitivity = ex.run_sensitivity(cases, pooled)
    out.write_csv("sensitivity.csv", sensitivity)

    step("experiment 4: two-fault programs")
    two_cases, two_excluded = ex.build_two_fault_cases(references)
    out.write_jsonl("two_fault_cases.jsonl", [ex.case_record(case) for case in two_cases])
    two = ex.run_two_fault(two_cases, params)
    out.write_csv("two_fault_per_case.csv", two["rows"])
    out.write_json("two_fault_summary.json", {
        "n_generated": len(two_cases) + len(two_excluded), "n_excluded": len(two_excluded),
        "n_not_detected": sum(not c.detected for c in two_cases), "n_detected": len(two["rows"]),
        "overall": two["overall"], "comparisons": two["comparisons"],
    })

    step("experiment 5: SIMULATED LLM-confidence signal")
    out.write_json("simulated_llm_summary.json", ex.run_simulated_llm(cases, params))

    step("experiment 6: targeted repair (validating every candidate patch)")
    repair = ex.run_repair(cases, references, params)
    out.write_csv("repair_per_case.csv", repair["rows"])
    out.write_jsonl("repair_attempts.jsonl", repair["attempts"])
    out.write_json("repair_summary.json", {k: repair[k] for k in ("overall", "comparisons")})

    step("drawing figures and writing SUMMARY.md")
    n_detected = len(first["rows"])
    visualize.plot_method_comparison(first["overall"], out.path / "fig_method_comparison.png", n_detected, len(names))
    visualize.plot_reliability(first["calibration"], out.path / "fig_reliability.png")
    visualize.plot_sensitivity(sensitivity, pooled.leak, out.path / "fig_sensitivity.png")
    (out.path / "SUMMARY.md").write_text(reporting.build_summary(out.path), encoding="utf-8")

    out.finish({"counts": {
        "programs": len(names),
        "mutants_generated": sum(len(r.mutants) for r in references.values()),
        "mutants_excluded": len(excluded),
        "mutants_valid": len(cases),
        "mutants_detected": n_detected,
        "mutants_not_detected": len(cases) - n_detected,
    }})
    step(f"done: {out.path}")
    return out.path


def load_params(program_name: Optional[str], mode: str = "coverage", path: Path = BENCHMARK_DIR) -> ModelParams:
    """Parameters for analysing ``program_name`` without using its own mutants.

    For a benchmark program the leave-one-out estimate is returned; for any
    other code (``program_name=None``) the pooled estimate.
    """
    import json

    ex.require_complete(path)
    if program_name is None:
        if mode != "coverage":
            raise ValueError("pooled parameters are stored for scope='coverage' only")
        return ModelParams.from_dict(json.loads((path / "params_pooled.json").read_text(encoding="utf-8")))
    data = json.loads((path / "params_lopo.json").read_text(encoding="utf-8"))
    return ModelParams.from_dict(data[program_name][mode]["params"])
