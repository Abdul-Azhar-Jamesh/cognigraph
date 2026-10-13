"""Builds results/research/SUMMARY.md and its figures from the result files only."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Sequence

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

LABELS = {
    "ochiai": "Ochiai", "tarantula": "Tarantula", "barinel": "Barinel", "metallaxis": "Metallaxis", "muse": "MUSE",
    "hybrid_avg": "Hybrid average", "lr_spectrum": "Logistic, spectrum", "lr_fusion": "Logistic fusion",
    "pcg": "PCG v2", "pcg_size": "PCG, size-aware prior", "pcg_fused": "PCG fused (proposed)",
    "pcg_fused_nocontext": "PCG fused, no context", "pcg_fused_const": "PCG fused, constant prior",
    "pcg_fused_recal": "PCG fused, recalibrated", "ochiai_gap": "Ochiai gap",
    "base_rate_1_over_n": "Base rate 1/n", "base_rate_pooled_in_sample": "Base rate pooled (in-sample)",
}
RANK_ORDER = ("ochiai", "tarantula", "barinel", "metallaxis", "muse", "hybrid_avg", "lr_spectrum", "lr_fusion",
              "pcg", "pcg_size", "pcg_fused", "pcg_fused_nocontext", "pcg_fused_const")
PROB_ORDER = ("base_rate_1_over_n", "base_rate_pooled_in_sample", "lr_spectrum", "lr_fusion", "pcg", "pcg_size",
              "pcg_fused", "pcg_fused_nocontext", "pcg_fused_const", "pcg_fused_recal")
CONF_ORDER = ("pcg", "pcg_size", "pcg_fused", "lr_spectrum", "lr_fusion", "ochiai", "ochiai_gap", "metallaxis",
              "hybrid_avg")


def _load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _ci(entry: dict, digits: int = 3) -> str:
    return f"{entry['mean']:.{digits}f} [{entry['ci_low']:.{digits}f}, {entry['ci_high']:.{digits}f}]"


def _p(value: float) -> str:
    return "< 0.0001" if value < 0.0001 else f"{value:.4f}"


def ranking_table(overall: dict, methods: Sequence[str] = RANK_ORDER) -> list[str]:
    lines = ["| Method | Top-1 | Top-3 | MRR |", "|---|---|---|---|"]
    for m in methods:
        if m in overall:
            o = overall[m]
            lines.append(f"| {LABELS[m]} | {_ci(o['top1'])} | {_ci(o['top3'])} | {_ci(o['reciprocal_rank'])} |")
    return lines


def comparison_table(comparisons: Sequence[dict]) -> list[str]:
    lines = ["| Comparison | Metric | Mean difference [95% CI] | Sign-flip p |", "|---|---|---|---|"]
    for c in comparisons:
        lines.append(f"| {c['comparison']} | {c['metric']} | {c['mean_difference']:+.4f} "
                     f"[{c['ci_low']:+.4f}, {c['ci_high']:+.4f}] | {_p(c['sign_flip_p_value'])} |")
    return lines


def probabilistic_table(quality: dict) -> list[str]:
    lines = [f"{quality['n_statements']} statements, {quality['n_faulty']} faulty. Skill is "
             "1 - Brier / Brier(base rate 1/n); positive means better than the base rate.\n",
             "| Method | Brier [95% CI] | Skill | Log loss | ECE |", "|---|---|---|---|---|"]
    for m in PROB_ORDER:
        if m in quality["methods"]:
            q = quality["methods"][m]
            lines.append(f"| {LABELS[m]} | {q['brier']:.4f} [{q['brier_ci_low']:.4f}, {q['brier_ci_high']:.4f}] | "
                         f"{q['skill_vs_1_over_n']:+.3f} | {q['log_loss']:.4f} | {q['ece']:.4f} |")
    return lines


def selective_table(selective: dict) -> list[str]:
    lines = ["| Confidence | Answers scored | Error rate | AURC | Normalised gain | Risk at 50% coverage |",
             "|---|---|---|---|---|---|"]
    for m in CONF_ORDER:
        if m in selective:
            s = selective[m]
            lines.append(f"| {LABELS[m]} | {LABELS[s['answers_scored']]} | {s['aurc_uninformative']:.3f} | "
                         f"{s['aurc']:.3f} | {s['normalised_gain']:+.3f} | {s['risk_at_coverage_50']:.3f} |")
    lines += ["", "| Comparison (first minus second) | AURC difference [95% CI] | Normalised-gain difference [95% CI] |",
              "|---|---|---|"]
    for c in selective.get("comparisons", []):
        lines.append(f"| {c['comparison']} | {c['aurc_difference']:+.3f} [{c['aurc_ci_low']:+.3f}, {c['aurc_ci_high']:+.3f}] | "
                     f"{c['gain_difference']:+.3f} [{c['gain_ci_low']:+.3f}, {c['gain_ci_high']:+.3f}] |")
    return lines


def build_summary(path: Path) -> str:
    loading = _load(path / "external_loading_report.json")
    fusion = _load(path / "fusion_params_pooled.json")
    d1 = _load(path / "d1_ranking.json")
    d1_prob = _load(path / "d1_probabilistic.json")
    d1_sel = _load(path / "d1_selective.json")
    stress = _load(path / "d1_stress_no_inverse.json")
    size = _load(path / "d1_size_prior.json")
    two = _load(path / "d1_two_fault_post_hoc.json")
    d2 = _load(path / "d2_transfer_summary.json")
    d2_in = _load(path / "d2_in_suite_summary.json")
    d3 = _load(path / "d3_transfer_summary.json")
    symptoms = _load(path / "symptoms.json")
    cost = _load(path / "cost.json")
    with open(path / "d1_per_case.csv", newline="", encoding="utf-8") as handle:
        d1_rows = list(csv.DictReader(handle))
    with open(path / "d2_transfer_per_case.csv", newline="", encoding="utf-8") as handle:
        d2_rows = list(csv.DictReader(handle))

    out: list[str] = []
    add = out.append
    add("# Research results (generated file, do not edit)\n")
    add("Produced by `python -m pcg research`. Every number is read from the data files in this directory. "
        "Intervals are 95% bootstrap intervals over programs. No multiple-comparison correction is applied.\n")

    add("## 1. Datasets\n")
    add("| Dataset | Content | Cases evaluated |\n|---|---|---|")
    add(f"| D1 | project benchmark, single-fault mutants, leave-one-program-out | {len(d1_rows)} |")
    add(f"| D2 | QuixBugs, one human-written bug per program | {loading['d2_detected']} of {loading['d2_cases']} |")
    add(f"| D3 | QuixBugs correct programs, sampled mutants | {loading['d3_detected']} detected of {loading['d3_cases']} valid |")
    dropped = {}
    for entry in loading["per_program"]:
        for key, value in entry.get("tests_dropped", {}).items():
            dropped[key] = dropped.get(key, 0) + value
    kept = sum(e.get("tests_kept", 0) for e in loading["per_program"])
    total = sum(e.get("tests_in_benchmark", 0) for e in loading["per_program"])
    add(f"\nQuixBugs: {loading['programs_with_json_tests']} programs have JSON tests, {loading['programs_used']} are used. "
        f"{kept} of {total} tests are kept; dropped: {dropped}. Runs without a result: {len(loading['excluded_runs'])}. "
        f"Fault kinds in D2: {sorted({e.get('fault_kind') for e in loading['per_program'] if e.get('fault_kind')})}.\n")

    add("## 2. Learned mutation-evidence tables (pooled over D1)\n")
    fp = fusion["fusion_params"]
    add("Estimated among statements that every failing test executed (context \"all\").\n")
    add("| Level | 0 no variant | 1 no effect | 2 partial | 3 fixes failing, breaks passing | 4 all tests pass |\n|---|---|---|---|---|---|")
    add("| P(level \\| faulty) | " + " | ".join(f"{v:.4f}" for v in fp["level_given_fault"]) + " |")
    add("| P(level \\| fault-free) | " + " | ".join(f"{v:.4f}" for v in fp["level_given_clean"]) + " |")
    add("| likelihood ratio | " + " | ".join(f"{a / b:.3f}" for a, b in zip(fp["level_given_fault"], fp["level_given_clean"])) + " |")
    add("| ratio without context (ablation) | " + " | ".join(
        f"{a / b:.3f}" for a, b in zip(fp["level_given_fault_nocontext"], fp["level_given_clean_nocontext"])) + " |")
    add(f"\nExpected faults per analysed program, mu = {fp['mu']:.3f}.\n")

    add("## 3. D1: ranking\n")
    out.extend(ranking_table(d1["overall"]))
    add("")
    out.extend(comparison_table(d1["comparisons"]))
    add("\nMRR by fault category:\n")
    add("| Category | n | Ochiai | Metallaxis | Hybrid average | Logistic fusion | PCG size-aware | PCG fused |\n|---|---|---|---|---|---|---|---|")
    for name, row in d1["by_category"].items():
        add(f"| {name} | {row['n']} | " + " | ".join(
            f"{row[m]['reciprocal_rank']:.3f}" for m in ("ochiai", "metallaxis", "hybrid_avg", "lr_fusion", "pcg_size", "pcg_fused")) + " |")
    levels = [int(r["fault_level"]) for r in d1_rows]
    add(f"\nLevel of the faulty statement in D1: " + ", ".join(f"level {v}: {levels.count(v)}" for v in range(5)) +
        ". Level 4 means a variant restores all tests, which on injected faults is usually the exact inverse of the injection.\n")

    add("## 4. D1 stress test: the reference-restoring variant removed\n")
    add("The variant whose text equals the reference program is removed from every mutation analysis, in training and in evaluation. "
        "This uses ground truth to remove information and is a stress test, not a result.\n")
    out.extend(ranking_table(stress["overall"], ("ochiai", "metallaxis", "muse", "hybrid_avg", "lr_fusion", "pcg_size", "pcg_fused")))
    add("")
    out.extend(comparison_table(stress["comparisons"]))
    add("")

    add("## 5. D1: quality of probabilities (detected cases, out-of-fold)\n")
    out.extend(probabilistic_table(d1_prob["quality"]))
    add("")
    out.extend(comparison_table(d1_prob["paired_brier"]))
    slopes = [m["a"] for m in d1_prob["recalibration_maps"].values()]
    add(f"\nRecalibration maps (nested): slope a between {min(slopes):.3f} and {max(slopes):.3f}; "
        f"map fitted on all out-of-fold D1 posteriors for transfer: a = {d1_prob['transfer_map']['a']:.3f}, b = {d1_prob['transfer_map']['b']:.3f}.\n")

    add("## 6. D1: selective localisation\n")
    add("Error rate = 1 - Top-1 of the method whose answers are scored. AURC = mean error when the most confident cases are "
        "answered first (lower is better). Normalised gain: 1 = oracle confidence, 0 = confidence carries no information.\n")
    out.extend(selective_table(d1_sel))
    add("")

    add("## 7. D1: constant versus size-aware prior (all valid mutants, spectrum evidence only)\n")
    add("| Program size | Statements | Observed fault rate | Mean predicted, constant | Mean predicted, size-aware | Brier constant | Brier size-aware | ECE constant | ECE size-aware |\n|---|---|---|---|---|---|---|---|---|")
    for name, block in [("all", size["overall"])] + list(size["by_program_size"].items()):
        a, b = block["pcg"], block["pcg_size"]
        add(f"| {name} | {a['statements']} | {a['observed_fault_rate']:.4f} | {a['mean_predicted']:.4f} | {b['mean_predicted']:.4f} | "
            f"{a['brier']:.4f} | {b['brier']:.4f} | {a['ece']:.4f} | {b['ece']:.4f} |")
    pb = size["paired_brier_difference_size_minus_const"]
    add(f"\nPaired Brier difference, size-aware minus constant: {pb['mean_difference']:+.5f} "
        f"[{pb['ci_low']:+.5f}, {pb['ci_high']:+.5f}], p = {_p(pb['sign_flip_p_value'])}.\n")

    add("## 8. D2: human-written bugs, parameters transferred from D1\n")
    out.extend(ranking_table(d2["overall"]))
    add("")
    out.extend(comparison_table(d2["comparisons"]))
    levels = [int(r["fault_level"]) for r in d2_rows]
    add(f"\nLevel of the faulty statement in D2: " + ", ".join(f"level {v}: {levels.count(v)}" for v in range(5)) + ".\n")
    add("Quality of probabilities:\n")
    out.extend(probabilistic_table(d2["probabilistic"]))
    add("")
    out.extend(comparison_table(d2["paired_brier"]))
    add("\nSelective localisation:\n")
    out.extend(selective_table(d2["selective"]))
    add("")

    add("## 9. D2 with parameters from mutants of the other QuixBugs programs (in-suite)\n")
    out.extend(ranking_table(d2_in["overall"]))
    add("")
    out.extend(comparison_table([c for c in d2_in["comparisons"] if c["metric"] == "reciprocal_rank"]))
    add("")
    out.extend(probabilistic_table(d2_in["probabilistic"]))
    add("")

    add("## 10. D3: mutants of QuixBugs programs, parameters transferred from D1\n")
    out.extend(ranking_table(d3["overall"]))
    add("")
    out.extend(comparison_table(d3["comparisons"]))
    add("")
    out.extend(probabilistic_table(d3["probabilistic"]))
    add("")
    out.extend(comparison_table(d3["paired_brier"]))
    add("")

    add("## 11. Post hoc: two-fault programs\n")
    add("Added after the context hypothesis (P5) was refuted on single faults. Not pre-registered.\n")
    add(f"{two['n']} detected two-fault programs; coverage context of their faulty statements: {two['context_of_faulty_statements']}.\n")
    add("| Method | First fault Top-1 | First fault MRR | Both in top 3 | Both in top 5 | Mean rank |\n|---|---|---|---|---|---|")
    for m in ("ochiai", "metallaxis", "hybrid_avg", "lr_fusion", "pcg_size", "pcg_fused", "pcg_fused_nocontext"):
        o = two["overall"][m]
        add(f"| {LABELS[m]} | {_ci(o['first_top1'])} | {_ci(o['first_reciprocal_rank'])} | {_ci(o['all_top3'])} | "
            f"{_ci(o['all_top5'])} | {_ci(o['mean_rank'], 2)} |")
    add("")
    out.extend(comparison_table(two["comparisons"]))
    add("")

    add("## 12. Which faults show a symptom that a compiler, type checker or analyser could see?\n")
    add("| Symptom | D1 (injected) | D2 (human-written) |\n|---|---|---|")
    names = {"detected_faults": "Detected faults", "compile_error": "Do not compile",
             "any_failing_test_raises_type_or_name_error": "Some failing test raises a type, name or attribute error",
             "any_failing_test_raises_other_exception": "Some failing test raises another exception",
             "any_failing_test_does_not_terminate": "Some failing test does not terminate",
             "only_wrong_return_values": "Only wrong return values",
             "analyser_flags_some_line": "pylint flags some line (behavioural finding)",
             "analyser_flags_the_faulty_line": "pylint flags the faulty line"}
    for key, label in names.items():
        add(f"| {label} | {symptoms['D1'][key]} | {symptoms['D2'][key]} |")
    add("")

    add("## 13. Cost of the mutation analysis\n")
    add("| Dataset | Cases | Variants generated | Distinct variant programs executed | Seconds |\n|---|---|---|---|---|")
    for name in ("D1", "D1_two_fault", "external"):
        c = cost[name]
        add(f"| {name} | {c['cases']} | {c['variants_generated']} | {c['variant_texts_run']} | {c['seconds']:.0f} |")
    add("\nSeconds are wall-clock on the machine of the run and are the only non-deterministic numbers in this file.\n")
    return "\n".join(out) + "\n"


# ----------------------------------------------------------------------------
# Figures
# ----------------------------------------------------------------------------

def write_figures(path: Path) -> None:
    d1 = _load(path / "d1_ranking.json")
    stress = _load(path / "d1_stress_no_inverse.json")
    d2 = _load(path / "d2_transfer_summary.json")
    d1_prob = _load(path / "d1_probabilistic.json")
    d1_sel = _load(path / "d1_selective.json")

    methods = ("ochiai", "metallaxis", "hybrid_avg", "lr_fusion", "pcg_size", "pcg_fused")
    panels = (("D1: injected faults", d1["overall"]), ("D1 stress test: exact repair removed", stress["overall"]),
              ("D2: human-written bugs (QuixBugs)", d2["overall"]))
    fig, axes = plt.subplots(1, 3, figsize=(15, 4.2), sharey=True)
    for ax, (title, overall) in zip(axes, panels):
        means = np.array([overall[m]["reciprocal_rank"]["mean"] for m in methods])
        low = means - np.array([overall[m]["reciprocal_rank"]["ci_low"] for m in methods])
        high = np.array([overall[m]["reciprocal_rank"]["ci_high"] for m in methods]) - means
        colours = ["#c0392b" if m.startswith("pcg") else ("#2c6fbb" if m.startswith("lr") else "#7f8c8d") for m in methods]
        ax.barh(range(len(methods)), means, xerr=[low, high], color=colours, capsize=3)
        ax.set_yticks(range(len(methods)))
        ax.set_yticklabels([LABELS[m] for m in methods])
        ax.set_xlim(0, 1)
        ax.set_xlabel("mean reciprocal rank")
        ax.set_title(title, fontsize=10)
        ax.invert_yaxis()
        ax.grid(axis="x", alpha=0.3)
    fig.suptitle("Fault localisation with and without mutation evidence (bars: 95% bootstrap interval over programs)", fontsize=10)
    fig.tight_layout()
    fig.savefig(path / "fig_fusion_ranking.png", dpi=130)
    plt.close(fig)

    shown = (("pcg_fused", d1_prob["quality"], "D1"), ("lr_fusion", d1_prob["quality"], "D1"),
             ("pcg_fused", d2["probabilistic"], "D2"), ("lr_fusion", d2["probabilistic"], "D2"))
    fig, axes = plt.subplots(1, 4, figsize=(17, 4.3), sharey=True)
    for ax, (method, quality, dataset) in zip(axes, shown):
        data = quality["methods"][method]
        rows = [r for r in data["reliability"] if r["count"]]
        ax.plot([0, 1], [0, 1], linestyle="--", color="grey")
        ax.plot([r["mean_predicted"] for r in rows], [r["observed_frequency"] for r in rows], marker="o",
                color="#c0392b" if method.startswith("pcg") else "#2c6fbb")
        for r in rows:
            ax.annotate(str(r["count"]), (r["mean_predicted"], r["observed_frequency"]),
                        textcoords="offset points", xytext=(4, -10), fontsize=7, color="grey")
        ax.set_title(f"{LABELS[method]}, {dataset}\nBrier {data['brier']:.3f}, log loss {data['log_loss']:.3f}, ECE {data['ece']:.3f}",
                     fontsize=9)
        ax.set_xlabel("predicted P(statement faulty)")
        ax.grid(alpha=0.3)
    axes[0].set_ylabel("observed fraction faulty")
    fig.suptitle("Reliability in distribution (D1) and under shift to human-written bugs (D2); small numbers = statements per bin", fontsize=10)
    fig.tight_layout()
    fig.savefig(path / "fig_fusion_reliability.png", dpi=130)
    plt.close(fig)

    fig, axes = plt.subplots(1, 2, figsize=(11, 4.2))
    for ax, (title, selective) in zip(axes, (("D1: injected faults", d1_sel), ("D2: human-written bugs", d2["selective"]))):
        for method, colour, style in (("pcg_size", "#c0392b", "-"), ("ochiai_gap", "#7f8c8d", "--"), ("ochiai", "#7f8c8d", ":"),
                                      ("pcg_fused", "#8e1b10", "-."), ("lr_fusion", "#2c6fbb", "-.")):
            curve = selective[method]["curve"]
            ax.plot([p["coverage"] for p in curve], [p["risk"] for p in curve], color=colour, linestyle=style,
                    label=f"{LABELS[method]} (AURC {selective[method]['aurc']:.3f})")
        ax.set_xlabel("coverage (fraction of cases answered)")
        ax.set_ylabel("risk (1 - Top-1 among answered cases)")
        ax.set_title(title, fontsize=10)
        ax.set_ylim(0, 1)
        ax.grid(alpha=0.3)
        ax.legend(fontsize=7)
    fig.suptitle("Selective localisation: answering only the most confident cases", fontsize=10)
    fig.tight_layout()
    fig.savefig(path / "fig_risk_coverage.png", dpi=130)
    plt.close(fig)
