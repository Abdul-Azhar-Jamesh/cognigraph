"""The Probabilistic Constraint Graph and its translation into the model.

Node kinds (stable string identifiers):

* ``s:<line>``  statement; carries the latent fault variable ``F_line``.
* ``v:<name>``  program variable.
* ``t:<index>`` test case: an input/output constraint with an observed outcome.
* ``d:<line>:<symbol>`` static-analysis finding attached to a statement.
* ``m:<line>``  mutation-analysis evidence of a statement (version 3): the
  level of the evidence variable and the statement's coverage context.

Edge kinds:

* ``def`` (statement -> variable) and ``use`` (variable -> statement),
* ``data`` (statement -> statement) data dependence,
* ``control`` (header -> statement) control dependence,
* ``executed`` (statement -> test) the test ran the statement,
* ``in_scope`` (statement -> test) the statement is a parent of the test's
  outcome variable in the Bayesian network,
* ``flags`` (finding -> statement),
* ``mutation`` (mutation evidence -> statement).

The Bayesian network is *read off this graph* by :func:`fault_model_from_graph`:
the ``in_scope`` edges are the parent sets of the noisy-OR test factors, and
the ``flags`` edges switch on the static-evidence factor. Changing the graph
changes the posterior.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional, Sequence

import networkx as nx
import numpy as np

from .config import ModelParams
from .dependence import Dependence
from .execution import Spectrum
from .fusion import FusionParams, mutation_likelihood_ratio, size_aware_prior
from .mbfl import MutationEvidence
from .model import FaultModel, apply_likelihood_ratio
from .program import Program
from .static_analysis import Finding


def statement_id(line: int) -> str:
    return f"s:{line}"


def tnode_id(index: int) -> str:
    return f"t:{index}"


def build_graph(
    program: Program,
    spectrum: Spectrum,
    dependence: Dependence,
    scopes: np.ndarray,
    findings: Optional[Sequence[Finding]] = None,
    mutation: Optional[MutationEvidence] = None,
) -> nx.DiGraph:
    """Assemble the constraint graph from extracted structure and raw evidence.

    ``findings=None`` means static analysis was not run (no static evidence);
    an empty list means it ran and reported nothing. ``mutation=None`` means
    no mutation analysis was run.
    """
    graph = nx.DiGraph(func_name=program.func_name, static_analysis_run=findings is not None)
    if mutation is not None:
        graph.graph["mutation_analysis_run"] = True
    for line in program.statements:
        graph.add_node(statement_id(line), kind="statement", line=line, code=program.line_text(line).strip())
    for line in program.statements:
        for name in sorted(dependence.defs[line]):
            graph.add_node(f"v:{name}", kind="variable", name=name)
            graph.add_edge(statement_id(line), f"v:{name}", kind="def")
        for name in sorted(dependence.uses[line]):
            graph.add_node(f"v:{name}", kind="variable", name=name)
            graph.add_edge(f"v:{name}", statement_id(line), kind="use")
    for source, target in sorted(dependence.data_edges):
        graph.add_edge(statement_id(source), statement_id(target), kind="data")
    for source, target in sorted(dependence.control_edges):
        # A pair can be both data- and control-dependent; control is recorded
        # in an attribute so neither relation is lost.
        if graph.has_edge(statement_id(source), statement_id(target)):
            graph.edges[statement_id(source), statement_id(target)]["also_control"] = True
        else:
            graph.add_edge(statement_id(source), statement_id(target), kind="control")
    for j in range(spectrum.n_tests):
        graph.add_node(tnode_id(j), kind="test", index=j, failed=bool(spectrum.failed[j]),
                       exit_kind=spectrum.exit_kinds[j], exit_line=spectrum.exit_lines[j])
        for i, line in enumerate(program.statements):
            if scopes[j, i]:
                graph.add_edge(statement_id(line), tnode_id(j), kind="in_scope")
            elif spectrum.coverage[j, i]:
                graph.add_edge(statement_id(line), tnode_id(j), kind="executed")
    for finding in findings or ():
        if finding.relevant and finding.line in program.statements:
            node = f"d:{finding.line}:{finding.symbol}"
            graph.add_node(node, kind="diagnostic", line=finding.line, symbol=finding.symbol,
                           message=finding.message)
            graph.add_edge(node, statement_id(finding.line), kind="flags")
    if mutation is not None:
        for i, line in enumerate(program.statements):
            node = f"m:{line}"
            graph.add_node(node, kind="mutation_evidence", line=line, level=int(mutation.levels[i]),
                           context=int(mutation.contexts[i]), metallaxis=float(mutation.metallaxis[i]),
                           muse=float(mutation.muse[i]))
            graph.add_edge(node, statement_id(line), kind="mutation")
    return graph


def mutation_evidence_from_graph(graph: nx.DiGraph) -> MutationEvidence:
    """Read the mutation evidence back from the graph's ``m:<line>`` nodes.

    A statement whose evidence node has been removed gets level 0 in context
    "none", for which the model's likelihood ratio is exactly 1.
    """
    lines = statement_lines(graph)
    levels, contexts = np.zeros(len(lines), dtype=int), np.zeros(len(lines), dtype=int)
    metallaxis, muse = np.zeros(len(lines)), np.zeros(len(lines))
    for i, line in enumerate(lines):
        node = f"m:{line}"
        if graph.has_node(node) and graph.has_edge(node, statement_id(line)):
            data = graph.nodes[node]
            levels[i], contexts[i] = data["level"], data["context"]
            metallaxis[i], muse[i] = data["metallaxis"], data["muse"]
    return MutationEvidence(levels, contexts, metallaxis, muse, 0, 0)


def statement_lines(graph: nx.DiGraph) -> list[int]:
    return sorted(data["line"] for _, data in graph.nodes(data=True) if data["kind"] == "statement")


def tnode_indices(graph: nx.DiGraph) -> list[int]:
    return sorted(data["index"] for _, data in graph.nodes(data=True) if data["kind"] == "test")


def static_flags(graph: nx.DiGraph) -> np.ndarray:
    """Boolean vector ``A``: statement has at least one ``flags`` edge."""
    return np.array([
        any(graph.edges[p, statement_id(line)]["kind"] == "flags" for p in graph.predecessors(statement_id(line)))
        for line in statement_lines(graph)
    ], dtype=bool)


def static_likelihood_ratio(flags: np.ndarray, params: ModelParams) -> np.ndarray:
    """``P(A_i | F_i = 1) / P(A_i | F_i = 0)`` for the observed flag values."""
    if params.static_tpr is None or params.static_fpr is None:
        raise ValueError("static-analysis likelihoods were not estimated")
    flagged = params.static_tpr / params.static_fpr
    unflagged = (1.0 - params.static_tpr) / (1.0 - params.static_fpr)
    return np.where(flags, flagged, unflagged)


def fault_model_from_graph(
    graph: nx.DiGraph,
    params: ModelParams,
    use_static: bool = False,
    extra_likelihood_ratio: Optional[np.ndarray] = None,
    *,
    fusion: Optional[FusionParams] = None,
    size_aware: bool = False,
    use_mutation: bool = False,
    use_context: bool = True,
) -> FaultModel:
    """Read the Bayesian network off the graph.

    * one fault variable per statement node, base prior ``params.prior_fault``;
    * one noisy-OR factor per test node whose parents are its ``in_scope``
      predecessors and whose observed value is the node's ``failed`` attribute;
    * optional unary factors: static flags and an extra per-statement
      likelihood ratio (used for the LLM-confidence channel);
    * version 3: with ``size_aware`` the base prior is ``fusion.mu / n``; with
      ``use_mutation`` each statement's ``m:<line>`` node contributes the
      likelihood ratio of its level, conditioned on its coverage context
      unless ``use_context`` is switched off (ablation).
    """
    lines = statement_lines(graph)
    tests = tnode_indices(graph)
    column = {line: i for i, line in enumerate(lines)}
    scopes = np.zeros((len(tests), len(lines)), dtype=bool)
    failed = np.zeros(len(tests), dtype=bool)
    for row, j in enumerate(tests):
        failed[row] = graph.nodes[tnode_id(j)]["failed"]
        for parent in graph.predecessors(tnode_id(j)):
            if graph.edges[parent, tnode_id(j)]["kind"] == "in_scope":
                scopes[row, column[graph.nodes[parent]["line"]]] = True
    if (size_aware or use_mutation) and fusion is None:
        raise ValueError("fusion parameters are required for the size-aware prior and for mutation evidence")
    prior = np.full(len(lines), size_aware_prior(len(lines), fusion.mu) if size_aware else params.prior_fault)
    if use_mutation:
        if not graph.graph.get("mutation_analysis_run", False):
            raise ValueError("mutation evidence requested but mutation analysis was not run")
        prior = apply_likelihood_ratio(
            prior, mutation_likelihood_ratio(mutation_evidence_from_graph(graph), fusion, use_context))
    if use_static:
        if not graph.graph.get("static_analysis_run", False):
            raise ValueError("static evidence requested but static analysis was not run")
        prior = apply_likelihood_ratio(prior, static_likelihood_ratio(static_flags(graph), params))
    if extra_likelihood_ratio is not None:
        prior = apply_likelihood_ratio(prior, np.asarray(extra_likelihood_ratio, dtype=float))
    grid, weights = params.exposure_prior()
    return FaultModel(prior, scopes, failed, grid, params.leak, weights)


def graph_to_json(graph: nx.DiGraph, path: Path) -> None:
    """Write the graph as a deterministic node/edge JSON document."""
    document = {
        "graph": dict(graph.graph),
        "nodes": [{"id": node, **data} for node, data in sorted(graph.nodes(data=True))],
        "edges": [{"source": u, "target": v, **data} for u, v, data in sorted(graph.edges(data=True), key=lambda e: e[:2])],
    }
    path.write_text(json.dumps(document, indent=2, sort_keys=True), encoding="utf-8")
