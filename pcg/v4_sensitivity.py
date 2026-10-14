"""Sensitivity of the version 4 ranking results to tie handling, and an independent recomputation.

The pre-registered mean average precision (``metrics.average_precision``) uses
mid-ranks for ties. When two faults tie, the formula counts both as "found
within rank r" at the shared mid-rank and can exceed 1 (up to 1.5 was seen).
Methods that tie many statements (coverage-only methods) are therefore
favoured. The pre-registered metric is left as it is; this module recomputes
the primary comparisons with the *expected* average precision when ties are
broken uniformly at random, which cannot exceed 1.

Scores of IV, PCG v3 fused, PCG spectrum only and logistic fusion come from
``probabilities.jsonl``; MUSE, Ochiai and FLITSR* are recomputed from the
cases kept by ``run_v4(stage_cache=...)``. Writes ``results/v4_sensitivity``.
"""

from __future__ import annotations

import json
import pickle
from pathlib import Path
from typing import Sequence

import numpy as np

from . import baselines, config, experiments as ex, metrics
from .flitsr import flitsr
from .v4_report import H1_BASELINES, _holm

DRAWS = 300
METHODS = ("iv", "pcg_fused", "pcg_size", "lr_fusion", "muse", "flitsr_star", "ochiai")
SETS = ("Q2", "E2", "Q3", "E3", "QHM", "EHM")


def expected_average_precision(scores: np.ndarray, fault_indices: Sequence[int], rng: np.random.Generator,
                               draws: int = DRAWS) -> float:
    """Average precision averaged over random orderings of tied statements (never above 1)."""
    rounded = np.round(np.asarray(scores, dtype=float), config.RANK_DECIMALS)
    faults = np.asarray(fault_indices)
    total = 0.0
    for _ in range(draws):
        order = np.lexsort((rng.random(len(rounded)), -rounded))
        rank = np.empty(len(rounded), dtype=int)
        rank[order] = np.arange(1, len(rounded) + 1)
        positions = np.sort(rank[faults])
        total += float(np.mean(np.arange(1, len(positions) + 1) / positions))
    return total / draws


def run_sensitivity(v4_path: Path, stage_cache: Path, out_path: Path = config.RESULTS_DIR / "v4_sensitivity") -> Path:
    with stage_cache.open("rb") as handle:
        cached = pickle.load(handle)
    cases = {c.case_id: c for name, group in {**cached["q"][0], **cached["e"][0]}.items() for c in group}
    observed = {**cached["q_observed"][0], **cached["e_observed"][0]}
    records = [json.loads(line) for line in (v4_path / "probabilities.jsonl").read_text(encoding="utf-8").splitlines()]
    rows = []
    for index, record in enumerate(records):
        if record["dataset"] not in SETS or record["condition"] != "transfer":
            continue
        case = cases[record["case_id"]]
        coverage, failed = case.spectrum.coverage, case.spectrum.failed
        scores = {m: np.asarray(record[m]) for m in ("iv", "pcg_fused", "pcg_size", "lr_fusion")}
        scores["muse"] = observed[case.case_id][1].muse
        scores["flitsr_star"] = flitsr(coverage, failed, multi_round=True)
        scores["ochiai"] = baselines.ochiai(coverage, failed)
        faults = np.flatnonzero(np.asarray(record["labels"])).tolist()
        rng = np.random.default_rng([config.SEED, 90, index])
        row = {"dataset": record["dataset"], "program": record["program"], "case_id": record["case_id"]}
        for m in METHODS:
            row[f"{m}.ap_mid"] = metrics.average_precision(scores[m], faults)
            row[f"{m}.ap_exp"] = expected_average_precision(scores[m], faults, rng)
        rows.append(row)

    out = ex.OutputDir(out_path)
    out.write_csv("per_case.csv", rows)
    write_derived(out.path, rows)
    out.finish()
    return out.path


def rebuild_derived(path: Path, out_path: Path) -> Path:
    """Rebuild ``summary.json`` and ``SUMMARY.md`` into ``out_path`` from the raw ``per_case.csv`` of ``path`` alone."""
    from .v4_report import _read_csv

    out_path.mkdir(parents=True, exist_ok=True)
    write_derived(out_path, _read_csv(path / "per_case.csv"))
    return out_path


def write_derived(folder: Path, rows) -> None:
    """Summary statistics, the corrected H1 comparisons and the Markdown table, from the per-case rows."""
    summary: dict = {"draws": DRAWS, "datasets": {}, "h1_corrected": []}
    for dataset in SETS:
        subset = [r for r in rows if r["dataset"] == dataset]
        summary["datasets"][dataset] = {
            "cases": len(subset),
            "share_above_one": {m: float(np.mean([r[f"{m}.ap_mid"] > 1 + 1e-9 for r in subset])) for m in METHODS},
            **{m: {"map_midrank": float(np.mean([r[f"{m}.ap_mid"] for r in subset])),
                   "map_expected": float(np.mean([r[f"{m}.ap_exp"] for r in subset]))} for m in METHODS}}
    entries = []
    for dataset in ("Q2", "E2"):
        subset = [r for r in rows if r["dataset"] == dataset]
        for baseline in H1_BASELINES:
            entry = ex._paired([{**r, "iv.x": r["iv.ap_exp"], f"{baseline}.x": r[f"{baseline}.ap_exp"]} for r in subset],
                               "iv", baseline, "x")
            entries.append({**entry, "dataset": dataset})
    for entry, adjusted in zip(entries, _holm([e["sign_flip_p_value"] for e in entries])):
        entry["holm_p_value"] = adjusted
        entry["supported"] = bool(entry["ci_low"] > 0 and adjusted < 0.05)
    summary["h1_corrected"] = entries
    (folder / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True, default=float), encoding="utf-8")
    lines = ["# Tie-corrected sensitivity of the average-precision results (generated)", "",
             "Expected average precision under random tie-breaking (300 draws per case, seeded).", "",
             "| Set | Method | MAP (mid-rank, as pre-registered) | MAP (expected) | Cases with AP above 1 |", "|---|---|---|---|---|"]
    for dataset, d in summary["datasets"].items():
        for m in METHODS:
            lines.append(f"| {dataset} | {m} | {d[m]['map_midrank']:.3f} | {d[m]['map_expected']:.3f} | "
                         f"{100 * d['share_above_one'][m]:.1f}% |")
    lines += ["", "H1 recomputed with the expected average precision:", "",
              "| Set | Comparison | Difference [95% CI] | Holm p | Supported |", "|---|---|---|---|---|"]
    for e in entries:
        lines.append(f"| {e['dataset']} | {e['comparison']} | {e['mean_difference']:+.3f} [{e['ci_low']:+.3f}, {e['ci_high']:+.3f}] | "
                     f"{e['holm_p_value']:.4f} | {'yes' if e['supported'] else 'no'} |")
    (folder / "SUMMARY.md").write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
