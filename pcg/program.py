"""Source ingestion: canonical form, compiler diagnostics, statement components.

A *component* of the model is one statement of the function under analysis,
identified by its line number in the **canonical** source (the output of
``ast.unparse``, which puts exactly one statement on each line). Line numbers
are therefore stable identifiers; no memory addresses are involved.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass
from typing import Optional

#: File name given to analysed code when it is compiled and traced.
TARGET_FILENAME = "<pcg-target>"


class ProgramError(ValueError):
    """The source cannot be analysed (does not parse, function missing, ...)."""


@dataclass(frozen=True)
class CompileDiagnostic:
    """A real diagnostic produced by the Python compiler."""

    kind: str
    message: str
    line: Optional[int]
    column: Optional[int]

    def to_dict(self) -> dict:
        return {"kind": self.kind, "message": self.message, "line": self.line, "column": self.column}


def compile_check(source: str) -> Optional[CompileDiagnostic]:
    """Compile ``source`` and return the compiler's diagnostic, or None if it compiles.

    A clean compile is *not* evidence of semantic correctness; it only means
    the tests can be run. The reported line is where the parser gave up, which
    can be after the true mistake.
    """
    try:
        compile(source, TARGET_FILENAME, "exec")
    except SyntaxError as exc:  # includes IndentationError and TabError
        return CompileDiagnostic(type(exc).__name__, exc.msg or "", exc.lineno, exc.offset)
    except ValueError as exc:  # e.g. source containing null bytes
        return CompileDiagnostic("ValueError", str(exc), None, None)
    return None


def canonicalize(source: str) -> str:
    """Return the canonical one-statement-per-line form of ``source``."""
    try:
        tree = ast.parse(source)
    except SyntaxError as exc:
        raise ProgramError(f"source does not parse: {exc.msg} (line {exc.lineno})") from exc
    return ast.unparse(tree) + "\n"


def find_function(tree: ast.Module, name: str) -> ast.FunctionDef:
    """Return the top-level function ``name`` from a parsed module."""
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node
    raise ProgramError(f"no top-level function named {name!r}")


def _is_docstring(stmt: ast.stmt) -> bool:
    return (
        isinstance(stmt, ast.Expr)
        and isinstance(stmt.value, ast.Constant)
        and isinstance(stmt.value.value, str)
    )


def body_statements(func: ast.FunctionDef) -> list[ast.stmt]:
    """All statements inside ``func`` (any nesting depth) in source order.

    Docstrings are skipped because they are never executed. A nested function
    definition is a statement (its ``def`` line runs when the function is
    defined) and the statements of its body are components too. Nested classes
    are rejected: the model has no component for them.
    """
    out: list[ast.stmt] = []

    def visit(stmts: list[ast.stmt], function_body: bool) -> None:
        for index, stmt in enumerate(stmts):
            if function_body and index == 0 and _is_docstring(stmt):
                continue
            if isinstance(stmt, ast.ClassDef):
                raise ProgramError("nested class definitions are not supported")
            out.append(stmt)
            is_function = isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef))
            for child_block in child_blocks(stmt):
                visit(child_block, is_function)

    visit(func.body, True)
    return sorted(out, key=lambda s: s.lineno)


def child_blocks(stmt: ast.stmt) -> list[list[ast.stmt]]:
    """The statement lists nested directly inside a compound statement."""
    blocks: list[list[ast.stmt]] = []
    for field in ("body", "orelse", "finalbody"):
        block = getattr(stmt, field, None)
        if isinstance(block, list) and block and isinstance(block[0], ast.stmt):
            blocks.append(block)
    for handler in getattr(stmt, "handlers", []) or []:
        blocks.append(handler.body)
    for case in getattr(stmt, "cases", []) or []:
        blocks.append(case.body)
    return blocks


@dataclass(frozen=True)
class Program:
    """A function under analysis, in canonical form.

    Attributes:
        source: canonical source text of the whole module.
        func_name: name of the function that the tests call.
        statements: sorted line numbers of the function's statements; these are
            the components (fault variables) of the model.
    """

    source: str
    func_name: str
    statements: tuple[int, ...]

    @classmethod
    def from_source(cls, source: str, func_name: str) -> "Program":
        canonical = canonicalize(source)
        func = find_function(ast.parse(canonical), func_name)
        lines = [stmt.lineno for stmt in body_statements(func)]
        if len(set(lines)) != len(lines):  # cannot happen for canonical source
            raise ProgramError("two statements share a line; source is not canonical")
        if not lines:
            raise ProgramError(f"function {func_name!r} has no statements")
        return cls(canonical, func_name, tuple(lines))

    @property
    def func_node(self) -> ast.FunctionDef:
        return find_function(ast.parse(self.source), self.func_name)

    def line_text(self, line: int) -> str:
        return self.source.splitlines()[line - 1]

    def listing(self) -> str:
        return "\n".join(f"{i:>3}  {text}" for i, text in enumerate(self.source.splitlines(), 1))
