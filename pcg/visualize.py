"""Figures. Every figure is drawn from data computed elsewhere; nothing here
computes or alters a result."""

from __future__ import annotations

from pathlib import Path
from typing import Sequence

import matplotlib

matplotlib.use("Agg")  # never open a window; the pipeline must run unattended
import matplotlib.pyplot as plt  # noqa: E402
import networkx as nx  # noqa: E402
import numpy as np  # noqa: E402

METHOD_LABELS = {
    "chance": "Chance",
    "execution_only": "Execution only (ef)",
    "simple_heuristic": "Heuristic (ef - ep)",
    "tarantula": "Tarantula",
    "ochiai": "Ochiai",
    "pcg_fixed_theta": "PCG, fixed theta",
    "pcg": "PCG",
    "pcg_slice": "PCG + slicing",
    "pcg_static": "PCG + static",
}


def draw_graph(graph: nx.DiGraph, path: Path, title: str) -> None:
    """Draw the constraint graph: variables, statements (coloured by posterior), tests."""
    statements = sorted((d["line"], n) for n, d in graph.nodes(data=True) if d["kind"] == "statement")
    tests = sorted((d["index"], n) for n, d in graph.nodes(data=True) if d["kind"] == "test")
    variables = sorted(n for n, d in graph.nodes(data=True) if d["kind"] == "variable")
    diagnostics = sorted(n for n, d in graph.nodes(data=True) if d["kind"] == "diagnostic")

    def column(nodes: Sequence[str], x: float) -> dict:
        count = max(len(nodes), 1)
        return {node: (x, 1.0 - (i + 0.5) / count) for i, node in enumerate(nodes)}

    pos = {}
    pos.update(column(variables, 0.0))
    pos.update(column([n for _, n in statements], 1.0))
    pos.update(column([n for _, n in tests], 2.0))
    pos.update({n: (0.55, pos[f"s:{graph.nodes[n]['line']}"][1] + 0.03) for n in diagnostics})

    height = max(5.0, 0.55 * max(len(statements), len(tests), len(variables)))
    fig, ax = plt.subplots(figsize=(13, height))
    styles = {
        "use": dict(edge_color="#b0b0b0", style="dotted", width=0.8),
        "def": dict(edge_color="#b0b0b0", style="solid", width=0.8),
        "data": dict(edge_color="#7f7fbf", style="dotted", width=1.0, connectionstyle="arc3,rad=0.35"),
        "control": dict(edge_color="#3f7f3f", style="dashed", width=1.0, connectionstyle="arc3,rad=-0.35"),
        "executed": dict(edge_color="#d0d0d0", style="dotted", width=0.8),
        "flags": dict(edge_color="#cc7a00", style="solid", width=1.2),
    }
    for kind, style in styles.items():
        edges = [(u, v) for u, v, d in graph.edges(data=True) if d["kind"] == kind]
        if edges:
            nx.draw_networkx_edges(graph, pos, edgelist=edges, ax=ax, arrowsize=7, node_size=500, **style)
    for failed, colour in ((True, "#c0392b"), (False, "#7fb77f")):
        edges = [(u, v) for u, v, d in graph.edges(data=True)
                 if d["kind"] == "in_scope" and graph.nodes[v]["failed"] == failed]
        if edges:
            nx.draw_networkx_edges(graph, pos, edgelist=edges, ax=ax, edge_color=colour,
                                   width=1.6 if failed else 0.9, arrowsize=7, node_size=500)

    posterior = [graph.nodes[n].get("posterior", 0.0) for _, n in statements]
    drawn = nx.draw_networkx_nodes(graph, pos, nodelist=[n for _, n in statements], node_color=posterior,
                                   cmap="Reds", vmin=0.0, vmax=1.0, node_size=520, edgecolors="black", ax=ax)
    fig.colorbar(drawn, ax=ax, fraction=0.025, pad=0.01, label="posterior P(statement faulty)")
    nx.draw_networkx_nodes(graph, pos, nodelist=variables, node_color="#e8e8f8", node_shape="s",
                           node_size=420, edgecolors="grey", ax=ax)
    for failed, colour in ((True, "#c0392b"), (False, "#7fb77f")):
        nodes = [n for _, n in tests if graph.nodes[n]["failed"] == failed]
        nx.draw_networkx_nodes(graph, pos, nodelist=nodes, node_color=colour, node_shape="D",
                               node_size=320, edgecolors="black", ax=ax)
    nx.draw_networkx_nodes(graph, pos, nodelist=diagnostics, node_color="#ffcc66", node_shape="^",
                           node_size=260, edgecolors="black", ax=ax)

    for line, node in statements:
        x, y = pos[node]
        data = graph.nodes[node]
        ax.text(x, y, str(line), ha="center", va="center", fontsize=8, fontweight="bold",
                color="white" if data.get("posterior", 0.0) > 0.55 else "black")
        box = dict(facecolor="white", alpha=0.85, edgecolor="none", pad=0.6)
        ax.text(x + 0.06, y + 0.012, f"{data['code'][:44]}", fontsize=7, va="bottom", family="monospace", bbox=box)
        note = f"p = {data.get('posterior', float('nan')):.3f}"
        if "posterior_fused" in data:
            note += f"   fused = {data['posterior_fused']:.3f}"
        if graph.has_node(f"m:{line}"):
            note += f"   mutation level {graph.nodes[f'm:{line}']['level']}"
        ax.text(x + 0.06, y - 0.012, note, fontsize=7, va="top", color="#8b0000", bbox=box)
    for name in variables:
        x, y = pos[name]
        ax.text(x - 0.05, y, graph.nodes[name]["name"], ha="right", va="center", fontsize=8, family="monospace")
    for index, node in tests:
        x, y = pos[node]
        ax.text(x + 0.05, y, f"test {index}: {'FAIL' if graph.nodes[node]['failed'] else 'pass'}",
                ha="left", va="center", fontsize=8)
    ax.text(0.0, 1.04, "variables", ha="center", fontsize=10, fontweight="bold")
    ax.text(1.0, 1.04, "statements  F_i (latent)", ha="center", fontsize=10, fontweight="bold")
    ax.text(2.0, 1.04, "tests  T_j (observed)", ha="center", fontsize=10, fontweight="bold")
    ax.set_title(title + "\nred/green: statement is a noisy-OR parent of a failing/passing test; "
                 "dashed green: control dependence; dotted blue: data dependence", fontsize=9)
    ax.set_xlim(-0.35, 2.45)
    ax.set_ylim(-0.03, 1.08)
    ax.axis("off")
    fig.tight_layout()
    fig.savefig(path, dpi=130)
    plt.close(fig)


