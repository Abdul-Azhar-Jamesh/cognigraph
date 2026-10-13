"""Program structure: variables, data dependence, control dependence, slicing.

This module extracts the *program* half of the constraint graph from the AST:

* which variables each statement defines and uses,
* data-dependence edges (``u -> s`` when ``u`` may define a variable ``s`` uses),
* control-dependence edges (``h -> s`` when the branch or loop header ``h``
  decides whether ``s`` runs).

The edges are used in inference through *slicing*: a test's outcome can only be
influenced by the executed statements from which the statement that ended the
test is reachable backwards along dependence edges. The model variant
``scope="slice"`` restricts each test's noisy-OR scope to that set.

The analysis is deliberately conservative (it over-approximates) and
intraprocedural. Its known blind spots are listed in LIMITATIONS.md: faults of
omission (a deleted statement has no dependences) and aliasing through
containers.
"""

from __future__ import annotations

import ast
import builtins
from dataclasses import dataclass
from typing import Iterable, Optional

from .program import Program, body_statements, child_blocks

#: Builtins that never mutate their arguments. Any other call is assumed to be
#: able to modify every variable passed to it.
PURE_BUILTINS = frozenset(
    "abs all any bool chr dict divmod enumerate float int isinstance len list max min "
    "ord pow print range repr reversed round set sorted str sum tuple zip".split()
)
_ELEMENT_ITERATORS = frozenset({"enumerate", "reversed", "zip", "sorted"})


def _own_expressions(stmt: ast.stmt) -> list[ast.AST]:
    """AST parts that belong to the statement itself, not to nested statements."""
    if isinstance(stmt, (ast.If, ast.While)):
        return [stmt.test]
    if isinstance(stmt, (ast.For, ast.AsyncFor)):
        return [stmt.target, stmt.iter]
    if isinstance(stmt, (ast.With, ast.AsyncWith)):
        return list(stmt.items)
    if isinstance(stmt, (ast.Try, ast.FunctionDef, ast.AsyncFunctionDef)):
        return []
    if isinstance(stmt, ast.Match):
        return [stmt.subject]
    return [stmt]


def _base_name(node: ast.AST) -> Optional[str]:
    """``xs`` for ``xs``, ``xs[i]``, ``xs.attr`` and nestings of these."""
    while isinstance(node, (ast.Subscript, ast.Attribute, ast.Starred)):
        node = node.value
    return node.id if isinstance(node, ast.Name) else None


def defs_and_uses(stmt: ast.stmt) -> tuple[set[str], set[str]]:
    """Variables a statement may define and variables it uses."""
    if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef)):
        return {stmt.name}, set()  # a nested ``def`` binds its name
    defs: set[str] = set()
    uses: set[str] = set()
    for root in _own_expressions(stmt):
        for node in ast.walk(root):
            if isinstance(node, ast.Name):
                (uses if isinstance(node.ctx, ast.Load) else defs).add(node.id)
            elif isinstance(node, (ast.Subscript, ast.Attribute)) and isinstance(node.ctx, (ast.Store, ast.Del)):
                base = _base_name(node)  # xs[i] = v  both reads and changes xs
                if base:
                    defs.add(base)
                    uses.add(base)
            elif isinstance(node, ast.AugAssign):
                base = _base_name(node.target)  # x += v  reads x
                if base:
                    defs.add(base)
                    uses.add(base)
            elif isinstance(node, ast.Call):
                if isinstance(node.func, ast.Attribute):
                    base = _base_name(node.func)  # xs.append(v) may change xs
                    if base:
                        defs.add(base)
                pure = isinstance(node.func, ast.Name) and node.func.id in PURE_BUILTINS
                if not pure:
                    for arg in list(node.args) + [kw.value for kw in node.keywords]:
                        base = _base_name(arg)
                        if base:
                            defs.add(base)
    return defs, uses


class _AliasClasses:
    """Union-find over variable names that may refer to the same object."""

    def __init__(self) -> None:
        self._parent: dict[str, str] = {}

    def find(self, name: str) -> str:
        self._parent.setdefault(name, name)
        while self._parent[name] != name:
            self._parent[name] = self._parent[self._parent[name]]
            name = self._parent[name]
        return name

    def union(self, a: str, b: str) -> None:
        self._parent[self.find(a)] = self.find(b)


def _alias_pairs(stmt: ast.stmt) -> Iterable[tuple[str, str]]:
    """Name pairs made aliases by ``a = b``, ``a = b[i]`` or ``for a in b``."""
    if isinstance(stmt, ast.Assign):
        source = _base_name(stmt.value)
        if source:
            for target in stmt.targets:
                for node in ast.walk(target):
                    if isinstance(node, ast.Name):
                        yield node.id, source
    elif isinstance(stmt, (ast.For, ast.AsyncFor)):
        sources = []
        base = _base_name(stmt.iter)
        if base:
            sources.append(base)
        elif (
            isinstance(stmt.iter, ast.Call)
            and isinstance(stmt.iter.func, ast.Name)
            and stmt.iter.func.id in _ELEMENT_ITERATORS
        ):
            sources.extend(filter(None, (_base_name(arg) for arg in stmt.iter.args)))
        for source in sources:
            for node in ast.walk(stmt.target):
                if isinstance(node, ast.Name):
                    yield node.id, source


