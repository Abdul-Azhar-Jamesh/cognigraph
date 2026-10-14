"""Derived outputs of the version 4 experiments.

Reads the raw outputs of ``pcg.v4`` (``per_case.csv``, ``per_case_secondary.csv``,
``probabilities.jsonl``, ``truncation_check.json``, ``cost.json``) and writes
``summary.json``, the tables under ``tables/``, the figures under ``figures/``
(PNG and PDF) and ``SUMMARY.md``. It can be re-run on an existing results
folder: ``python -m pcg v4-report``.
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

LABELS = {
    "ochiai": "Ochiai", "tarantula": "Tarantula", "barinel": "Barinel", "flitsr": "FLITSR", "flitsr_star": "FLITSR*",
    "metallaxis": "Metallaxis", "muse": "MUSE", "hybrid_avg": "Hybrid average", "lr_spectrum": "Logistic, spectrum",
    "lr_fusion": "Logistic fusion", "pcg_size": "PCG spectrum only", "pcg_fused": "PCG v3 fused",
    "iv": "IV (proposed)", "iv_composite": "IV, composite layer", "iv_c1": "IV, at most 1 fault",
    "iv_c2": "IV, at most 2 faults", "iv_spectrum": "IV, no variants", "iv_half": "IV, extra-fault odds x 0.5",
    "iv_quarter": "IV, extra-fault odds x 0.25",
}
MAIN = ("ochiai", "tarantula", "barinel", "flitsr", "flitsr_star", "metallaxis", "muse", "hybrid_avg", "lr_spectrum",
        "lr_fusion", "pcg_size", "pcg_fused", "iv")
ABLATIONS = ("iv", "iv_composite", "iv_c1", "iv_c2", "iv_spectrum", "iv_half", "iv_quarter")
PROB = ("lr_fusion", "pcg_size", "pcg_fused", "iv", "iv_composite", "iv_c1")
KEYS = ("ap", "first_top1", "first_top3", "all_top3", "all_top5", "mean_rank")
H1_BASELINES = ("pcg_fused", "pcg_size", "muse", "flitsr_star", "lr_fusion")
MIXES = {"D1-mix": ("D1-1", "D1-2"), "Q-mix": ("Q1", "Q2", "Q3"), "E-mix": ("E1", "E2", "E3")}
DATASET_NOTE = {
    "D1-1": "development, 1 injected fault", "D1-2": "development, 2 injected faults",
    "QH": "QuixBugs human-written bugs", "Q1": "QuixBugs, 1 injected fault", "Q2": "QuixBugs, 2 injected faults",
    "Q3": "QuixBugs, 3 injected faults", "QHM": "QuixBugs human bug + 1 injected fault",
    "EH": "HumanEvalFix human-written bugs", "E1": "HumanEval, 1 injected fault", "E2": "HumanEval, 2 injected faults",
    "E3": "HumanEval, 3 injected faults", "EHM": "HumanEvalFix human bug + 1 injected fault",
}
COLORS = {"iv": "#c0392b", "pcg_fused": "#2c7fb8", "pcg_size": "#7fcdbb", "muse": "#e6a020", "flitsr_star": "#6a51a3",
          "lr_fusion": "#4d4d4d", "ochiai": "#9e9e9e", "metallaxis": "#b8860b", "barinel": "#8c6d31",
          "hybrid_avg": "#bdbdbd"}


def _read_csv(path: Path) -> list[dict]:
    rows = []
    with path.open(encoding="utf-8", newline="") as handle:
        for raw in csv.DictReader(handle):
            row = {}
            for key, value in raw.items():
                if key in ("dataset", "condition", "program", "case_id"):
                    row[key] = value
                else:
                    row[key] = float(value) if value not in ("", None) else float("nan")
            rows.append(row)
    return rows


def _holm(p_values: Sequence[float]) -> list[float]:
    order = np.argsort(p_values)
    adjusted, running = [0.0] * len(p_values), 0.0
    for rank, index in enumerate(order):
        running = max(running, (len(p_values) - rank) * p_values[index])
        adjusted[index] = min(1.0, running)
    return adjusted


def _program_means(rows: Sequence[dict], key: str) -> dict[str, float]:
    sums: dict[str, list[float]] = {}
    for row in rows:
        sums.setdefault(row["program"], []).append(row[key])
    return {program: float(np.mean(values)) for program, values in sums.items()}


def _bootstrap_mean(values: np.ndarray, seed: int = config.SEED) -> tuple[float, float]:
    rng = np.random.default_rng(seed)
    draws = rng.integers(0, len(values), size=(config.BOOTSTRAP_RESAMPLES, len(values)))
    means = values[draws].mean(axis=1)
    return float(np.percentile(means, 2.5)), float(np.percentile(means, 97.5))


def _quality(records: Sequence[dict], method: str) -> dict:
    p = np.concatenate([np.asarray(r[method], dtype=float) for r in records])
    y = np.concatenate([np.asarray(r["labels"], dtype=float) for r in records])
    base = np.concatenate([np.full(len(r["labels"]), sum(r["labels"]) / len(r["labels"])) for r in records])
    clusters = [r["program"] for r in records for _ in r["labels"]]
    low, high = metrics.cluster_bootstrap_ci((p - y) ** 2, clusters)
    return {"statements": int(len(y)), "faulty": int(y.sum()), "brier": metrics.brier_score(p, y),
            "brier_ci_low": low, "brier_ci_high": high, "brier_base_rate": metrics.brier_score(base, y),
            "skill": metrics.brier_skill(p, y, base), "log_loss": metrics.log_loss(p, y),
            "log_loss_base_rate": metrics.log_loss(base, y), "ece": metrics.expected_calibration_error(p, y),
            "reliability": metrics.reliability_table(p, y)}


def _paired_brier(records: Sequence[dict], a: str, b: str) -> dict:
    pa = np.concatenate([np.asarray(r[a], dtype=float) for r in records])
    pb = np.concatenate([np.asarray(r[b], dtype=float) for r in records])
    y = np.concatenate([np.asarray(r["labels"], dtype=float) for r in records])
    clusters = [r["program"] for r in records for _ in r["labels"]]
    diff = (pa - y) ** 2 - (pb - y) ** 2
    sums, counts, _ = metrics.cluster_means(diff, clusters)
    low, high = metrics.cluster_bootstrap_ci(diff, clusters)
    return {"comparison": f"{a} - {b}", "metric": "brier (lower is better)", "mean_difference": float(diff.mean()),
            "ci_low": low, "ci_high": high, "sign_flip_p_value": metrics.paired_sign_flip_test(sums / counts)}


def build_summary(path: Path) -> dict:
    rows = _read_csv(path / "per_case.csv")
    secondary = _read_csv(path / "per_case_secondary.csv")
    records = [json.loads(line) for line in (path / "probabilities.jsonl").read_text(encoding="utf-8").splitlines()]
    truncation = json.loads((path / "truncation_check.json").read_text(encoding="utf-8"))
    by_set: dict[str, list[dict]] = {}
    for row in rows:
        by_set.setdefault(row["dataset"], []).append(row)
    for mix, parts in MIXES.items():
        by_set[mix] = [row for part in parts for row in by_set.get(part, [])]
    records_by_set: dict[str, list[dict]] = {}
    for record in records:
        records_by_set.setdefault(record["dataset"], []).append(record)
    for mix, parts in MIXES.items():
        records_by_set[mix] = [r for part in parts for r in records_by_set.get(part, [])]
    methods = [m for m in LABELS if f"{m}.ap" in rows[0]]

    summary: dict = {"datasets": {}, "ranking": {}, "calibration": {}, "selective": {}, "hypotheses": {}}
    for name, subset in by_set.items():
        summary["datasets"][name] = {
            "cases": len(subset), "programs": len({r["program"] for r in subset}),
            "mean_statements": float(np.mean([r["n_statements"] for r in subset])),
            "mean_failing_tests": float(np.mean([r["n_failed"] for r in subset])),
            "mean_tests": float(np.mean([r["n_tests"] for r in subset])),
            "share_all_faults_with_restoring_variant": float(np.mean(
                [r["faults_with_restoring_variant"] >= r["n_faults"] for r in subset])),
            "mean_expected_faults": float(np.mean([r["expected_faults"] for r in subset])),
            "mean_boundary_mass": float(np.mean([r["boundary_mass"] for r in subset]))}
        summary["ranking"][name] = ex._aggregate(subset, methods, KEYS + ("first_rr",))

    # H1: mean average precision on two-fault sets
    h1 = [dict(ex._paired(by_set[d], "iv", b, "ap"), dataset=d) for d in ("Q2", "E2") for b in H1_BASELINES]
    for entry, adjusted in zip(h1, _holm([e["sign_flip_p_value"] for e in h1])):
        entry["holm_p_value"] = adjusted
        entry["supported"] = bool(entry["ci_low"] > 0 and adjusted < 0.05)
    summary["hypotheses"]["H1"] = h1
    summary["hypotheses"]["H1_development"] = [dict(ex._paired(by_set["D1-2"], "iv", b, "ap"), dataset="D1-2")
                                               for b in H1_BASELINES]
    # H2: single-fault cost
    h2 = [dict(ex._paired(by_set[d], "iv", "pcg_fused", "first_top1"), dataset=d) for d in ("D1-1", "Q1", "E1")]
    for entry in h2:
        entry["supported"] = bool(entry["ci_low"] > -0.02)
    summary["hypotheses"]["H2"] = h2
    # H3: human-written bugs
    h3 = [dict(ex._paired(by_set[d], "iv", b, "first_rr"), dataset=d)
          for d in ("EH", "QH") for b in ("pcg_size", "pcg_fused", "lr_fusion", "ochiai")]
    for entry in h3:
        entry["supported"] = bool(entry["ci_low"] > 0)
    summary["hypotheses"]["H3"] = h3
    # H4: unknown number of faults, programs weighted equally
    h4 = {}
    for mix in ("Q-mix", "E-mix", "D1-mix"):
        means = {m: _program_means(by_set[mix], f"{m}.ap") for m in MAIN}
        programs = sorted(means["iv"])
        table = {m: float(np.mean([means[m][p] for p in programs])) for m in MAIN}
        order = sorted(table, key=table.get, reverse=True)
        runner_up = next(m for m in order if m != "iv")
        diff = np.array([means["iv"][p] - means[runner_up][p] for p in programs])
        low, high = _bootstrap_mean(diff)
        h4[mix] = {"programs": len(programs), "program_weighted_map": table, "order": order, "best_other": runner_up,
                   "difference_to_best_other": float(diff.mean()), "ci_low": low, "ci_high": high,
                   "sign_flip_p_value": metrics.paired_sign_flip_test(diff),
                   "supported": bool(order[0] == "iv" and low > 0)}
    summary["hypotheses"]["H4"] = h4
    # H5 and calibration tables
    for name, subset in records_by_set.items():
        summary["calibration"][name] = {m: _quality(subset, m) for m in PROB if m in subset[0]}
    summary["hypotheses"]["H5"] = {
        "skill_of_iv": {name: summary["calibration"][name]["iv"]["skill"] for name in summary["calibration"]},
        "paired_brier": [dict(_paired_brier(records_by_set[d], "iv", b), dataset=d)
                         for d in ("D1-2", "Q2", "E2", "Q3", "E3", "Q1", "E1", "QH", "EH")
                         for b in ("pcg_fused", "lr_fusion")]}
    held_out = [name for name in summary["calibration"] if not name.startswith("D1")]
    summary["hypotheses"]["H5"]["supported"] = bool(
        all(summary["calibration"][name]["iv"]["skill"] > 0 for name in held_out)
        and all(e["ci_high"] < 0 for e in summary["hypotheses"]["H5"]["paired_brier"]
                if e["dataset"] in ("Q2", "E2") and e["comparison"].endswith("pcg_fused")))
    # H6
    differences = np.array([t["max_abs_difference"] for t in truncation])
    summary["hypotheses"]["H6"] = {
        "cases": len(truncation), "share_below_0.05": float(np.mean(differences < 0.05)),
        "median_difference": float(np.median(differences)), "p95_difference": float(np.percentile(differences, 95)),
        "max_difference": float(differences.max()),
        "share_same_top_statement": float(np.mean([t["same_top_statement"] for t in truncation])),
        "mean_mass_on_four_faults": float(np.mean([t["mass_on_four_faults"] for t in truncation])),
        "supported": bool(np.mean(differences < 0.05) >= 0.95)}
    # H7
    h7 = {}
    for mix in ("Q-mix", "E-mix", "D1-mix"):
        subset = by_set[mix]
        scores = np.array([r["expected_faults"] for r in subset])
        multi = np.array([r["n_faults"] > 1 for r in subset])
        programs = sorted({r["program"] for r in subset})
        index = {p: [i for i, r in enumerate(subset) if r["program"] == p] for p in programs}
        rng = np.random.default_rng(config.SEED)
        draws = []
        for _ in range(1000):
            chosen = np.concatenate([index[programs[int(i)]] for i in rng.integers(0, len(programs), len(programs))])
            value = metrics.roc_auc(scores[chosen], multi[chosen])
            if not np.isnan(value):
                draws.append(value)
        h7[mix] = {"auc": metrics.roc_auc(scores, multi), "ci_low": float(np.percentile(draws, 2.5)),
                   "ci_high": float(np.percentile(draws, 97.5)),
                   "mean_expected_faults_by_true_count": {
                       str(int(k)): float(np.mean([r["expected_faults"] for r in subset if r["n_faults"] == k]))
                       for k in sorted({r["n_faults"] for r in subset})}}
        h7[mix]["supported"] = bool(h7[mix]["ci_low"] > 0.5)
    summary["hypotheses"]["H7"] = h7

    # selective localisation
    for name in ("Q-mix", "E-mix", "EH", "QH", "D1-mix"):
        subset = by_set[name]
        table = {}
        for m in ("iv", "pcg_fused", "lr_fusion", "pcg_size", "muse", "flitsr_star"):
            confidence = np.array([r[f"{m}.confidence"] for r in subset])
            correct = np.array([r[f"{m}.first_top1"] for r in subset])
            reference = metrics.aurc_reference_values(correct)
            coverage, risk = metrics.risk_coverage(confidence, correct)
            table[m] = {"error_rate": float(1 - correct.mean()), "aurc": metrics.aurc(confidence, correct),
                        **{f"aurc_{k}": v for k, v in reference.items()},
                        "curve": {"coverage": np.round(coverage, 4).tolist(), "risk": np.round(risk, 4).tolist()}}
        summary["selective"][name] = table

    # breakdowns
    summary["by_restoring_variant"] = {}
    for name in ("D1-2", "Q2", "E2"):
        split = {}
        for label, keep in (("all faults have a restoring variant", lambda r: r["faults_with_restoring_variant"] >= r["n_faults"]),
                            ("at least one fault has none", lambda r: r["faults_with_restoring_variant"] < r["n_faults"])):
            subset = [r for r in by_set[name] if keep(r)]
            if subset:
                split[label] = {"cases": len(subset), **{m: float(np.mean([r[f"{m}.ap"] for r in subset]))
                                                          for m in ("iv", "pcg_fused", "pcg_size", "muse", "flitsr_star", "lr_fusion")}}
        summary["by_restoring_variant"][name] = split
    summary["human_bugs_by_restoring_variant"] = {}
    for name in ("QH", "EH"):
        split = {}
        for label, keep in (("has a restoring variant", lambda r: r["faults_with_restoring_variant"] >= 1),
                            ("has none", lambda r: r["faults_with_restoring_variant"] < 1)):
            subset = [r for r in by_set[name] if keep(r)]
            if subset:
                split[label] = {"cases": len(subset), **{m: float(np.mean([r[f"{m}.first_rr"] for r in subset]))
                                                          for m in ("iv", "pcg_fused", "pcg_size", "muse", "ochiai", "lr_fusion")}}
        summary["human_bugs_by_restoring_variant"][name] = split

    # secondary conditions (HumanEvalFix)
    second: dict = {}
    for row in secondary:
        second.setdefault((row["condition"], row["dataset"]), []).append(row)
    summary["secondary"] = {}
    for (condition, dataset), subset in sorted(second.items()):
        transfer = {r["case_id"]: r for r in by_set[dataset]}
        entry = {"cases": len(subset), "methods": {}}
        for m in ("iv", "pcg_fused", "lr_fusion", "pcg_size"):
            values = np.array([r[f"{m}.ap"] for r in subset])
            reference = np.array([transfer[r["case_id"]][f"{m}.ap"] for r in subset])
            clusters = [r["program"] for r in subset]
            low, high = metrics.cluster_bootstrap_ci(values - reference, clusters)
            entry["methods"][m] = {"map": float(values.mean()), "map_transfer": float(reference.mean()),
                                   "difference": float((values - reference).mean()), "ci_low": low, "ci_high": high,
                                   "first_top1": float(np.mean([r[f"{m}.first_top1"] for r in subset]))}
        summary["secondary"][f"{condition}:{dataset}"] = entry
    summary["cost"] = json.loads((path / "cost.json").read_text(encoding="utf-8"))
    return summary


# ----------------------------------------------------------------------------
# Tables
# ----------------------------------------------------------------------------

def _write_csv(path: Path, header: Sequence[str], rows: Sequence[Sequence]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(header)
        writer.writerows(rows)


def write_tables(path: Path, summary: dict) -> None:
    tables = path / "tables"
    tables.mkdir(exist_ok=True)
    rows = []
    for dataset, by_method in summary["ranking"].items():
        for method, values in by_method.items():
            rows.append([dataset, method, LABELS[method]] + [f"{values[k][s]:.4f}" for k in KEYS for s in ("mean", "ci_low", "ci_high")])
    _write_csv(tables / "ranking_all.csv", ["dataset", "method", "label"] + [f"{k}_{s}" for k in KEYS for s in ("mean", "ci_low", "ci_high")], rows)
    rows = [[d, m, LABELS[m], q["statements"], q["faulty"], f"{q['brier']:.5f}", f"{q['brier_ci_low']:.5f}",
             f"{q['brier_ci_high']:.5f}", f"{q['brier_base_rate']:.5f}", f"{q['skill']:.4f}", f"{q['log_loss']:.5f}",
             f"{q['log_loss_base_rate']:.5f}", f"{q['ece']:.5f}"]
            for d, by_method in summary["calibration"].items() for m, q in by_method.items()]
    _write_csv(tables / "calibration_all.csv", ["dataset", "method", "label", "statements", "faulty", "brier", "brier_ci_low",
                                                "brier_ci_high", "brier_base_rate", "skill", "log_loss",
                                                "log_loss_base_rate", "ece"], rows)
    rows = []
    for key in ("H1", "H1_development", "H2", "H3"):
        for e in summary["hypotheses"][key]:
            rows.append([key, e["dataset"], e["comparison"], e["metric"], f"{e['mean_difference']:.4f}", f"{e['ci_low']:.4f}",
                         f"{e['ci_high']:.4f}", f"{e['sign_flip_p_value']:.5f}", f"{e.get('holm_p_value', float('nan')):.5f}",
                         e.get("supported", "")])
    for e in summary["hypotheses"]["H5"]["paired_brier"]:
        rows.append(["H5", e["dataset"], e["comparison"], e["metric"], f"{e['mean_difference']:.5f}", f"{e['ci_low']:.5f}",
                     f"{e['ci_high']:.5f}", f"{e['sign_flip_p_value']:.5f}", "", ""])
    _write_csv(tables / "paired_comparisons.csv", ["hypothesis", "dataset", "comparison", "metric", "mean_difference",
                                                   "ci_low", "ci_high", "sign_flip_p", "holm_p", "supported"], rows)


# ----------------------------------------------------------------------------
# Figures
# ----------------------------------------------------------------------------

def _style() -> None:
    plt.rcParams.update({"font.size": 9, "axes.spines.top": False, "axes.spines.right": False, "axes.grid": True,
                         "grid.alpha": 0.25, "grid.linewidth": 0.6, "legend.frameon": False, "figure.dpi": 120,
                         "savefig.dpi": 300, "savefig.bbox": "tight", "font.family": "DejaVu Sans"})


def _save(fig, folder: Path, name: str) -> None:
    for suffix in ("png", "pdf"):
        fig.savefig(folder / f"{name}.{suffix}", metadata={"CreationDate": None} if suffix == "pdf" else {"Software": None})
    plt.close(fig)


def _bars(ax, ranking: dict, methods: Sequence[str], key: str, title: str, xlabel: str) -> None:
    order = sorted(methods, key=lambda m: ranking[m][key]["mean"])
    means = [ranking[m][key]["mean"] for m in order]
    low = [ranking[m][key]["mean"] - ranking[m][key]["ci_low"] for m in order]
    high = [ranking[m][key]["ci_high"] - ranking[m][key]["mean"] for m in order]
    colors = [COLORS.get(m, "#bdbdbd") if m in ("iv", "pcg_fused") else "#b0b0b0" for m in order]
    ax.barh(range(len(order)), means, xerr=[low, high], color=colors, error_kw={"elinewidth": 0.8, "capsize": 2})
    ax.set_yticks(range(len(order)))
    ax.set_yticklabels([LABELS[m] for m in order])
    ax.set_xlabel(xlabel)
    ax.set_title(title, loc="left", fontsize=9, fontweight="bold")
    ax.grid(axis="y", visible=False)
    for i, value in enumerate(means):
        ax.text(value + high[i] + 0.01, i, f"{value:.2f}", va="center", fontsize=7)
    ax.set_xlim(0, 1.08)


def write_figures(path: Path, summary: dict) -> None:
    _style()
    folder = path / "figures"
    folder.mkdir(exist_ok=True)
    ranking, calibration = summary["ranking"], summary["calibration"]

    # 1. two-fault programs: mean average precision of every method
    fig, axes = plt.subplots(1, 3, figsize=(13, 4.2), sharex=True)
    for ax, name in zip(axes, ("D1-2", "Q2", "E2")):
        _bars(ax, ranking[name], MAIN, "ap", f"{name}: {DATASET_NOTE[name]} (n = {summary['datasets'][name]['cases']})",
              "mean average precision (95% interval)")
    fig.suptitle("Two faults: mean average precision by method", x=0.01, ha="left", fontsize=11)
    fig.tight_layout()
    _save(fig, folder, "fig1_two_fault_map")

    # 2. the trade-off: one fault against two faults
    fig, axes = plt.subplots(1, 3, figsize=(13, 4.2), sharex=True, sharey=True)
    for ax, (single, double) in zip(axes, (("D1-1", "D1-2"), ("Q1", "Q2"), ("E1", "E2"))):
        for m in MAIN:
            x, y = ranking[single][m]["first_top1"]["mean"], ranking[double][m]["ap"]["mean"]
            ax.scatter(x, y, s=42 if m in ("iv", "pcg_fused") else 22, color=COLORS.get(m, "#9e9e9e"), zorder=3)
            ax.annotate(LABELS[m], (x, y), textcoords="offset points", xytext=(4, 3), fontsize=6.5)
        ax.set_title(f"{single} and {double}", loc="left", fontsize=9, fontweight="bold")
        ax.set_xlabel("one fault: Top-1")
    axes[0].set_ylabel("two faults: mean average precision")
    fig.suptitle("Each method on single-fault and on two-fault programs (upper right is better)", x=0.01, ha="left", fontsize=11)
    fig.tight_layout()
    _save(fig, folder, "fig2_single_vs_two_fault")

    # 3. mean average precision by number of faults
    fig, axes = plt.subplots(1, 2, figsize=(9.5, 3.8), sharey=True)
    for ax, prefix in zip(axes, ("Q", "E")):
        for m in ("iv", "pcg_fused", "pcg_size", "muse", "flitsr_star", "lr_fusion"):
            values = [ranking[f"{prefix}{k}"][m]["ap"] for k in (1, 2, 3)]
            ax.errorbar([1, 2, 3], [v["mean"] for v in values],
                        yerr=[[v["mean"] - v["ci_low"] for v in values], [v["ci_high"] - v["mean"] for v in values]],
                        marker="o", markersize=4, linewidth=1.6 if m == "iv" else 1.0, color=COLORS[m], label=LABELS[m], capsize=2)
        ax.set_xticks([1, 2, 3])
        ax.set_xlabel("number of injected faults")
        ax.set_title({"Q": "QuixBugs programs", "E": "HumanEval programs"}[prefix], loc="left", fontsize=9, fontweight="bold")
    axes[0].set_ylabel("mean average precision")
    axes[1].legend(fontsize=7, loc="lower left")
    fig.tight_layout()
    _save(fig, folder, "fig3_map_by_fault_count")

    # 4. reliability
    fig, axes = plt.subplots(1, 3, figsize=(12, 3.9), sharex=True, sharey=True)
    for ax, name in zip(axes, ("E-mix", "Q-mix", "EH")):
        ax.plot([0, 1], [0, 1], color="#555555", linewidth=0.8, linestyle="--")
        for m in ("iv", "pcg_fused", "lr_fusion"):
            table = [b for b in calibration[name][m]["reliability"] if b["count"] > 0]
            ax.plot([b["mean_predicted"] for b in table], [b["observed_frequency"] for b in table], marker="o",
                    markersize=3.5, color=COLORS[m], linewidth=1.2,
                    label=f"{LABELS[m]} (ECE {calibration[name][m]['ece']:.3f})")
        ax.set_title(f"{name}", loc="left", fontsize=9, fontweight="bold")
        ax.set_xlabel("predicted probability of being faulty")
        ax.legend(fontsize=7, loc="upper left")
    axes[0].set_ylabel("observed share of faulty statements")
    fig.tight_layout()
    _save(fig, folder, "fig4_reliability")

    # 5. risk-coverage
    fig, axes = plt.subplots(1, 3, figsize=(12, 3.9), sharey=True)
    for ax, name in zip(axes, ("E-mix", "Q-mix", "EH")):
        for m in ("iv", "pcg_fused", "lr_fusion", "muse"):
            curve = summary["selective"][name][m]["curve"]
            ax.plot(curve["coverage"], curve["risk"], color=COLORS[m], linewidth=1.4 if m == "iv" else 1.0,
                    label=f"{LABELS[m]} (AURC {summary['selective'][name][m]['aurc']:.3f})")
        ax.set_title(name, loc="left", fontsize=9, fontweight="bold")
        ax.set_xlabel("share of programs answered (most confident first)")
        ax.legend(fontsize=7)
    axes[0].set_ylabel("share of answers whose top statement is not faulty")
    fig.tight_layout()
    _save(fig, folder, "fig5_risk_coverage")

    # 6. ablations
    fig, axes = plt.subplots(1, 4, figsize=(14, 3.4), sharey=True)
    for ax, (name, key, label) in zip(axes, (("Q2", "ap", "MAP"), ("E2", "ap", "MAP"), ("Q1", "first_top1", "Top-1"), ("E1", "first_top1", "Top-1"))):
        values = [ranking[name][m][key] for m in ABLATIONS]
        ax.barh(range(len(ABLATIONS)), [v["mean"] for v in values],
                xerr=[[v["mean"] - v["ci_low"] for v in values], [v["ci_high"] - v["mean"] for v in values]],
                color=[COLORS["iv"] if m == "iv" else "#b0b0b0" for m in ABLATIONS], error_kw={"elinewidth": 0.8, "capsize": 2})
        ax.set_yticks(range(len(ABLATIONS)))
        ax.set_yticklabels([LABELS[m] for m in ABLATIONS])
        ax.invert_yaxis()
        ax.set_title(f"{name}: {label}", loc="left", fontsize=9, fontweight="bold")
        ax.grid(axis="y", visible=False)
    fig.tight_layout()
    _save(fig, folder, "fig6_ablations")

    # 7. inferred number of faults
    rows = _read_csv(path / "per_case.csv")
    fig, axes = plt.subplots(1, 2, figsize=(9.5, 3.6), sharey=True)
    for ax, prefix in zip(axes, ("Q", "E")):
        data = [[r["expected_faults"] for r in rows if r["dataset"] == f"{prefix}{k}"] for k in (1, 2, 3)]
        ax.boxplot(data, tick_labels=["1", "2", "3"], showfliers=False, medianprops={"color": COLORS["iv"]})
        ax.plot([1, 2, 3], [1, 2, 3], color="#555555", linestyle="--", linewidth=0.8)
        ax.set_xlabel("true number of faults")
        ax.set_title({"Q": "QuixBugs programs", "E": "HumanEval programs"}[prefix] +
                     f" (AUC {summary['hypotheses']['H7'][prefix + '-mix']['auc']:.2f})", loc="left", fontsize=9, fontweight="bold")
    axes[0].set_ylabel("posterior expected number of faults")
    fig.tight_layout()
    _save(fig, folder, "fig7_inferred_fault_count")

    # 8. human-written bugs
    fig, axes = plt.subplots(1, 2, figsize=(10, 4.2), sharex=True)
    for ax, name in zip(axes, ("EH", "QH")):
        _bars(ax, ranking[name], MAIN, "first_rr", f"{name}: {DATASET_NOTE[name]} (n = {summary['datasets'][name]['cases']})",
              "mean reciprocal rank (95% interval)")
    fig.tight_layout()
    _save(fig, folder, "fig8_human_bugs")


# ----------------------------------------------------------------------------
# SUMMARY.md
# ----------------------------------------------------------------------------

def _cell(v: dict, digits: int = 3) -> str:
    return f"{v['mean']:.{digits}f} [{v['ci_low']:.{digits}f}, {v['ci_high']:.{digits}f}]"


def build_markdown(summary: dict) -> str:
    out = ["# Version 4 results (generated)", "",
           "Generated by `pcg.v4_report` from the raw outputs in this folder. Do not edit by hand.",
           "Intervals are 95% cluster-bootstrap intervals with the program as the unit.", "", "## 1. Data sets", "",
           "| Set | Content | Cases scored | Programs | Mean statements | Mean failing / all tests | All faults have a restoring variant |",
           "|---|---|---|---|---|---|---|"]
    for name, d in summary["datasets"].items():
        out.append(f"| {name} | {DATASET_NOTE.get(name, 'union of ' + ', '.join(MIXES.get(name, ())))} | {d['cases']} | {d['programs']} | "
                   f"{d['mean_statements']:.1f} | {d['mean_failing_tests']:.1f} / {d['mean_tests']:.1f} | "
                   f"{d['share_all_faults_with_restoring_variant']:.2f} |")
    section = 2
    for name in ("D1-1", "D1-2", "Q1", "Q2", "Q3", "QH", "QHM", "E1", "E2", "E3", "EH", "EHM", "Q-mix", "E-mix"):
        out += ["", f"## {section}. {name}: {DATASET_NOTE.get(name, 'pooled sets, number of faults unknown')}", "",
                "| Method | MAP | First fault Top-1 | First fault Top-3 | All faults in top 3 | Mean rank of faults |", "|---|---|---|---|---|---|"]
        for m in MAIN + tuple(a for a in ABLATIONS if a != "iv"):
            r = summary["ranking"][name][m]
            out.append(f"| {LABELS[m]} | {_cell(r['ap'])} | {_cell(r['first_top1'])} | {_cell(r['first_top3'])} | "
                       f"{_cell(r['all_top3'])} | {r['mean_rank']['mean']:.2f} |")
        section += 1
    h = summary["hypotheses"]
    out += ["", f"## {section}. Hypotheses", "", "### H1: two faults, IV against each baseline (mean average precision)", "",
            "| Set | Comparison | Difference [95% CI] | Sign-flip p | Holm p | Supported |", "|---|---|---|---|---|---|"]
    for e in h["H1"]:
        out.append(f"| {e['dataset']} | {e['comparison']} | {e['mean_difference']:+.3f} [{e['ci_low']:+.3f}, {e['ci_high']:+.3f}] | "
                   f"{e['sign_flip_p_value']:.4f} | {e['holm_p_value']:.4f} | {'yes' if e['supported'] else 'no'} |")
    out += ["", "Development set, for reference (not a test):", "", "| Set | Comparison | Difference [95% CI] |", "|---|---|---|"]
    for e in h["H1_development"]:
        out.append(f"| {e['dataset']} | {e['comparison']} | {e['mean_difference']:+.3f} [{e['ci_low']:+.3f}, {e['ci_high']:+.3f}] |")
    out += ["", "### H2: one fault, IV minus PCG v3 fused (Top-1); supported if the interval stays above -0.02", "",
            "| Set | Difference [95% CI] | Supported |", "|---|---|---|"]
    for e in h["H2"]:
        out.append(f"| {e['dataset']} | {e['mean_difference']:+.3f} [{e['ci_low']:+.3f}, {e['ci_high']:+.3f}] | {'yes' if e['supported'] else 'no'} |")
    out += ["", "### H3: human-written bugs, IV against other methods (reciprocal rank of the best-ranked fault line)", "",
            "| Set | Comparison | Difference [95% CI] | Sign-flip p | Interval excludes zero |", "|---|---|---|---|---|"]
    for e in h["H3"]:
        out.append(f"| {e['dataset']} | {e['comparison']} | {e['mean_difference']:+.3f} [{e['ci_low']:+.3f}, {e['ci_high']:+.3f}] | "
                   f"{e['sign_flip_p_value']:.4f} | {'yes' if e['supported'] else 'no'} |")
    out += ["", "### H4: number of faults unknown (programs weighted equally)", "",
            "| Set | Programs | Best method | IV | Best other | IV minus best other [95% CI] | Supported |", "|---|---|---|---|---|---|---|"]
    for name, e in h["H4"].items():
        out.append(f"| {name} | {e['programs']} | {LABELS[e['order'][0]]} | {e['program_weighted_map']['iv']:.3f} | "
                   f"{LABELS[e['best_other']]} {e['program_weighted_map'][e['best_other']]:.3f} | "
                   f"{e['difference_to_best_other']:+.3f} [{e['ci_low']:+.3f}, {e['ci_high']:+.3f}] | {'yes' if e['supported'] else 'no'} |")
    out += ["", "### H5: probabilities", "",
            "| Set | Method | Brier [95% CI] | Base-rate Brier | Skill | Log loss | Base-rate log loss | ECE |", "|---|---|---|---|---|---|---|---|"]
    for name, by_method in summary["calibration"].items():
        for m, q in by_method.items():
            out.append(f"| {name} | {LABELS[m]} | {q['brier']:.4f} [{q['brier_ci_low']:.4f}, {q['brier_ci_high']:.4f}] | "
                       f"{q['brier_base_rate']:.4f} | {q['skill']:+.3f} | {q['log_loss']:.4f} | {q['log_loss_base_rate']:.4f} | {q['ece']:.4f} |")
    out += ["", "| Set | Comparison | Brier difference [95% CI] | Sign-flip p |", "|---|---|---|---|"]
    for e in h["H5"]["paired_brier"]:
        out.append(f"| {e['dataset']} | {e['comparison']} | {e['mean_difference']:+.4f} [{e['ci_low']:+.4f}, {e['ci_high']:+.4f}] | {e['sign_flip_p_value']:.4f} |")
    out += ["", f"H5 supported as stated: {'yes' if h['H5']['supported'] else 'no'}.", "",
            "### H6: at most three against at most four faults", "",
            f"{h['H6']['cases']} sampled two-fault cases: largest marginal difference below 0.05 in "
            f"{100 * h['H6']['share_below_0.05']:.0f}% of cases (median {h['H6']['median_difference']:.4f}, 95th percentile "
            f"{h['H6']['p95_difference']:.4f}, maximum {h['H6']['max_difference']:.4f}); same top statement in "
            f"{100 * h['H6']['share_same_top_statement']:.0f}%; mean posterior mass on four faults "
            f"{h['H6']['mean_mass_on_four_faults']:.4f}. Supported: {'yes' if h['H6']['supported'] else 'no'}.", "",
            "### H7: does the posterior expected number of faults separate multi-fault from single-fault programs?", "",
            "| Set | AUC [95% CI] | Mean expected faults when the truth is 1 / 2 / 3 | Supported |", "|---|---|---|---|"]
    for name, e in h["H7"].items():
        by = e["mean_expected_faults_by_true_count"]
        out.append(f"| {name} | {e['auc']:.3f} [{e['ci_low']:.3f}, {e['ci_high']:.3f}] | "
                   f"{' / '.join(f'{by[k]:.2f}' for k in sorted(by))} | {'yes' if e['supported'] else 'no'} |")
    section += 1
    out += ["", f"## {section}. Selective localisation", "",
            "| Set | Confidence and answers of | Error rate | AURC | AURC if confidence were useless | AURC of an oracle |", "|---|---|---|---|---|---|"]
    for name, table in summary["selective"].items():
        for m, e in table.items():
            out.append(f"| {name} | {LABELS[m]} | {e['error_rate']:.3f} | {e['aurc']:.3f} | {e['aurc_uninformative']:.3f} | {e['aurc_oracle']:.3f} |")
    section += 1
    out += ["", f"## {section}. Two faults, by whether every fault has a restoring variant (MAP)", "",
            "| Set | Group | Cases | IV | PCG v3 fused | PCG spectrum | MUSE | FLITSR* | Logistic fusion |", "|---|---|---|---|---|---|---|---|---|"]
    for name, split in summary["by_restoring_variant"].items():
        for label, e in split.items():
            out.append(f"| {name} | {label} | {e['cases']} | " + " | ".join(f"{e[m]:.3f}" for m in ("iv", "pcg_fused", "pcg_size", "muse", "flitsr_star", "lr_fusion")) + " |")
    out += ["", "Human-written bugs, by whether a restoring variant exists (MRR):", "",
            "| Set | Group | Cases | IV | PCG v3 fused | PCG spectrum | MUSE | Ochiai | Logistic fusion |", "|---|---|---|---|---|---|---|---|---|"]
    for name, split in summary["human_bugs_by_restoring_variant"].items():
        for label, e in split.items():
            out.append(f"| {name} | {label} | {e['cases']} | " + " | ".join(f"{e[m]:.3f}" for m in ("iv", "pcg_fused", "pcg_size", "muse", "ochiai", "lr_fusion")) + " |")
    section += 1
    out += ["", f"## {section}. Secondary conditions on HumanEvalFix (MAP; difference to the transfer condition)", "",
            "| Condition and set | Cases | Method | MAP | MAP in transfer | Difference [95% CI] |", "|---|---|---|---|---|---|"]
    for name, entry in summary["secondary"].items():
        for m, e in entry["methods"].items():
            out.append(f"| {name} | {entry['cases']} | {LABELS[m]} | {e['map']:.3f} | {e['map_transfer']:.3f} | "
                       f"{e['difference']:+.3f} [{e['ci_low']:+.3f}, {e['ci_high']:+.3f}] |")
    section += 1
    out += ["", f"## {section}. Cost", "", "| Part | Cases | Variants generated | Distinct variants executed | Seconds |", "|---|---|---|---|---|"]
    for name, c in summary["cost"].items():
        if isinstance(c, dict):
            out.append(f"| {name} | {c['cases']} | {c['variants_generated']} | {c['variant_texts_run']} | {c['seconds']:.0f} |")
    out += ["", f"Whole run: {summary['cost']['total_seconds'] / 60:.0f} minutes.", ""]
    return "\n".join(out)


def write_all(path: Path) -> None:
    summary = build_summary(path)
    (path / "summary.json").write_text(json.dumps(summary, indent=1, sort_keys=True), encoding="utf-8", newline="\n")
    write_tables(path, summary)
    write_figures(path, summary)
    (path / "SUMMARY.md").write_text(build_markdown(summary), encoding="utf-8", newline="\n")