def plot_method_comparison(overall: dict, path: Path, n_cases: int, n_programs: int) -> None:
    """Bar chart of Top-1, Top-3 and MRR with cluster-bootstrap 95% intervals."""
    methods = [m for m in METHOD_LABELS if m in overall]
    keys = [("top1", "Top-1"), ("top3", "Top-3"), ("reciprocal_rank", "MRR")]
    fig, axes = plt.subplots(1, 3, figsize=(14, 4.2), sharey=True)
    for ax, (key, label) in zip(axes, keys):
        means = np.array([overall[m][key]["mean"] for m in methods])
        low = means - np.array([overall[m][key]["ci_low"] for m in methods])
        high = np.array([overall[m][key]["ci_high"] for m in methods]) - means
        colours = ["#c0392b" if m.startswith("pcg") else "#7f8c8d" for m in methods]
        ax.barh(range(len(methods)), means, xerr=[low, high], color=colours, capsize=3)
        ax.set_yticks(range(len(methods)))
        ax.set_yticklabels([METHOD_LABELS[m] for m in methods])
        ax.set_xlim(0, 1)
        ax.set_title(label)
        ax.invert_yaxis()
        ax.grid(axis="x", alpha=0.3)
    fig.suptitle(f"Single-fault localisation, {n_cases} detected mutants of {n_programs} programs "
                 "(leave-one-program-out; bars: 95% cluster-bootstrap interval)", fontsize=10)
    fig.tight_layout()
    fig.savefig(path, dpi=130)
    plt.close(fig)


