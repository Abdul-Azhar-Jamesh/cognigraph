"""Controlled fault injection (mutation operators) on canonical source.

Every mutant differs from its parent in exactly one AST node, and therefore in
exactly one source line. That line is the ground-truth fault location; it is
*derived by diffing the two texts*, not taken from the operator's own claim,
and is stored separately from everything the inference code can see.

Operators (each replacement is listed explicitly; nothing is random):

==========  ===========  ====================================================
operator    category     transformation
==========  ===========  ====================================================
ROR-flip    comparison   ``<``->``>``, ``<=``->``>=``, ``>``->``<``,
                         ``>=``->``<=``, ``==``<->``!=``
ROR-bound   boundary     ``<``<->``<=``, ``>``<->``>=``
CRP         off_by_one   integer constant ``c`` -> ``c+1`` and ``c-1``
LCR         boolean      ``and``<->``or``
NEG         boolean      negate the condition of ``if`` / ``while``
MEM         boolean      ``in``<->``not in``
AOR         arithmetic   ``+``<->``-``, ``*``->``+``, ``/``->``*``,
                         ``//``->``*``, ``%``->``*`` (also in ``x op= y``)
BCR         return_value ``True``<->``False``
JMP         control_flow ``break``<->``continue``
SDL         omission     delete an assignment or expression statement
                         (the line is kept as ``pass`` so line numbers do not move)
==========  ===========  ====================================================
"""

from __future__ import annotations

import ast
import copy
from dataclasses import dataclass
from typing import Callable, Iterator, Optional

from .program import Program, body_statements, find_function

_ROR_FLIP = {ast.Lt: ast.Gt, ast.LtE: ast.GtE, ast.Gt: ast.Lt, ast.GtE: ast.LtE, ast.Eq: ast.NotEq, ast.NotEq: ast.Eq}
_ROR_BOUND = {ast.Lt: ast.LtE, ast.LtE: ast.Lt, ast.Gt: ast.GtE, ast.GtE: ast.Gt}
_MEMBERSHIP = {ast.In: ast.NotIn, ast.NotIn: ast.In}
_AOR = {ast.Add: ast.Sub, ast.Sub: ast.Add, ast.Mult: ast.Add, ast.Div: ast.Mult, ast.FloorDiv: ast.Mult, ast.Mod: ast.Mult}
_SYMBOL = {
    ast.Lt: "<", ast.LtE: "<=", ast.Gt: ">", ast.GtE: ">=", ast.Eq: "==", ast.NotEq: "!=",
    ast.In: "in", ast.NotIn: "not in", ast.Add: "+", ast.Sub: "-", ast.Mult: "*", ast.Div: "/",
    ast.FloorDiv: "//", ast.Mod: "%", ast.And: "and", ast.Or: "or",
}


@dataclass(frozen=True)
class Mutant:
    """A program version with one injected fault.

    Attributes:
        mutant_id: stable identifier ``<line>:<operator>:<n>``.
        operator / category: which transformation produced it.
        description: human-readable account of the exact change.
        source: full mutated source (canonical form).
        line: ground-truth fault line, the single line that differs.
    """

    mutant_id: str
    operator: str
    category: str
    description: str
    source: str
    line: int


# An edit is (operator, category, description, function that mutates the node in place).
_Edit = tuple[str, str, str, Callable[[ast.AST], Optional[ast.AST]]]


def _edits_for(node: ast.AST) -> Iterator[_Edit]:
    """Yield every single-node edit applicable to ``node``."""
    if isinstance(node, ast.Compare):
        for position, op in enumerate(node.ops):
            for table, name, category in ((_ROR_FLIP, "ROR-flip", "comparison"),
                                          (_ROR_BOUND, "ROR-bound", "boundary"),
                                          (_MEMBERSHIP, "MEM", "boolean")):
                new = table.get(type(op))
                if new is not None:
                    def apply(n, position=position, new=new):
                        n.ops[position] = new()
                    yield name, category, f"'{_SYMBOL[type(op)]}' -> '{_SYMBOL[new]}'", apply
    elif isinstance(node, ast.BoolOp):
        new = ast.Or if isinstance(node.op, ast.And) else ast.And

        def apply(n, new=new):
            n.op = new()
        yield "LCR", "boolean", f"'{_SYMBOL[type(node.op)]}' -> '{_SYMBOL[new]}'", apply
    elif isinstance(node, (ast.BinOp, ast.AugAssign)):
        new = _AOR.get(type(node.op))
        if new is not None:
            def apply(n, new=new):
                n.op = new()
            yield "AOR", "arithmetic", f"'{_SYMBOL[type(node.op)]}' -> '{_SYMBOL[new]}'", apply
    elif isinstance(node, ast.Constant):
        if type(node.value) is bool:
            def apply(n):
                n.value = not n.value
            yield "BCR", "return_value", f"{node.value} -> {not node.value}", apply
        elif type(node.value) is int:
            for delta in (1, -1):
                def apply(n, delta=delta):
                    n.value = n.value + delta
                yield "CRP", "off_by_one", f"{node.value} -> {node.value + delta}", apply
    elif isinstance(node, (ast.Break, ast.Continue)):
        new = ast.Continue if isinstance(node, ast.Break) else ast.Break

        def apply(n, new=new):
            return ast.copy_location(new(), n)
        yield "JMP", "control_flow", f"{type(node).__name__.lower()} -> {new.__name__.lower()}", apply
    if isinstance(node, (ast.If, ast.While)):
        def negate(n):
            # Remove an existing ``not`` instead of stacking a second one.
            if isinstance(n.test, ast.UnaryOp) and isinstance(n.test.op, ast.Not):
                n.test = n.test.operand
            else:
                n.test = ast.UnaryOp(op=ast.Not(), operand=n.test)
        yield "NEG", "boolean", "negate condition", negate
    if isinstance(node, (ast.Assign, ast.AugAssign, ast.Expr)):
        def delete(n):
            return ast.copy_location(ast.Pass(), n)
        yield "SDL", "omission", "statement deleted (replaced by pass)", delete


