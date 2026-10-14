"""Demonstration of the version 4 model: ``python -m pcg demo-v4``.

Three cases from the development benchmark, chosen by fixed rules (not by
hand), so that a failure is shown next to a success:

* ``two_faults``     the first two-fault program, in identifier order, where the
                     version 3 fused model does not have both faults in its top
                     three and the interventional model does;
* ``cost_of_generality``  the first single-fault program where version 3 ranks the
                     fault first and the interventional model does not;
* ``no_repair``      the first two-fault program in which no variant of either
                     faulty statement makes any failing test pass.

All parameters used for a case are estimated without the program it comes from.
Ground truth is printed last and never enters the analysis.
"""

from __future__ import annotations

from pathlib import Path
from typing import Callable

import numpy as np

from . import config, experiments as ex, metrics
from . import v4
from .fusion import size_aware_prior
from .interventional import enumerate_configurations, summarise
from .mbfl import LEVEL_NAMES, LEVEL_PLAUSIBLE

DEMO_V4_DIR = config.RESULTS_DIR / "demo_v4"


def _analysis(case: ex.Case, observed: dict, fitted: v4.Fitted) -> dict:
    scores, _ = v4.score(case, observed, fitted, ablations=False)
    params, fusion = fitted.trained.params, fitted.trained.fusion
    grid, weights = params.exposure_prior()
    n = len(case.program.statements)
    posterior = summarise(enumerate_configurations(
        np.full(n, size_aware_prior(n, fusion.mu)), case.spectrum.coverage, case.spectrum.failed,
        observed[case.case_id][0], fitted.iv, grid, weights, params.leak, config.IV_MAX_FAULTS))
    return {"scores": scores, "posterior": posterior}


def _write_case(folder: Path, title: str, rule: str, case: ex.Case, observed: dict, analysis: dict) -> str:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    from .v4_report import _save, _style

    folder.mkdir(parents=True, exist_ok=True)
    observations, evidence = observed[case.case_id]
    scores, posterior = analysis["scores"], analysis["posterior"]
    statements = case.program.statements
    failed = case.spectrum.failed
    lines = [f"## {title}", "", f"Selection rule: {rule}", "", f"Case `{case.case_id}`. {case.spectrum.n_failed} of "
             f"{case.spectrum.n_tests} tests fail.", "", "```", case.program.listing(), "```", "",
             "| Line | Statement | Failing tests that run it | Variants | Best variant fixes | Version 3 reads this as | "
             "Spectrum only | Version 3 fused | Interventional |", "|---|---|---|---|---|---|---|---|---|"]
    for index, line in enumerate(statements):
        own = [o for o in observations if o.column == index]
        best = max((int(o.flips.sum()) for o in own), default=0)
        in_scope = int((case.spectrum.coverage[:, index] & failed).sum())
        lines.append(f"| {line} | `{case.program.line_text(line).strip()}` | {in_scope} | {len(own)} | "
                     f"{best} of {in_scope} | {LEVEL_NAMES[int(evidence.levels[index])]} | {scores['pcg_size'][index]:.3f} | "
                     f"{scores['pcg_fused'][index]:.3f} | **{scores['iv'][index]:.3f}** |")
    sizes = ", ".join(f"{k} fault{'s' if k != 1 else ''}: {p:.2f}" for k, p in enumerate(posterior.size_distribution) if k)
    most = ", ".join(str(statements[i]) for i in posterior.map_faults)
    faults = [i for i, flag in enumerate(case.faulty_mask) if flag]
    lines += ["", f"Interventional model: probability of {sizes}. Most probable set of faulty lines: {{{most}}}.", "",
              "Ground truth (evaluation only): faulty line"
              f"{'s' if len(faults) != 1 else ''} {', '.join(str(statements[i]) for i in faults)}. "
              f"A restoring variant exists for {int((evidence.levels[faults] == LEVEL_PLAUSIBLE).sum())} of {len(faults)}.", "",
              "| Model | Mid-rank of each faulty line | Average precision |", "|---|---|---|"]
    for key, label in (("pcg_size", "Spectrum only"), ("pcg_fused", "Version 3 fused"), ("iv", "Interventional")):
        ranks = [sum(metrics.tie_interval(scores[key], i)) / 2 for i in faults]
        lines.append(f"| {label} | {', '.join(f'{r:g}' for r in ranks)} | {metrics.average_precision(scores[key], faults):.3f} |")
    (folder / "faulty_program.py").write_text(case.program.source, encoding="utf-8", newline="\n")

    _style()
    fig, ax = plt.subplots(figsize=(max(6.0, 0.55 * len(statements) + 2), 3.2))
    x = np.arange(len(statements))
    for offset, (key, label, color) in enumerate((("pcg_size", "Spectrum only", "#7fcdbb"),
                                                  ("pcg_fused", "Version 3 fused", "#2c7fb8"),
                                                  ("iv", "Interventional", "#c0392b"))):
        ax.bar(x + (offset - 1) * 0.27, scores[key], width=0.27, label=label, color=color)
    ax.set_xticks(x)
    ax.set_xticklabels([f"line {s}" + (" *" if i in faults else "") for i, s in enumerate(statements)], rotation=45, ha="right")
    ax.set_ylabel("P(statement is faulty)")
    ax.set_ylim(0, 1.05)
    ax.set_title(f"{title} (* = faulty line, shown for evaluation only)", loc="left", fontsize=9, fontweight="bold")
    ax.legend(fontsize=7)
    _save(fig, folder, "posteriors")
    return "\n".join(lines) + "\n"


