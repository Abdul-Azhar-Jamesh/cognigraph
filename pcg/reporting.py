"""Builds ``SUMMARY.md`` from the result files (and from nothing else).

Every number in the summary is read back from a JSON/CSV file written by the
experiments, so the summary cannot drift from the data.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

from .visualize import METHOD_LABELS


def _load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _csv(path: Path) -> list[dict]:
    with open(path, newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def _ci(entry: dict, digits: int = 3) -> str:
    return f"{entry['mean']:.{digits}f} [{entry['ci_low']:.{digits}f}, {entry['ci_high']:.{digits}f}]"


def _p(value: float) -> str:
    return "< 0.0001" if value < 0.0001 else f"{value:.4f}"


def _comparison_rows(comparisons: list[dict]) -> list[str]:
    lines = ["| Comparison | Metric | Mean difference [95% CI] | Programs better / worse / equal | Sign-flip p |",
             "|---|---|---|---|---|"]
    for c in comparisons:
        lines.append(
            f"| {c['comparison']} | {c['metric']} | {c['mean_difference']:+.4f} [{c['ci_low']:+.4f}, {c['ci_high']:+.4f}] "
            f"| {c['programs_a_better']} / {c['programs_b_better']} / {c['programs_equal']} | {_p(c['sign_flip_p_value'])} |")
    return lines


def build_summary(path: Path) -> str:
    """Render the Markdown summary of one finished benchmark directory."""
    programs = _load(path / "programs.json")
    cases = [json.loads(line) for line in (path / "cases.jsonl").read_text(encoding="utf-8").splitlines()]
    excluded = _load(path / "excluded_mutants.json")
    first = _load(path / "first_order_summary.json")
    calibration = _load(path / "calibration.json")
    pooled = _load(path / "params_pooled.json")
    two = _load(path / "two_fault_summary.json")
    llm = _load(path / "simulated_llm_summary.json")
    repair = _load(path / "repair_summary.json")
    ablation = _load(path / "slice_ablation_without_sdl.json")
    fault_free = _csv(path / "fault_free_programs.csv")
    sensitivity = _csv(path / "sensitivity.csv")

    detected = [c for c in cases if c["classification"] == "detected"]
    generated = sum(p["mutants_generated"] for p in programs)
    out: list[str] = []
    add = out.append

    add("# Benchmark results (generated file, do not edit)\n")
    add("Produced by `python -m pcg benchmark`. Every number below is read from the data files in this "
        "directory. Intervals are 95% percentile bootstrap intervals that resample whole programs.\n")

    add("## 1. Benchmark\n")
    add("| Quantity | Value |\n|---|---|")
    add(f"| Reference programs | {len(programs)} |")
    add(f"| Statements per program (min / mean / max) | {min(len(p['statements']) for p in programs)} / "
        f"{sum(len(p['statements']) for p in programs) / len(programs):.1f} / {max(len(p['statements']) for p in programs)} |")
    add(f"| Tests per program (min / mean / max) | {min(len(p['tests']) for p in programs)} / "
        f"{sum(len(p['tests']) for p in programs) / len(programs):.1f} / {max(len(p['tests']) for p in programs)} |")
    add(f"| Single-fault mutants generated | {generated} |")
    add(f"| Excluded (runner exceeded the wall-clock limit) | {len(excluded)} |")
    add(f"| Valid mutants | {len(cases)} |")
    add(f"| Detected by the tests (used for localisation) | {len(detected)} |")
    add(f"| Not detected (equivalent or missed; never counted as localised) | {len(cases) - len(detected)} |\n")
    categories: dict[str, list[int]] = {}
    for c in cases:
        entry = categories.setdefault(c["ground_truth_EVALUATION_ONLY"]["categories"][0], [0, 0])
        entry[0] += 1
        entry[1] += c["classification"] == "detected"
    add("| Fault category | Valid mutants | Detected |\n|---|---|---|")
    for name in sorted(categories):
        add(f"| {name} | {categories[name][0]} | {categories[name][1]} |")
    add("")

    add("## 2. Estimated parameters (pooled over all mutants, for reference)\n")
    add("Each evaluated program uses its own leave-one-program-out estimate (`params_lopo.json`); "
        "the pooled values below show the typical magnitudes.\n")
    add("| Parameter | Meaning | Estimate |\n|---|---|---|")
    add(f"| pi | P(statement faulty) | {pooled['prior_fault']:.4f} |")
    add(f"| lambda | P(test fails with no fault in scope) | {pooled['leak']:.6f} |")
    add(f"| theta (pooled) | P(executed fault makes the test fail) | {pooled['theta']:.4f} |")
    add(f"| P(A=1 \\| F=1) | pylint flags a faulty statement | {pooled['static_tpr']:.4f} |")
    add(f"| P(A=1 \\| F=0) | pylint flags a fault-free statement | {pooled['static_fpr']:.4f} |\n")
    add("Exposure-rate prior fitted by EM (mixture of binomials):\n")
    add("| theta | " + " | ".join(f"{t:.2f}" for t in pooled["theta_grid"]) + " |")
    add("|---|" + "---|" * len(pooled["theta_grid"]))
    add("| weight | " + " | ".join(f"{w:.3f}" for w in pooled["theta_weights"]) + " |\n")

    add("## 3. Single-fault localisation (leave-one-program-out)\n")
    add(f"{len(detected)} detected mutants. Ties are scored by their expected value under a random tie-break.\n")
    add("| Method | Top-1 | Top-3 | MRR | EXAM (lower is better) |\n|---|---|---|---|---|")
    for method in METHOD_LABELS:
        if method in first["overall"]:
            o = first["overall"][method]
            add(f"| {METHOD_LABELS[method]} | {_ci(o['top1'])} | {_ci(o['top3'])} | {_ci(o['reciprocal_rank'])} | {_ci(o['exam'])} |")
    add("\n### Paired comparisons\n")
    add("Differences are per mutant; the test is a sign-flip permutation test on per-program mean differences.\n")
    out.extend(_comparison_rows(first["comparisons"]))
    add("\n### By fault category (MRR)\n")
    add("| Category | n | Ochiai | PCG | PCG fixed theta | PCG + slicing | PCG + static |\n|---|---|---|---|---|---|---|")
    for name, row in first["by_category"].items():
        add(f"| {name} | {row['n']} | " + " | ".join(
            f"{row[m]['reciprocal_rank']:.3f}" for m in ("ochiai", "pcg", "pcg_fixed_theta", "pcg_slice", "pcg_static")) + " |")
    add("")

    add("## 4. Probabilistic quality of the posteriors\n")
    add("All statements of all valid mutants, out-of-fold. The base-rate reference predicts the prior for every statement.\n")
    add("| Model | Statements | Faulty | Brier | Log loss | ECE (10 bins) |\n|---|---|---|---|---|---|")
    for name in ("base_rate_reference", "pcg_fixed_theta", "pcg", "pcg_slice", "pcg_static"):
        d = calibration[name]["all_valid_mutants"]
        label = "Base rate (prior only)" if name == "base_rate_reference" else METHOD_LABELS[name]
        add(f"| {label} | {d['n_statements']} | {d['n_faulty']} | {d['brier']:.4f} | {d['log_loss']:.4f} | {d['ece']:.4f} |")
    add("\nReliability table for PCG (predicted vs observed):\n")
    add("| Bin | Statements | Mean predicted | Observed frequency |\n|---|---|---|---|")
    for row in calibration["pcg"]["all_valid_mutants"]["reliability"]:
        if row["count"]:
            add(f"| {row['bin_low']:.1f}-{row['bin_high']:.1f} | {row['count']} | {row['mean_predicted']:.3f} | {row['observed_frequency']:.3f} |")
    prior_nf = sum(float(r["prior_p_no_fault"]) for r in fault_free) / len(fault_free)
    post_nf = sum(float(r["posterior_p_no_fault"]) for r in fault_free) / len(fault_free)
    add(f"\nFault-free reference programs (all tests pass): mean P(no fault) rises from {prior_nf:.3f} (prior) "
        f"to {post_nf:.3f} (posterior); minimum posterior {min(float(r['posterior_p_no_fault']) for r in fault_free):.3f}.\n")

    add("## 5. Ablation: dependence slicing\n")
    add("Slicing shrinks each test's scope to its backward dependence slice. A deleted statement (SDL mutant) has no "
        "dependences, so slicing cannot see it. The table repeats the comparison with SDL mutants removed from "
        "both training and evaluation.\n")
    add(f"| Method ({ablation['n_detected']} detected non-SDL mutants) | Top-1 | Top-3 | MRR |\n|---|---|---|---|")
    for method in ("ochiai", "pcg", "pcg_slice"):
        o = ablation["overall"][method]
        add(f"| {METHOD_LABELS[method]} | {_ci(o['top1'])} | {_ci(o['top3'])} | {_ci(o['reciprocal_rank'])} |")
    add("")
    per_case = _csv(path / "first_order_per_case.csv")
    sdl = [r for r in per_case if r["operator"] == "SDL"]
    other = [r for r in per_case if r["operator"] != "SDL"]
    add(f"In the full benchmark, the faulty line lies outside the slice scope of at least one failing test for "
        f"{sum(r['fault_in_slice_scope_of_all_failing'] == 'False' for r in sdl)} of {len(sdl)} detected SDL mutants "
        f"and for {sum(r['fault_in_slice_scope_of_all_failing'] == 'False' for r in other)} of {len(other)} other mutants.\n")
    out.extend(_comparison_rows(ablation["comparisons"]))
    add("")

    add("## 6. Sensitivity to hand-set parameters (fixed-theta model)\n")
    top1 = [float(r["top1"]) for r in sensitivity]
    brier = [float(r["brier"]) for r in sensitivity]
    add(f"Over {len(sensitivity)} hand-set (theta, lambda, pi) combinations: Top-1 ranges from {min(top1):.3f} to "
        f"{max(top1):.3f}; Brier score from {min(brier):.4f} to {max(brier):.4f}. Full grid: `sensitivity.csv`.\n")

    add("## 7. Two-fault programs\n")
    add(f"{two['n_generated']} sampled, {two['n_excluded']} excluded (runner limit), {two['n_not_detected']} not detected, "
        f"{two['n_detected']} evaluated. Parameters come from the single-fault folds. Ties use mid-ranks here, "
        "so a method that ties every statement (chance) scores 0 on Top-1 by construction.\n")
    add("| Method | First fault Top-1 | First fault Top-3 | First fault MRR | Both in top 3 | Both in top 5 | Mean rank |\n|---|---|---|---|---|---|---|")
    for method in METHOD_LABELS:
        if method in two["overall"]:
            o = two["overall"][method]
            add(f"| {METHOD_LABELS[method]} | {_ci(o['first_top1'])} | {_ci(o['first_top3'])} | {_ci(o['first_reciprocal_rank'])} "
                f"| {_ci(o['all_top3'])} | {_ci(o['all_top5'])} | {_ci(o['mean_rank'], 2)} |")
    add("")
    out.extend(_comparison_rows(two["comparisons"]))
    add("")

    add("## 8. SIMULATED LLM-confidence signal\n")
    add("**The confidence values in this section are synthetic.** They are drawn from Beta distributions that depend on "
        "the ground truth, to measure how the model would use a signal of known quality. They are not outputs of any "
        "language model and say nothing about real LLM calibration.\n")
    add("| Signal | Faulty-line distribution | PCG Top-1 | LLM-only Top-1 | PCG + LLM Top-1 | PCG MRR | PCG + LLM MRR | PCG Brier | PCG + LLM Brier |\n|---|---|---|---|---|---|---|---|---|")
    for level in ("uninformative", "weak", "strong"):
        d = llm[level]
        add(f"| {level} | {d['faulty_line_confidence_distribution']} | {d['pcg']['top1']['mean']:.3f} | "
            f"{d['llm_only']['top1']['mean']:.3f} ± {d['llm_only']['top1']['sd']:.3f} | "
            f"{d['pcg_plus_llm']['top1']['mean']:.3f} ± {d['pcg_plus_llm']['top1']['sd']:.3f} | {d['pcg']['mrr']['mean']:.3f} | "
            f"{d['pcg_plus_llm']['mrr']['mean']:.3f} ± {d['pcg_plus_llm']['mrr']['sd']:.3f} | {d['brier']['pcg']['mean']:.4f} | "
            f"{d['brier']['pcg_plus_llm']['mean']:.4f} |")
    first_level = next(iter(llm.values()))
    add(f"\nFault-free lines always draw from {first_level['fault_free_line_confidence_distribution']}. "
        f"Mean ± standard deviation over {first_level['replicates']} seeded replicates.\n")

    add("## 9. Targeted repair\n")
    add("A patch is *plausible* when it compiles and passes every test; *exact* when its text equals the reference "
        "program. Plausible does not mean correct.\n")
    add("| Strategy | Plausible repair rate | Exact repair rate | Candidates validated | Fault line inside region |\n|---|---|---|---|---|")
    labels = {"pcg_top3": "PCG, top-3 statements", "ochiai_top3": "Ochiai, top-3 statements",
              "unguided_all": "Unguided, all statements"}
    for strategy, label in labels.items():
        o = repair["overall"][strategy]
        add(f"| {label} | {_ci(o['repaired'])} | {_ci(o['exact'])} | {_ci(o['candidates_tried'], 2)} | {_ci(o['fault_line_in_region'])} |")
    add("")
    out.extend(_comparison_rows(repair["comparisons"]))
    add("")
    return "\n".join(out) + "\n"
