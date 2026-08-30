"""
AST safety validator (§13).

In this MVP's primary architecture (Path A: schema-driven), the LLM never
writes Python/Manim code at all — it only emits Scene JSON, which is
parsed by Pydantic (packages/scene_schema) and compiled by a fixed,
hand-written function (manim_engine/renderer/compiler.py). There is no
code string to validate on that path, which is a stronger guarantee than
any AST check could provide.

This validator exists for two reasons even so:
  1. Defense in depth — if a future "fallback path" (§12, generating
     Manim code directly for scenarios the schema can't express) is ever
     enabled, this is the gate it must pass before ever reaching a
     renderer process.
  2. It's reused by the debug CLI as a general "is this Python file safe
     to exec" sanity check on ad-hoc scripts during development.

Never a substitute for the sandbox (§15) — restated as the core invariant
from the spec: no LLM-generated or LLM-influenced code executes outside
the Docker sandbox, ever, regardless of what this validator says.
"""
from __future__ import annotations

import ast
from dataclasses import dataclass, field

# Import allowlist: only these top-level modules may be imported by
# generated code. Nothing filesystem/network/process/reflection related.
ALLOWED_IMPORTS = {
    "manim",
    "numpy",
    "math",
}

# Attribute/name blocklist: catches the most common escape hatches even
# if reached through an allowed module (e.g. `numpy.testing` weirdness,
# or builtins smuggled through getattr chains).
BLOCKED_NAMES = {
    "eval", "exec", "compile", "__import__",
    "open", "input",
    "os", "sys", "subprocess", "shutil", "socket", "requests", "urllib",
    "pathlib", "importlib", "pickle", "marshal", "ctypes",
    "globals", "locals", "vars", "getattr", "setattr", "delattr",
    "__builtins__", "__loader__", "__spec__",
}

BLOCKED_ATTRS = {
    "__globals__", "__code__", "__closure__", "__class__", "__bases__",
    "__subclasses__", "__mro__", "__dict__", "__builtins__",
}


@dataclass
class ASTValidationResult:
    valid: bool
    errors: list[str] = field(default_factory=list)

    def as_repair_context(self) -> str:
        return "; ".join(self.errors)


class _SafetyVisitor(ast.NodeVisitor):
    def __init__(self) -> None:
        self.errors: list[str] = []

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            top = alias.name.split(".")[0]
            if top not in ALLOWED_IMPORTS:
                self.errors.append(f"line {node.lineno}: import of '{alias.name}' is not allowed")
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        top = (node.module or "").split(".")[0]
        if top not in ALLOWED_IMPORTS:
            self.errors.append(f"line {node.lineno}: import from '{node.module}' is not allowed")
        self.generic_visit(node)

    def visit_Name(self, node: ast.Name) -> None:
        if node.id in BLOCKED_NAMES:
            self.errors.append(f"line {node.lineno}: use of '{node.id}' is not allowed")
        self.generic_visit(node)

    def visit_Attribute(self, node: ast.Attribute) -> None:
        if node.attr in BLOCKED_ATTRS:
            self.errors.append(f"line {node.lineno}: access to '.{node.attr}' is not allowed")
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        func = node.func
        if isinstance(func, ast.Name) and func.id in BLOCKED_NAMES:
            self.errors.append(f"line {node.lineno}: call to '{func.id}()' is not allowed")
        self.generic_visit(node)

    # Dunder-method definitions are a classic sandbox-escape vector
    # (overriding __reduce__, __del__, etc. to run code at unexpected
    # times) — block any except the handful Manim scenes legitimately need.
    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        dunder_allowlist = {"__init__", "construct", "setup", "tear_down"}
        if node.name.startswith("__") and node.name.endswith("__") and node.name not in dunder_allowlist:
            self.errors.append(f"line {node.lineno}: defining '{node.name}' is not allowed")
        self.generic_visit(node)


def validate_python_ast(source_code: str) -> ASTValidationResult:
    try:
        tree = ast.parse(source_code)
    except SyntaxError as e:
        return ASTValidationResult(valid=False, errors=[f"SyntaxError: {e.msg} (line {e.lineno})"])

    visitor = _SafetyVisitor()
    visitor.visit(tree)

    if visitor.errors:
        return ASTValidationResult(valid=False, errors=visitor.errors)
    return ASTValidationResult(valid=True)
