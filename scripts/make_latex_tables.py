"""Turn result tables into LaTeX for the manuscript: ``python scripts/make_latex_tables.py``.

Reads ``results/v5/summary.json`` (the CSV tables hold the same numbers rounded to four decimals) and writes ``research/manuscript/tables/*.tex`` (booktabs style; needs no package other than
booktabs). The CSV files stay the authoritative copy; the .tex files are derived and can be rebuilt at any time.
"""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "research" / "manuscript" / "tables"
NAMES = {"muse": "MUSE", "flitsr_star": "FLITSR*", "pcg_size": "PCG spectrum only", "pcg_fused": "PCG v3 fused",
         "lr_fusion": "Logistic fusion"}


def escape(text: str) -> str:
    return text.replace("&", r"\&").replace("_", r"\_").replace("%", r"\%").replace("*", r"$^{*}$")


def table(caption: str, label: str, header: list[str], rows: list[list[str]], spec: str) -> str:
    lines = [r"\begin{table}[t]", r"\centering", rf"\caption{{{caption}}}", rf"\label{{{label}}}", rf"\begin{{tabular}}{{{spec}}}",
             r"\toprule", " & ".join(header) + r" \\", r"\midrule"]
    lines += [" & ".join(row) + r" \\" for row in rows]
    lines += [r"\bottomrule", r"\end{tabular}", r"\end{table}", ""]
    return "\n".join(lines)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    summary = json.loads((ROOT / "results/v5/summary.json").read_text(encoding="utf-8"))  # full precision, no double rounding
    rows = []
    for r in summary["hypotheses"]["C1"]:
        baseline = NAMES[r["comparison"].split(" - ")[1]]
        rows.append([r["dataset"].replace("M", "") + " faults", escape(baseline),
                     f"{r['mean_difference']:+.3f} [{r['ci_low']:+.3f}, {r['ci_high']:+.3f}]",
                     f"{r['holm_p_value']:.4f}", "yes" if r["supported"] else "no"])
    (OUT / "table_c1.tex").write_text(table(
        "MBPP confirmatory study: expected average precision of IV minus each baseline (95\\% cluster bootstrap interval, Holm-adjusted $p$).",
        "tab:c1", ["Faults", "Baseline", "Difference [95\\% CI]", "Holm $p$", "Supported"], rows, "llccc"), encoding="utf-8", newline="\n")

    rows = []
    for r in summary["hypotheses"]["C4"]:
        if r["baseline"] == "muse":
            rows.append([str(r["faults"]), r["benchmark"], str(r["programs"]),
                         f"{r['mean_difference']:+.3f} [{r['ci_low']:+.3f}, {r['ci_high']:+.3f}]"])
    (OUT / "table_forest_muse.tex").write_text(table(
        "IV minus MUSE, expected average precision, per benchmark and pooled.", "tab:muse",
        ["Faults", "Benchmark", "Programs", "Difference [95\\% CI]"], rows, "llcc"), encoding="utf-8", newline="\n")

    labels = {"iv": "IV", "pcg_fused": "PCG v3 fused", "lr_fusion": "Logistic fusion", "pcg_size": "PCG spectrum only"}
    rows = [[d, labels[m], f"{q['brier']:.4f}", f"{q['skill']:+.3f}", f"{q['log_loss']:.3f}", f"{q['ece']:.3f}"]
            for d, by in summary["calibration"].items() for m, q in by.items()]
    (OUT / "table_calibration.tex").write_text(table(
        "Quality of the statement probabilities on MBPP (skill is relative to the base rate of each program).", "tab:cal",
        ["Set", "Method", "Brier", "Skill", "Log loss", "ECE"], rows, "llcccc"), encoding="utf-8", newline="\n")
    print("wrote", ", ".join(p.name for p in sorted(OUT.glob("*.tex"))))


if __name__ == "__main__":
    main()
