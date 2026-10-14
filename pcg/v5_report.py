"""Derived outputs of the version 5 study (tables, statistics, figures) from the raw files of ``results/v5``.

``python -m pcg v5-report`` rebuilds them without re-running any experiment. The tie-corrected rows of the version 4
benchmarks (QuixBugs, HumanEval) used for the pooled comparisons are read from ``results/v4_sensitivity``.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Sequence

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

from . import config, experiments as ex, metrics  # noqa: E402
from .v4_report import (COLORS, LABELS, MAIN, _bars, _holm, _paired_brier, _quality, _read_csv, _save,  # noqa: E402
                        _style)

SETS = ("M1", "M2", "M3")
C1_BASELINES = ("muse", "flitsr_star", "pcg_size", "pcg_fused", "lr_fusion")
KEYS = ("ap_exp", "ap", "first_top1", "all_top3")
BENCHMARK_COLORS = {"QuixBugs": "#2c7fb8", "HumanEval": "#e6a020", "MBPP": "#c0392b", "pooled": "#222222"}
BENCHMARK_OF = {"Q": "QuixBugs", "E": "HumanEval", "M": "MBPP"}


def _diff(rows: Sequence[dict], a: str, b: str, key: str = "ap_exp") -> dict:
    return ex._paired(list(rows), a, b, key)


def build_summary(path: Path, sensitivity: Path = config.RESULTS_DIR / "v4_sensitivity") -> dict:
    rows = _read_csv(path / "per_case.csv")
    records = [json.loads(line) for line in (path / "probabilities.jsonl").read_text(encoding="utf-8").splitlines()]
    by_set = {s: [r for r in rows if r["dataset"] == s] for s in SETS}
    methods = [m for m in LABELS if f"{m}.ap_exp" in rows[0]]
    summary: dict = {"datasets": {}, "ranking": {}, "hypotheses": {}, "calibration": {}}
    for s, subset in by_set.items():
        summary["datasets"][s] = {"cases": len(subset), "programs": len({r["program"] for r in subset}),
                                  "mean_statements": float(np.mean([r["n_statements"] for r in subset])),
                                  "mean_tests": float(np.mean([r["n_tests"] for r in subset])),
                                  "mean_failing_tests": float(np.mean([r["n_failed"] for r in subset])),
                                  "mean_expected_faults": float(np.mean([r["expected_faults"] for r in subset])),
                                  "share_ap_above_one": float(np.mean([r["iv.ap"] > 1 + 1e-9 for r in subset]))}
        summary["ranking"][s] = ex._aggregate(subset, methods, KEYS)

    c1 = [dict(_diff(by_set[s], "iv", b), dataset=s) for s in ("M2", "M3") for b in C1_BASELINES]
    for entry, adjusted in zip(c1, _holm([e["sign_flip_p_value"] for e in c1])):
        entry["holm_p_value"] = adjusted
        entry["supported"] = bool(entry["ci_low"] > 0 and adjusted < 0.05)
    summary["hypotheses"]["C1"] = c1
    c2 = dict(_diff(by_set["M1"], "iv", "pcg_fused", "first_top1"), dataset="M1")
    c2["supported"] = bool(c2["ci_low"] > -0.02)
    summary["hypotheses"]["C2"] = c2
    summary["hypotheses"]["C3"] = {s: next(e["mean_difference"] for e in c1 if e["dataset"] == s and e["comparison"].endswith("muse"))
                                   for s in ("M2", "M3")}

    # pooled comparisons over the three benchmarks (QuixBugs and HumanEval rows come from the version 4 sensitivity run)
    old = _read_csv(sensitivity / "per_case.csv")
    groups = {"2": {"QuixBugs": [r for r in old if r["dataset"] == "Q2"], "HumanEval": [r for r in old if r["dataset"] == "E2"],
                    "MBPP": by_set["M2"]},
              "3": {"QuixBugs": [r for r in old if r["dataset"] == "Q3"], "HumanEval": [r for r in old if r["dataset"] == "E3"],
                    "MBPP": by_set["M3"]}}
    forest = []
    for faults, per_benchmark in groups.items():
        for baseline in ("muse", "flitsr_star", "pcg_size", "pcg_fused", "lr_fusion"):
            pooled = []
            for benchmark, subset in per_benchmark.items():
                entry = _diff(subset, "iv", baseline)
                forest.append({"faults": int(faults), "benchmark": benchmark, "baseline": baseline,
                               "programs": len({r["program"] for r in subset}), **{k: entry[k] for k in
                               ("mean_difference", "ci_low", "ci_high", "sign_flip_p_value")}})
                pooled += [{**r, "program": benchmark[0] + ":" + r["program"]} for r in subset]
            entry = _diff(pooled, "iv", baseline)
            forest.append({"faults": int(faults), "benchmark": "pooled", "baseline": baseline,
                           "programs": len({r["program"] for r in pooled}), **{k: entry[k] for k in
                           ("mean_difference", "ci_low", "ci_high", "sign_flip_p_value")}})
    summary["hypotheses"]["C4"] = forest

    records_by_set = {s: [r for r in records if r["dataset"] == s] for s in SETS}
    for s in SETS:
        summary["calibration"][s] = {m: _quality(records_by_set[s], m) for m in ("iv", "pcg_fused", "lr_fusion", "pcg_size")}
    summary["paired_brier"] = [dict(_paired_brier(records_by_set[s], "iv", b), dataset=s)
                               for s in SETS for b in ("pcg_fused", "lr_fusion")]
    mixed = [r for r in rows]
    summary["inferred_faults"] = {
        "auc_multi_vs_single": metrics.roc_auc(np.array([r["expected_faults"] for r in mixed]), np.array([r["n_faults"] > 1 for r in mixed])),
        "mean_by_true_count": {str(k): float(np.mean([r["expected_faults"] for r in mixed if r["n_faults"] == k])) for k in (1, 2, 3)}}
    summary["cost"] = json.loads((path / "cost.json").read_text(encoding="utf-8"))
    return summary


def write_tables(path: Path, summary: dict) -> None:
    folder = path / "tables"
    folder.mkdir(exist_ok=True)

    def write(name: str, header: Sequence[str], body: Sequence[Sequence]) -> None:
        with (folder / name).open("w", encoding="utf-8", newline="") as handle:
            writer = csv.writer(handle, lineterminator="\n")
            writer.writerow(header)
            writer.writerows(body)

    write("ranking_all.csv", ["dataset", "method"] + [f"{k}_{s}" for k in KEYS for s in ("mean", "ci_low", "ci_high")],
          [[d, m] + [f"{v[k][s]:.4f}" for k in KEYS for s in ("mean", "ci_low", "ci_high")]
           for d, by in summary["ranking"].items() for m, v in by.items()])
    write("c1_comparisons.csv", ["dataset", "comparison", "mean_difference", "ci_low", "ci_high", "sign_flip_p", "holm_p", "supported"],
          [[e["dataset"], e["comparison"], f"{e['mean_difference']:.4f}", f"{e['ci_low']:.4f}", f"{e['ci_high']:.4f}",
            f"{e['sign_flip_p_value']:.5f}", f"{e['holm_p_value']:.5f}", e["supported"]] for e in summary["hypotheses"]["C1"]])
    write("forest_all_benchmarks.csv", ["faults", "benchmark", "baseline", "programs", "mean_difference", "ci_low", "ci_high", "sign_flip_p"],
          [[e["faults"], e["benchmark"], e["baseline"], e["programs"], f"{e['mean_difference']:.4f}", f"{e['ci_low']:.4f}",
            f"{e['ci_high']:.4f}", f"{e['sign_flip_p_value']:.5f}"] for e in summary["hypotheses"]["C4"]])
    write("calibration.csv", ["dataset", "method", "brier", "brier_ci_low", "brier_ci_high", "brier_base_rate", "skill", "log_loss", "ece"],
          [[d, m, f"{q['brier']:.5f}", f"{q['brier_ci_low']:.5f}", f"{q['brier_ci_high']:.5f}", f"{q['brier_base_rate']:.5f}",
            f"{q['skill']:.4f}", f"{q['log_loss']:.5f}", f"{q['ece']:.5f}"] for d, by in summary["calibration"].items() for m, q in by.items()])


def write_figures(path: Path, summary: dict) -> None:
    _style()
    folder = path / "figures"
    folder.mkdir(exist_ok=True)
    fig, axes = plt.subplots(1, 3, figsize=(13, 4.2), sharex=True)
    for ax, s in zip(axes, SETS):
        _bars(ax, summary["ranking"][s], MAIN, "ap_exp", f"{s}: {s[1]} injected fault{'s' if s[1] != '1' else ''} "
              f"(n = {summary['datasets'][s]['programs']} programs)", "expected average precision (95% interval)")
    fig.tight_layout()
    _save(fig, folder, "fig_v5_1_mbpp_ranking")

    forest = summary["hypotheses"]["C4"]
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.6), sharex=True)
    baselines = list(("muse", "flitsr_star", "pcg_size", "pcg_fused", "lr_fusion"))
    for ax, faults in zip(axes, (2, 3)):
        for b_index, baseline in enumerate(baselines):
            for offset, benchmark in zip((-0.27, -0.09, 0.09, 0.27), ("QuixBugs", "HumanEval", "MBPP", "pooled")):
                e = next(x for x in forest if x["faults"] == faults and x["baseline"] == baseline and x["benchmark"] == benchmark)
                y = b_index + offset
                ax.errorbar(e["mean_difference"], y, xerr=[[e["mean_difference"] - e["ci_low"]], [e["ci_high"] - e["mean_difference"]]],
                            fmt="D" if benchmark == "pooled" else "o", markersize=4.5 if benchmark == "pooled" else 3.5,
                            color=BENCHMARK_COLORS[benchmark], elinewidth=1.0, capsize=1.5,
                            label=benchmark if b_index == 0 else None)
        ax.axvline(0, color="#555555", linewidth=0.8)
        ax.set_yticks(range(len(baselines)))
        ax.set_yticklabels([LABELS[b] for b in baselines])
        ax.invert_yaxis()
        ax.set_xlabel("IV minus baseline: expected average precision (95% interval)")
        ax.set_title(f"{faults} injected faults", loc="left", fontsize=9, fontweight="bold")
        ax.grid(axis="y", visible=False)
    axes[0].legend(fontsize=7, loc="lower right")
    fig.tight_layout()
    _save(fig, folder, "fig_v5_2_forest")

    fig, axes = plt.subplots(1, 3, figsize=(12, 3.9), sharex=True, sharey=True)
    for ax, s in zip(axes, SETS):
        ax.plot([0, 1], [0, 1], color="#555555", linewidth=0.8, linestyle="--")
        for m in ("iv", "pcg_fused", "lr_fusion"):
            q = summary["calibration"][s][m]
            table = [b for b in q["reliability"] if b["count"] > 0]
            ax.plot([b["mean_predicted"] for b in table], [b["observed_frequency"] for b in table], marker="o", markersize=3.5,
                    color=COLORS[m], linewidth=1.2, label=f"{LABELS[m]} (skill {q['skill']:+.2f}, ECE {q['ece']:.3f})")
        ax.set_title(s, loc="left", fontsize=9, fontweight="bold")
        ax.set_xlabel("predicted probability of being faulty")
        ax.legend(fontsize=6.5, loc="upper left")
    axes[0].set_ylabel("observed share of faulty statements")
    fig.tight_layout()
    _save(fig, folder, "fig_v5_3_reliability")


def build_markdown(summary: dict) -> str:
    h = summary["hypotheses"]
    out = ["# Version 5 results: MBPP confirmatory study (generated)", "",
           "Generated by `pcg.v5_report` from the raw files. Primary metric: expected average precision (random tie-breaking). "
           "Intervals: 95% cluster bootstrap, programs as the unit.", "", "## Data", "",
           "| Set | Cases | Programs | Mean statements | Mean tests | Mean failing tests | Mean inferred faults |", "|---|---|---|---|---|---|---|"]
    for s, d in summary["datasets"].items():
        out.append(f"| {s} | {d['cases']} | {d['programs']} | {d['mean_statements']:.1f} | {d['mean_tests']:.1f} | "
                   f"{d['mean_failing_tests']:.1f} | {d['mean_expected_faults']:.2f} |")
    for s in SETS:
        out += ["", f"## {s}", "", "| Method | Expected AP | Mid-rank AP (v4 definition) | First fault Top-1 | All faults in top 3 |", "|---|---|---|---|---|"]
        for m in MAIN:
            r = summary["ranking"][s][m]
            c = lambda v: f"{v['mean']:.3f} [{v['ci_low']:.3f}, {v['ci_high']:.3f}]"
            out.append(f"| {LABELS[m]} | {c(r['ap_exp'])} | {c(r['ap'])} | {c(r['first_top1'])} | {c(r['all_top3'])} |")
    out += ["", "## C1: IV against each baseline, expected AP (Holm over 10 comparisons)", "",
            "| Set | Comparison | Difference [95% CI] | Sign-flip p | Holm p | Supported |", "|---|---|---|---|---|---|"]
    for e in h["C1"]:
        out.append(f"| {e['dataset']} | {e['comparison']} | {e['mean_difference']:+.3f} [{e['ci_low']:+.3f}, {e['ci_high']:+.3f}] | "
                   f"{e['sign_flip_p_value']:.4f} | {e['holm_p_value']:.4f} | {'yes' if e['supported'] else 'no'} |")
    c2 = h["C2"]
    out += ["", "## C2: single-fault cost (IV minus PCG v3 fused, Top-1)", "",
            f"{c2['mean_difference']:+.3f} [{c2['ci_low']:+.3f}, {c2['ci_high']:+.3f}]; supported (lower end above -0.02): "
            f"{'yes' if c2['supported'] else 'no'}.", "",
            f"## C3: sign of IV minus MUSE: M2 {h['C3']['M2']:+.3f}, M3 {h['C3']['M3']:+.3f}.", "",
            "## C4: IV minus baseline over the three benchmarks (expected AP)", "",
            "| Faults | Baseline | Benchmark | Programs | Difference [95% CI] | Sign-flip p |", "|---|---|---|---|---|---|"]
    for e in h["C4"]:
        out.append(f"| {e['faults']} | {LABELS[e['baseline']]} | {e['benchmark']} | {e['programs']} | "
                   f"{e['mean_difference']:+.3f} [{e['ci_low']:+.3f}, {e['ci_high']:+.3f}] | {e['sign_flip_p_value']:.4f} |")
    out += ["", "## Probabilities", "", "| Set | Method | Brier [95% CI] | Base-rate Brier | Skill | Log loss | ECE |", "|---|---|---|---|---|---|---|"]
    for s, by in summary["calibration"].items():
        for m, q in by.items():
            out.append(f"| {s} | {LABELS[m]} | {q['brier']:.4f} [{q['brier_ci_low']:.4f}, {q['brier_ci_high']:.4f}] | "
                       f"{q['brier_base_rate']:.4f} | {q['skill']:+.3f} | {q['log_loss']:.4f} | {q['ece']:.4f} |")
    out += ["", "| Set | Comparison | Brier difference [95% CI] | Sign-flip p |", "|---|---|---|---|"]
    for e in summary["paired_brier"]:
        out.append(f"| {e['dataset']} | {e['comparison']} | {e['mean_difference']:+.4f} [{e['ci_low']:+.4f}, {e['ci_high']:+.4f}] | {e['sign_flip_p_value']:.4f} |")
    inf = summary["inferred_faults"]
    out += ["", f"Inferred number of faults: AUC for separating multi-fault from single-fault programs {inf['auc_multi_vs_single']:.3f}; "
            f"mean by true count {', '.join(f'{k}: {v:.2f}' for k, v in inf['mean_by_true_count'].items())}.", "",
            f"Whole run: {summary['cost']['total_seconds'] / 60:.0f} minutes.", ""]
    return "\n".join(out)


def write_all(path: Path) -> None:
    summary = build_summary(path)
    (path / "summary.json").write_text(json.dumps(summary, indent=1, sort_keys=True), encoding="utf-8", newline="\n")
    write_tables(path, summary)
    write_figures(path, summary)
    (path / "SUMMARY.md").write_text(build_markdown(summary), encoding="utf-8", newline="\n")