def run_demo_v4(out_path: Path = DEMO_V4_DIR, log: Callable[[str], None] = print) -> Path:
    out = ex.OutputDir(out_path)
    references = ex.load_references()
    single, _ = ex.build_first_order_cases(references)
    two = sorted((c for c in ex.build_two_fault_cases(references)[0] if c.detected), key=lambda c: c.case_id)
    observed, _ = v4.observe([c for c in single if c.detected] + two, config.STEP_LIMIT, config.SUBPROCESS_TIMEOUT_S, log)
    folds: dict[str, v4.Fitted] = {}

    def fitted(case: ex.Case) -> v4.Fitted:
        if case.program_name not in folds:
            folds[case.program_name] = v4.fit([c for c in single if c.program_name != case.program_name], observed,
                                              f"D1 without {case.program_name}")
        return folds[case.program_name]

    def top3(scores: np.ndarray, case: ex.Case) -> bool:
        return metrics.multi_fault_metrics(scores, np.flatnonzero(case.faulty_mask).tolist())["all_top3"] == 1.0

    def first(cases, condition):
        for case in cases:
            analysis = _analysis(case, observed, fitted(case))
            if condition(case, analysis):
                return case, analysis
        raise RuntimeError("no case satisfies the selection rule")

    rules = (
        ("two_faults", "Two faults: the mechanism the model was built for", two,
         "first two-fault program, in identifier order, where version 3 fused does not have both faults in its top 3 and the interventional model does",
         lambda c, a: not top3(a["scores"]["pcg_fused"], c) and top3(a["scores"]["iv"], c)),
        ("cost_of_generality", "One fault: where allowing several faults costs accuracy",
         sorted((c for c in single if c.detected), key=lambda c: c.case_id),
         "first single-fault program where version 3 fused ranks the fault first and the interventional model does not",
         lambda c, a: metrics.multi_fault_metrics(a["scores"]["pcg_fused"], np.flatnonzero(c.faulty_mask).tolist())["first_top1"] == 1.0
         and metrics.multi_fault_metrics(a["scores"]["iv"], np.flatnonzero(c.faulty_mask).tolist())["first_top1"] < 1.0),
        ("no_repair", "Two faults, no variant of either faulty statement fixes a failing test: the evidence is missing", two,
         "first two-fault program in which no variant of either faulty statement makes any failing test pass",
         lambda c, a: not any(o.flips.any() for o in observed[c.case_id][0] if c.faulty_mask[o.column])),
    )
    text = ["# Demonstration of the interventional model (generated)", "",
            "Three cases chosen by fixed rules from the development benchmark. Parameters for each case are",
            "estimated without the program it comes from. Columns give P(statement is faulty) under three models.", ""]
    for name, title, cases, rule, condition in rules:
        case, analysis = first(cases, condition)
        log(f"    {name}: {case.case_id}")
        text.append(_write_case(out.path / name, title, rule, case, observed, analysis))
    (out.path / "DEMO_V4.md").write_text("\n".join(text), encoding="utf-8", newline="\n")
    out.finish()
    return out.path
