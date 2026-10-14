"""Check the numbers of the manuscript against the saved results: ``python scripts/verify_manuscript.py``.

Every claim below is a text snippet built from the result files (``results/v5``, ``results/v4``, ``results/v4_sensitivity``,
``results/v4_synthetic``, ``results/v5_development``); the check is that the snippet occurs in ``research/manuscript/paper.md``
(line breaks and repeated spaces ignored). A missing snippet means the manuscript and the results disagree, or the wording
changed and the claim here must follow. Exit status 0 when all claims are found. Nothing is written.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def squash(text: str) -> str:
    return re.sub(r"\s+", " ", text)


PAPER = squash((ROOT / "research" / "manuscript" / "paper.md").read_text(encoding="utf-8"))


def load(path: str):
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


v5, v4 = load("results/v5/summary.json"), load("results/v4/summary.json")
sens, syn = load("results/v4_sensitivity/summary.json"), load("results/v4_synthetic/summary.json")
kappa = load("results/v5_development/kappa_selection.json")
missing: list[str] = []
count = 0


def check(snippet: str, why: str) -> None:
    global count
    count += 1
    if squash(snippet) not in PAPER:
        missing.append(f"{why}: expected `{snippet}`")


def ci(e: dict) -> str:
    return f"{e['mean_difference']:+.3f} [{e['ci_low']:+.3f}, {e['ci_high']:+.3f}]"


def holm(p: float) -> str:
    return "0.0005" if p < 0.001 else f"{p:.3f}" if p < 0.01 else f"{p:.2f}" if p >= 0.1 else f"{p:.3f}"


NAMES = {"muse": "MUSE", "lr_fusion": "Logistic fusion", "pcg_fused": "PCG v3 fused", "pcg_size": "PCG spectrum only",
         "flitsr_star": "FLITSR\\*"}
R, CAL, V4R = v5["ranking"], v5["calibration"], v4["ranking"]
ap = lambda s, m: R[s][m]["ap_exp"]["mean"]
top1 = lambda s, m: R[s][m]["first_top1"]["mean"]
skill = lambda s, m: f"{CAL[s][m]['skill']:+.3f}"

# Table 1 (confirmatory comparisons C1), all ten rows with their Holm p values
for e in v5["hypotheses"]["C1"]:
    check(f"| {e['dataset'][1]} | {NAMES[e['comparison'].split(' - ')[1]]} | {ci(e)} | {holm(e['holm_p_value'])} |", "table 1 row")

# abstract and 5.1
m2 = next(e for e in v5["hypotheses"]["C1"] if e["dataset"] == "M2" and e["comparison"].endswith("muse"))
m3 = next(e for e in v5["hypotheses"]["C1"] if e["dataset"] == "M3" and e["comparison"].endswith("muse"))
check(f"{m2['mean_difference']:+.3f}, 95% interval [{m2['ci_low']:+.3f}, {m2['ci_high']:+.3f}], Holm-adjusted p = {m2['holm_p_value']:.3f}", "abstract MUSE, two faults")
check(f"{ci(m3)}", "MUSE, three faults")
pooled = {(e["faults"], e["baseline"]): e for e in v5["hypotheses"]["C4"] if e["benchmark"] == "pooled"}
check(f"{ci(pooled[(2, 'muse')])} ({pooled[(2, 'muse')]['programs']} programs)", "pooled MUSE, two faults")
check(f"{ci(pooled[(3, 'muse')])} ({pooled[(3, 'muse')]['programs']} programs)", "pooled MUSE, three faults")
c2 = v5["hypotheses"]["C2"]
check(f"{c2['mean_difference']:+.3f} [{c2['ci_low']:+.3f}, {c2['ci_high']:+.3f}]", "C2")
check(f"{v5['datasets']['M2']['programs']} fresh MBPP programs", "number of MBPP programs")
check(f"{v4['datasets']['EH']['cases'] + v4['datasets']['QH']['cases']} human-written bugs", "human bugs (HumanEvalFix plus QuixBugs)")
check(f"IV {ap('M2', 'iv'):.3f}, logistic fusion {ap('M2', 'lr_fusion'):.3f}, MUSE {ap('M2', 'muse'):.3f}, v3 fused {ap('M2', 'pcg_fused'):.3f}, "
      f"spectrum-only {ap('M2', 'pcg_size'):.3f}, FLITSR\\* {ap('M2', 'flitsr_star'):.3f}", "expected AP at two faults")
check(f"IV {top1('M2', 'iv'):.3f}, MUSE {top1('M2', 'muse'):.3f}, logistic fusion {top1('M2', 'lr_fusion'):.3f}, v3 fused {top1('M2', 'pcg_fused'):.3f}",
      "first-fault Top-1 at two faults")
check(f"expected AP ({ap('M1', 'iv'):.3f}) is below the learned fusion ({ap('M1', 'lr_fusion'):.3f}) and the v3 fusion ({ap('M1', 'pcg_fused'):.3f})",
      "single-fault expected AP")

# 5.2 other held-out benchmarks
h1 = {(e["dataset"], e["comparison"].split(" - ")[1]): e for e in v4["hypotheses"]["H1"]}
sq = {(e["dataset"], e["comparison"].split(" - ")[1]): e for e in sens["h1_corrected"]}
check(f"{h1[('Q2', 'muse')]['mean_difference']:+.3f} and {h1[('E2', 'muse')]['mean_difference']:+.3f} (mid-rank) and "
      f"{sq[('Q2', 'muse')]['mean_difference']:+.3f} and {sq[('E2', 'muse')]['mean_difference']:+.3f} (expected AP)", "differences to MUSE on v4 benchmarks")
h3 = {(e["dataset"], e["comparison"].split(" - ")[1]): e for e in v4["hypotheses"]["H3"]}
eh = V4R["EH"]
check(f"IV's mean reciprocal rank is {eh['iv']['first_rr']['mean']:.3f}", "EH MRR of IV")
check(f"{eh['pcg_fused']['first_rr']['mean']:.3f} for the v3 fusion ({ci(h3[('EH', 'pcg_fused')])})", "EH v3 fusion")
check(f"{eh['lr_fusion']['first_rr']['mean']:.3f} for logistic fusion ({ci(h3[('EH', 'lr_fusion')])})", "EH logistic fusion")
check(f"(-{abs(h3[('QH', 'pcg_fused')]['mean_difference']):.3f}, -{abs(h3[('QH', 'lr_fusion')]['mean_difference']):.3f}", "QH differences")
split = v4["human_bugs_by_restoring_variant"]["EH"]
check(f"({split['has a restoring variant']['cases']} of {v4['datasets']['EH']['cases']} bugs) the MRR is {split['has a restoring variant']['iv']:.3f}", "EH with restoring variant")
check(f"where none exists {split['has none']['iv']:.3f}", "EH without restoring variant")

# 5.3 probabilities
check(f"one fault IV {skill('M1', 'iv')} (v3 fused {skill('M1', 'pcg_fused')}, learned fusion {skill('M1', 'lr_fusion')})", "skill, one fault")
check(f"two faults IV **{skill('M2', 'iv')}**, v3 fused {skill('M2', 'pcg_fused')}, learned fusion {skill('M2', 'lr_fusion')}, "
      f"coverage-only network {skill('M2', 'pcg_size')}", "skill, two faults")
check(f"three faults IV {skill('M3', 'iv')}, v3 fused {skill('M3', 'pcg_fused')}, learned fusion {skill('M3', 'lr_fusion')}, "
      f"coverage-only network {skill('M3', 'pcg_size')}", "skill, three faults")
diffs = [abs(e["mean_difference"]) for e in v5["paired_brier"] if e["dataset"] in ("M2", "M3")]
check(f"-{min(diffs):.3f} to -{max(diffs):.3f}", "paired Brier range")
inf = v5["inferred_faults"]
check(f"AUC {inf['auc_multi_vs_single']:.3f} on MBPP", "AUC")
check(f"({inf['mean_by_true_count']['2']:.2f} and {inf['mean_by_true_count']['3']:.2f} on MBPP)", "inferred faults, two and three")

# 5.4 simulated programs
sim = {key: cell["methods"] for key, cell in syn.items()}
check(f"{sim['well_specified|2']['iv']['map']:.2f} (two faults) against {sim['well_specified|2']['muse']['map']:.2f} for MUSE", "simulation, model correct")
check(f"({sim['few_repairs|2']['iv']['map']:.3f} against {sim['few_repairs|2']['pcg_spectrum']['map']:.3f} at two faults, "
      f"{sim['few_repairs|3']['iv']['map']:.3f} against {sim['few_repairs|3']['pcg_spectrum']['map']:.3f} at three)", "simulation, few repairs")

# 6 negative results
rows = {str(r["kappa"]): r for r in kappa["rows"]}
check(f"log loss {rows['1.0']['pooled.log_loss']:.4f} to {rows['inf']['pooled.log_loss']:.4f}", "hierarchical prior")
check(f"{R['M2']['iv']['all_top3']['mean']:.3f} against {R['M2']['pcg_size']['all_top3']['mean']:.3f} to {R['M2']['hybrid_avg']['all_top3']['mean']:.3f}",
      "all faults in the top 3")
check(f"expected AP {ap('M1', 'pcg_fused'):.3f} and {ap('M1', 'lr_fusion'):.3f} against {ap('M1', 'iv'):.3f} on MBPP", "single-fault comparison")
check(f"skill is negative at three faults ({sim['few_repairs|3']['iv']['skill']:+.3f})", "simulation, few repairs, skill")

# data and setup claims (sections 3, 4, 7, abstract)
sys.path.insert(0, str(ROOT))
from pcg import config, v4 as v4module  # noqa: E402

D = v4["datasets"]
check(f"({D['D1-1']['programs']} programs, {D['D1-1']['cases']} detected faults)", "development set")
check(f"({D['E-mix']['programs']} programs with 1 to 3 injected faults", "HumanEval programs")
check(f"QuixBugs ({D['QH']['programs']} programs, 1 to 3 injected faults, {D['QH']['cases']} human bugs)", "QuixBugs programs")
check(f"twelve baselines", "number of baselines") if len(v4module.BASELINE_METHODS) == 12 else missing.append("number of baselines is not 12")
check(f"a mixture of {config.IV_NONREPAIR_KINDS if config.IV_NONREPAIR_KINDS != 5 else 'five'} kinds", "non-repair kinds")
check(f"({config.EXPECTED_AP_DRAWS} draws)", "draws of the expected AP")
check(f"most {'three' if config.IV_MAX_FAULTS == 3 else config.IV_MAX_FAULTS} faulty statements", "faults enumerated")
share = lambda ds: D[ds]["share_all_faults_with_restoring_variant"]
single = sorted([share("D1-1"), share("E1"), share("Q1")])
human = sorted([share("QH"), share("EH")])
check(f"({single[0]:.2f} to {single[-1]:.2f} of single faults against {human[0]:.2f} to {human[-1]:.2f} of human bugs)", "restoring variants")
h7 = v4["hypotheses"]["H7"]
check(f"about {round((h7['Q-mix']['auc'] + h7['E-mix']['auc']) / 2, 2):.2f} on QuixBugs and HumanEval", "AUC on the other benchmarks")
import csv  # noqa: E402

rows = list(csv.DictReader((ROOT / "results/v4/per_case.csv").open(encoding="utf-8")))
shares = {}
for column in rows[0]:
    if column.endswith(".ap") and not column.startswith("iv_"):
        shares[column] = sum(float(r[column]) > 1 + 1e-9 for r in rows) / len(rows)
top = max(float(r[c]) for r in rows for c in shares)
check(f"exceeded 1 in {100 * min(shares.values()):.1f} to {100 * max(shares.values()):.1f}% of cases (maximum {top:.1f})", "tie flaw")

gap = max(abs(V4R[d]["iv_c2"]["ap"]["mean"] - V4R[d]["iv"]["ap"]["mean"]) for d in ("Q2", "E2", "Q3", "E3"))
check(f"(differences at most {gap:.3f})", "at most two faults against three (version 4 ablation)")

print(f"{count} claims checked; {len(missing)} not found in research/manuscript/paper.md")
for line in missing:
    print("MISSING", line.replace("\n", "\\n"))
sys.exit(1 if missing else 0)