def _replace_node(root: ast.AST, target: ast.AST, replacement: ast.AST) -> None:
    for parent in ast.walk(root):
        for field, value in ast.iter_fields(parent):
            if value is target:
                setattr(parent, field, replacement)
                return
            if isinstance(value, list):
                for index, item in enumerate(value):
                    if item is target:
                        value[index] = replacement
                        return
    raise ValueError("node to replace was not found")


def _changed_lines(a: str, b: str) -> Optional[list[int]]:
    lines_a, lines_b = a.splitlines(), b.splitlines()
    if len(lines_a) != len(lines_b):
        return None
    return [i for i, (x, y) in enumerate(zip(lines_a, lines_b), 1) if x != y]


def generate_mutants(program: Program) -> list[Mutant]:
    """All distinct single-edit mutants of ``program``'s function.

    Edits are enumerated in a fixed order (statements top to bottom, nodes in
    ``ast.walk`` order, replacements in table order). An edit is kept only if
    the result parses, differs from the parent in exactly one line, and is not
    textually identical to an earlier mutant.
    """
    tree = ast.parse(program.source)
    func = find_function(tree, program.func_name)
    mutants: list[Mutant] = []
    seen = {program.source}
    counter: dict[tuple[int, str], int] = {}

    for stmt_index, stmt in enumerate(body_statements(func)):
        own_nodes = [stmt] + [n for root in _own_parts(stmt) for n in ast.walk(root)]
        # ``stmt`` may also be yielded by walking its own parts (simple statements).
        unique_nodes = list(dict.fromkeys(own_nodes))
        for node_index, node in enumerate(unique_nodes):
            for edit_index, (operator, category, description, _) in enumerate(_edits_for(node)):
                # Re-locate the same node and edit inside a fresh copy of the tree.
                tree_copy = copy.deepcopy(tree)
                func_copy = find_function(tree_copy, program.func_name)
                stmt_copy = body_statements(func_copy)[stmt_index]
                nodes_copy = list(dict.fromkeys([stmt_copy] + [n for root in _own_parts(stmt_copy) for n in ast.walk(root)]))
                node_copy = nodes_copy[node_index]
                apply = list(_edits_for(node_copy))[edit_index][3]
                replacement = apply(node_copy)
                if replacement is not None:
                    _replace_node(tree_copy, node_copy, replacement)
                ast.fix_missing_locations(tree_copy)
                try:
                    source = ast.unparse(tree_copy) + "\n"
                    ast.parse(source)
                except (SyntaxError, ValueError):
                    continue
                changed = _changed_lines(program.source, source)
                if source in seen or changed is None or len(changed) != 1:
                    continue
                seen.add(source)
                line = changed[0]
                serial = counter.get((line, operator), 0)
                counter[(line, operator)] = serial + 1
                mutants.append(Mutant(f"{line}:{operator}:{serial}", operator, category,
                                      f"line {line}: {description}", source, line))
    return mutants


def _own_parts(stmt: ast.stmt) -> list[ast.AST]:
    """Expression parts of a statement, excluding nested statements."""
    if isinstance(stmt, (ast.If, ast.While)):
        return [stmt.test]
    if isinstance(stmt, (ast.For, ast.AsyncFor)):
        return [stmt.target, stmt.iter]
    if isinstance(stmt, (ast.With, ast.AsyncWith)):
        return list(stmt.items)
    if isinstance(stmt, (ast.Try, ast.Match, ast.FunctionDef, ast.AsyncFunctionDef)):
        return []
    return [stmt]
