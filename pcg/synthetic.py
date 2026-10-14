"""Controlled synthetic study of the interventional model (protocol stage A).

Programs are *simulated*: random coverage, known faulty statements, and test
and variant outcomes drawn from a stated generating process. Nothing here is a
real program, and no result of this module is evidence about real faults. The
purpose is to see whether inference does what the mathematics says when the
model is right, and how it degrades when specific assumptions are broken.

The generating parameters are the ones fitted on D1 (``fitted_on_d1.json``),
so the simulated world resembles the real data in its rates. Scenarios:

* ``well_specified``    data from the model itself.
* ``own_exposure``      every fault has its own exposure rate.
* ``correlated_tests``  tests come in groups of three that share coverage and exposures.
* ``coupled_faults``    two faults in the scope of one test are exposed together or not at all.
* ``many_maskers``      five times as many masking variants on fault-free statements.
* ``few_repairs``       only 20% of faulty statements have a repair among their variants.
* ``half_variants``     half of the variants are missing.
* ``four_faults``       four faults, while inference allows at most three.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Sequence

import numpy as np

from . import baselines, config, experiments as ex, metrics
from .fusion import FusionCase, effective_prior, estimate_fusion_params, size_aware_prior
from .interventional import (InterventionParams, VariantObservation, enumerate_configurations,
                             estimate_intervention_params, summarise)
from .mbfl import mutation_evidence
from .model import FaultModel, infer

SYNTHETIC_DIR = config.RESULTS_DIR / "v4_synthetic"
SCENARIOS = ("well_specified", "own_exposure", "correlated_tests", "coupled_faults", "many_maskers", "few_repairs",
             "half_variants", "four_faults")
METHODS = ("ochiai", "muse", "pcg_spectrum", "pcg_fused", "iv_c1", "iv", "iv_true")
PROB_METHODS = ("pcg_spectrum", "pcg_fused", "iv_c1", "iv", "iv_true")
TRAINING_PROGRAMS = 400
PROGRAMS_PER_CELL = 250


@dataclass(frozen=True)
class World:
    """Generating parameters."""

    iv: InterventionParams
    theta_grid: tuple[float, ...]
    theta_weights: tuple[float, ...]
    leak: float


@dataclass
class SyntheticCase:
    coverage: np.ndarray
    failed: np.ndarray
    faulty: np.ndarray
    observations: list[VariantObservation]
    variants: list[tuple[int, list[str]]]  # (statement number, behaviour per test) for the version 3 summaries


def simulate(rng: np.random.Generator, world: World, n_faults: int, scenario: str) -> SyntheticCase:
    """One simulated faulty program with at least one failing test."""
    p = world.iv
    group = 3 if scenario == "correlated_tests" else 1
    while True:
        n = int(rng.integers(6, 15))
        base_tests = int(rng.integers(3, 5)) if group > 1 else int(rng.integers(7, 13))
        reach = rng.uniform(0.35, 1.0, size=n)
        coverage = rng.random((base_tests, n)) < reach[None, :]
        coverage[np.arange(base_tests), rng.integers(0, n, base_tests)] = True
        faults = rng.choice(n, size=n_faults, replace=False)
        theta = np.full(n_faults, rng.choice(world.theta_grid, p=world.theta_weights))
        if scenario == "own_exposure":
            theta = rng.choice(world.theta_grid, size=n_faults, p=world.theta_weights)
        exposed = (rng.random((base_tests, n_faults)) < theta[None, :]) & coverage[:, faults]
        if scenario == "coupled_faults":
            shared = coverage[:, faults].sum(axis=1) >= 2
            together = rng.random(base_tests) < theta[0]
            exposed[shared] = (coverage[:, faults] & together[:, None])[shared]
        leak = rng.random(base_tests) < world.leak
        coverage, exposed, leak = (np.repeat(a, group, axis=0) for a in (coverage, exposed, leak))
        failed = leak | exposed.any(axis=1)
        if failed.any():
            break
    m = len(failed)
    faulty = np.zeros(n, dtype=bool)
    faulty[faults] = True
    alpha = 0.2 if scenario == "few_repairs" else p.alpha
    kappa = np.array(p.kappa)
    if scenario == "many_maskers":
        masker = int(np.argmax(p.psi))
        kappa = kappa.copy()
        kappa[masker] *= 5.0
        kappa /= kappa.sum()
    observations, variants = [], []
    for s in range(n):
        count = int(rng.poisson(4.0))
        if scenario == "half_variants":
            count = int(rng.binomial(count, 0.5))
        repair = int(rng.integers(count)) if faulty[s] and count and rng.random() < alpha else -1
        failing = np.flatnonzero(coverage[:, s] & failed)
        passing = np.flatnonzero(coverage[:, s] & ~failed)
        for v in range(count):
            if v == repair:
                column = int(np.flatnonzero(faults == s)[0])
                others = np.delete(exposed, column, axis=1).any(axis=1) | leak
                sole = exposed[:, column] & ~others
                flips = rng.random(len(failing)) < np.where(sole[failing], p.gamma[0], p.delta)
                breaks = rng.random(len(passing)) < p.beta[0]
            else:
                kind = int(rng.choice(len(kappa), p=kappa))
                flips = rng.random(len(failing)) < p.psi[kind]
                breaks = rng.random(len(passing)) < p.eta[kind]
            observations.append(VariantObservation(s, failing, flips, len(passing), int(breaks.sum())))
            behaviour = ["bad" if f else "ok" for f in failed]
            for j, flip in zip(failing, flips):
                behaviour[j] = "ok" if flip else "bad"
            for j, broken in zip(passing, breaks):
                behaviour[j] = "broken" if broken else "ok"
            variants.append((s + 1, behaviour))
    return SyntheticCase(coverage, failed, faulty, observations, variants)


def _evidence(case: SyntheticCase):
    n = case.coverage.shape[1]
    base = ["bad" if f else "ok" for f in case.failed]
    return mutation_evidence(list(range(1, n + 1)), case.coverage, case.failed, base, ["ok"] * len(base), case.variants)


def run_synthetic(v4_path: Path = config.RESULTS_DIR / "v4", out_path: Path = SYNTHETIC_DIR,
                  log: Callable[[str], None] = print) -> Path:
    """Run every scenario and write ``results/v4_synthetic``."""
    fitted = json.loads((v4_path / "fitted_on_d1.json").read_text(encoding="utf-8"))
    iv = fitted["interventional"]
    true_iv = InterventionParams(iv["alpha"], tuple(iv["rho"]), tuple(iv["gamma"]), tuple(iv["beta"]), tuple(iv["kappa"]),
                                 tuple(iv["psi"]), tuple(iv["eta"]), 1.0, "exclusive", "generating parameters (from D1)")
    model = fitted["model_params"]
    world = World(true_iv, tuple(model["theta_grid"]), tuple(model["theta_weights"]), model["leak"])
    out = ex.OutputDir(out_path)

    rng = np.random.default_rng([config.SEED, 77])
    training = [simulate(rng, world, 1, "well_specified") for _ in range(TRAINING_PROGRAMS)]
    learned, counts = estimate_intervention_params([(c.observations, c.faulty) for c in training],
                                                   "simulated single-fault programs", config.IV_NONREPAIR_KINDS,
                                                   config.IV_REPAIR_KINDS, "exclusive")
    fusion, _ = estimate_fusion_params([FusionCase(_evidence(c), c.faulty) for c in training], "simulated single-fault programs")
    out.write_json("parameters.json", {"generating": true_iv.to_dict(), "estimated_from_single_fault_simulations": learned.to_dict(),
                                       "estimation": counts, "version3_tables": fusion.to_dict(),
                                       "theta_grid": world.theta_grid, "theta_weights": world.theta_weights, "leak": world.leak})

    rows, records = [], []
    for scenario in SCENARIOS:
        for n_faults in ((4,) if scenario == "four_faults" else (1, 2, 3)):
            rng = np.random.default_rng([config.SEED, 78, SCENARIOS.index(scenario), n_faults])
            for index in range(PROGRAMS_PER_CELL):
                case = simulate(rng, world, n_faults, scenario)
                n = case.coverage.shape[1]
                evidence = _evidence(case)
                prior = np.full(n, size_aware_prior(n, fusion.mu))
                common = (prior, case.coverage, case.failed, case.observations)
                grid = (world.theta_grid, world.theta_weights, world.leak, config.IV_MAX_FAULTS)
                enumeration = enumerate_configurations(*common, learned, *grid)
                main = summarise(enumeration)
                fused_prior = effective_prior(n, 0.0, fusion, evidence, size_aware=True, use_mutation=True)
                scores = {
                    "ochiai": baselines.ochiai(case.coverage, case.failed),
                    "muse": evidence.muse,
                    "pcg_spectrum": summarise(enumerate_configurations(*common, None, *grid)).marginals,
                    "pcg_fused": infer(FaultModel(fused_prior, case.coverage, case.failed, world.theta_grid, world.leak,
                                                  world.theta_weights)).marginals,
                    "iv_c1": summarise(enumeration, max_faults=1).marginals,
                    "iv": main.marginals,
                    "iv_true": summarise(enumerate_configurations(*common, true_iv, *grid)).marginals,
                }
                faults = np.flatnonzero(case.faulty).tolist()
                row = {"scenario": scenario, "n_faults": n_faults, "program": f"{scenario}-{n_faults}-{index}",
                       "n_statements": n, "expected_faults": main.expected_faults, "boundary_mass": main.boundary_mass}
                for method, values in scores.items():
                    row[f"{method}.ap"] = metrics.average_precision(values, faults)
                    row[f"{method}.first_top1"] = metrics.multi_fault_metrics(values, faults)["first_top1"]
                rows.append(row)
                records.append({"scenario": scenario, "n_faults": n_faults, "labels": case.faulty.astype(int).tolist(),
                                **{m: np.round(scores[m], 6).tolist() for m in PROB_METHODS}})
        log(f"    {scenario}: done")
    out.write_csv("per_case.csv", rows)

    summary: dict = {}
    for scenario in SCENARIOS:
        for n_faults in sorted({r["n_faults"] for r in rows if r["scenario"] == scenario}):
            subset = [r for r in rows if r["scenario"] == scenario and r["n_faults"] == n_faults]
            recs = [r for r in records if r["scenario"] == scenario and r["n_faults"] == n_faults]
            y = np.concatenate([np.asarray(r["labels"], dtype=float) for r in recs])
            base = np.concatenate([np.full(len(r["labels"]), sum(r["labels"]) / len(r["labels"])) for r in recs])
            cell = {"programs": len(subset), "mean_expected_faults": float(np.mean([r["expected_faults"] for r in subset])),
                    "mean_boundary_mass": float(np.mean([r["boundary_mass"] for r in subset])), "methods": {}}
            for method in METHODS:
                ap = np.array([r[f"{method}.ap"] for r in subset])
                entry = {"map": float(ap.mean()), "map_se": float(ap.std(ddof=1) / np.sqrt(len(ap))),
                         "first_top1": float(np.mean([r[f"{method}.first_top1"] for r in subset]))}
                if method in PROB_METHODS:
                    p = np.concatenate([np.asarray(r[method], dtype=float) for r in recs])
                    entry.update(brier=metrics.brier_score(p, y), skill=metrics.brier_skill(p, y, base),
                                 log_loss=metrics.log_loss(p, y), ece=metrics.expected_calibration_error(p, y))
                cell["methods"][method] = entry
            summary[f"{scenario}|{n_faults}"] = cell
    out.write_json("summary.json", summary)
    (out.path / "SUMMARY.md").write_text(_markdown(summary), encoding="utf-8", newline="\n")
    _figure(out.path, summary)
    out.finish({"counts": {"simulated_programs": len(rows), "training_programs": TRAINING_PROGRAMS}})
    return out.path


LABELS = {"ochiai": "Ochiai", "muse": "MUSE", "pcg_spectrum": "PCG spectrum only", "pcg_fused": "PCG v3 fused",
          "iv_c1": "IV, at most 1 fault", "iv": "IV", "iv_true": "IV with the generating parameters"}


def _markdown(summary: dict) -> str:
    out = ["# Synthetic study (generated)", "",
           "**Simulated programs, not real ones.** Generated by `pcg.synthetic`; see its module text for the scenarios.",
           f"Each cell: {PROGRAMS_PER_CELL} simulated programs. IV uses parameters estimated from {TRAINING_PROGRAMS} "
           "simulated single-fault programs of the well-specified scenario.", "",
           "## Mean average precision", "", "| Scenario | Faults | " + " | ".join(LABELS[m] for m in METHODS) + " | Mean inferred faults |",
           "|---|---|" + "---|" * (len(METHODS) + 1)]
    for key, cell in summary.items():
        scenario, faults = key.split("|")
        out.append(f"| {scenario} | {faults} | " + " | ".join(f"{cell['methods'][m]['map']:.3f}" for m in METHODS)
                   + f" | {cell['mean_expected_faults']:.2f} |")
    out += ["", "## Quality of probabilities", "", "| Scenario | Faults | Method | Brier | Skill vs base rate | Log loss | ECE |", "|---|---|---|---|---|---|---|"]
    for key, cell in summary.items():
        scenario, faults = key.split("|")
        for m in PROB_METHODS:
            e = cell["methods"][m]
            out.append(f"| {scenario} | {faults} | {LABELS[m]} | {e['brier']:.4f} | {e['skill']:+.3f} | {e['log_loss']:.4f} | {e['ece']:.4f} |")
    return "\n".join(out) + "\n"


def _figure(path: Path, summary: dict) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    from .v4_report import _save, _style
    _style()
    folder = path / "figures"
    folder.mkdir(exist_ok=True)
    colors = {"ochiai": "#9e9e9e", "muse": "#e6a020", "pcg_spectrum": "#7fcdbb", "pcg_fused": "#2c7fb8", "iv_c1": "#f4a582",
              "iv": "#c0392b"}
    scenarios = [s for s in SCENARIOS if s != "four_faults"]
    fig, axes = plt.subplots(2, len(scenarios), figsize=(2.6 * len(scenarios), 5.6), sharex=True, sharey="row")
    for column, scenario in enumerate(scenarios):
        for method, color in colors.items():
            cells = [summary[f"{scenario}|{k}"]["methods"][method] for k in (1, 2, 3)]
            axes[0, column].errorbar([1, 2, 3], [c["map"] for c in cells], yerr=[1.96 * c["map_se"] for c in cells], marker="o",
                                     markersize=3, color=color, linewidth=1.5 if method == "iv" else 0.9, label=LABELS[method], capsize=2)
            if "ece" in cells[0]:
                axes[1, column].plot([1, 2, 3], [c["ece"] for c in cells], marker="o", markersize=3, color=color,
                                     linewidth=1.5 if method == "iv" else 0.9)
        axes[0, column].set_title(scenario.replace("_", " "), fontsize=8, fontweight="bold", loc="left")
        axes[1, column].set_xlabel("true number of faults")
        axes[1, column].set_xticks([1, 2, 3])
    axes[0, 0].set_ylabel("mean average precision")
    axes[1, 0].set_ylabel("expected calibration error")
    axes[0, -1].legend(fontsize=6, loc="lower left")
    fig.suptitle("Simulated programs: ranking and calibration when assumptions hold or are broken", x=0.01, ha="left", fontsize=10)
    fig.tight_layout()
    _save(fig, folder, "fig_synthetic")