@dataclass(frozen=True)
class Dependence:
    """Structural relations between the statements of one function.

    Attributes:
        statements: statement line numbers.
        defs / uses: variables defined / used by each statement line.
        data_edges: ``(u, s)`` pairs, ``s`` may read a value written by ``u``.
        control_edges: ``(h, s)`` pairs, header ``h`` controls whether ``s`` runs.
    """

    statements: tuple[int, ...]
    defs: dict[int, frozenset[str]]
    uses: dict[int, frozenset[str]]
    data_edges: frozenset[tuple[int, int]]
    control_edges: frozenset[tuple[int, int]]

    def backward_slice(self, criterion: int) -> frozenset[int]:
        """Statements from which ``criterion`` is reachable (itself included)."""
        parents: dict[int, set[int]] = {line: set() for line in self.statements}
        for source, target in self.data_edges | self.control_edges:
            parents[target].add(source)
        seen = {criterion}
        stack = [criterion]
        while stack:
            for parent in parents.get(stack.pop(), ()):
                if parent not in seen:
                    seen.add(parent)
                    stack.append(parent)
        return frozenset(seen)


def analyze_dependence(program: Program) -> Dependence:
    """Extract def/use sets and dependence edges for ``program``."""
    func = program.func_node
    statements = body_statements(func)
    lines = tuple(stmt.lineno for stmt in statements)

    aliases = _AliasClasses()
    for stmt in statements:
        for a, b in _alias_pairs(stmt):
            aliases.union(a, b)

    raw = {stmt.lineno: defs_and_uses(stmt) for stmt in statements}
    # Names such as ``len`` or ``range`` are builtins, not program variables,
    # unless the function itself binds them.
    local_names = {arg.arg for arg in ast.walk(func.args) if isinstance(arg, ast.arg)}
    local_names |= {name for d, _ in raw.values() for name in d}
    not_variables = set(dir(builtins)) - local_names
    defs: dict[int, frozenset[str]] = {line: frozenset(d) for line, (d, _) in raw.items()}
    uses: dict[int, frozenset[str]] = {line: frozenset(u - not_variables) for line, (_, u) in raw.items()}

    # Data dependence, flow-insensitive: sound for loops, coarse by design.
    def classes(names: Iterable[str]) -> set[str]:
        return {aliases.find(name) for name in names}

    data_edges = {
        (u, s)
        for u in lines
        for s in lines
        if u != s and classes(defs[u]) & classes(uses[s])
    }

    control_edges: set[tuple[int, int]] = set()
    statement_lines = set(lines)

    def subtree_lines(stmt: ast.stmt) -> list[int]:
        """Statement lines nested (at any depth) inside a compound statement."""
        out = []
        for block in child_blocks(stmt):
            for child in block:
                if child.lineno in statement_lines:  # skips docstrings of nested functions
                    out.append(child.lineno)
                out.extend(subtree_lines(child))
        return out

    # Whoever uses a nested function depends on every statement of its body.
    for stmt in statements:
        if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef)):
            data_edges.update((line, stmt.lineno) for line in subtree_lines(stmt))

    def visit(block: list[ast.stmt], ancestors: list[ast.stmt]) -> None:
        for stmt in block:
            if stmt.lineno not in statement_lines:
                continue
            if ancestors:  # nesting: the direct parent header controls the statement
                control_edges.add((ancestors[-1].lineno, stmt.lineno))
            if isinstance(stmt, (ast.Return, ast.Raise)):
                # An early exit decides whether *any* other statement still runs.
                for header in ancestors:
                    control_edges.update((header.lineno, line) for line in lines if line != header.lineno)
            elif isinstance(stmt, (ast.Break, ast.Continue)):
                loop_at = max(
                    (i for i, a in enumerate(ancestors) if isinstance(a, (ast.For, ast.AsyncFor, ast.While))),
                    default=None,
                )
                if loop_at is not None:
                    loop = ancestors[loop_at]
                    affected = [loop.lineno] + subtree_lines(loop)
                    for header in ancestors[loop_at + 1 :]:
                        control_edges.update((header.lineno, line) for line in affected if line != header.lineno)
            for child in child_blocks(stmt):
                visit(child, ancestors + [stmt])

    docstring_free = [s for s in func.body if s.lineno in set(lines)]
    visit(docstring_free, [])
    return Dependence(lines, defs, uses, frozenset(data_edges), frozenset(control_edges))