def plot_reliability(calibration: dict, path: Path) -> None:
    """Reliability diagram: predicted fault probability vs observed fault frequency."""
    variants = [v for v in ("pcg_fixed_theta", "pcg", "pcg_static") if v in calibration]
    fig, axes = plt.subplots(1, len(variants), figsize=(4.6 * len(variants), 4.4), sharey=True)
    for ax, variant in zip(np.atleast_1d(axes), variants):
        data = calibration[variant]["all_valid_mutants"]
        rows = [r for r in data["reliability"] if r["count"]]
        ax.plot([0, 1], [0, 1], linestyle="--", color="grey", label="perfect calibration")
        ax.plot([r["mean_predicted"] for r in rows], [r["observed_frequency"] for r in rows],
                marker="o", color="#c0392b", label="observed")
        for r in rows:
            ax.annotate(str(r["count"]), (r["mean_predicted"], r["observed_frequency"]),
                        textcoords="offset points", xytext=(4, -10), fontsize=7, color="grey")
        ax.set_title(f"{METHOD_LABELS[variant]}\nBrier {data['brier']:.3f}, ECE {data['ece']:.3f}", fontsize=10)
        ax.set_xlabel("predicted P(statement faulty)")
        ax.grid(alpha=0.3)
    np.atleast_1d(axes)[0].set_ylabel("observed fraction faulty")
    np.atleast_1d(axes)[0].legend(fontsize=8, loc="upper left")
    fig.suptitle("Reliability of the posteriors (out-of-fold; small numbers = statements per bin)", fontsize=10)
    fig.tight_layout()
    fig.savefig(path, dpi=130)
    plt.close(fig)


def plot_sensitivity(rows: Sequence[dict], reference_leak: float, path: Path) -> None:
    """Heat maps of Top-1 and Brier score over hand-set (theta, prior) values."""
    grid = [r for r in rows if abs(r["leak"] - reference_leak) < 1e-15]
    thetas = sorted({r["theta"] for r in grid})
    priors = sorted({r["prior_fault"] for r in grid})
    thetas = [t for t in thetas if sum(1 for r in grid if r["theta"] == t) == len(priors)]
    fig, axes = plt.subplots(1, 2, figsize=(11, 4))
    for ax, key, title in zip(axes, ("top1", "brier"), ("Top-1 accuracy", "Brier score (lower is better)")):
        matrix = np.array([[next(r[key] for r in grid if r["theta"] == t and r["prior_fault"] == p)
                            for p in priors] for t in thetas])
        image = ax.imshow(matrix, cmap="viridis", aspect="auto")
        ax.set_xticks(range(len(priors)))
        ax.set_xticklabels([f"{p:g}" for p in priors])
        ax.set_yticks(range(len(thetas)))
        ax.set_yticklabels([f"{t:g}" for t in thetas])
        ax.set_xlabel("prior fault probability (hand-set)")
        ax.set_ylabel("exposure rate theta (hand-set, fixed)")
        ax.set_title(title, fontsize=10)
        for i in range(len(thetas)):
            for j in range(len(priors)):
                ax.text(j, i, f"{matrix[i, j]:.3f}", ha="center", va="center", color="white", fontsize=8)
        fig.colorbar(image, ax=ax)
    fig.suptitle("Sensitivity of the fixed-theta model to hand-set parameters", fontsize=10)
    fig.tight_layout()
    fig.savefig(path, dpi=130)
    plt.close(fig)
