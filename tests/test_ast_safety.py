"""Tests for manim_engine/renderer/ast_safety.py."""
from manim_engine.renderer.ast_safety import validate_python_ast


def test_safe_manim_code_accepted():
    code = """
from manim import Scene, Square, Create

class MyScene(Scene):
    def construct(self):
        sq = Square()
        self.play(Create(sq))
"""
    result = validate_python_ast(code)
    assert result.valid, result.errors


def test_os_import_rejected():
    result = validate_python_ast("import os\nos.system('rm -rf /')")
    assert not result.valid


def test_subprocess_import_rejected():
    result = validate_python_ast("import subprocess\nsubprocess.run(['ls'])")
    assert not result.valid


def test_eval_call_rejected():
    result = validate_python_ast("x = eval('1+1')")
    assert not result.valid


def test_exec_call_rejected():
    result = validate_python_ast("exec('print(1)')")
    assert not result.valid


def test_dunder_reduce_rejected():
    code = """
class Evil:
    def __reduce__(self):
        return (print, ('pwned',))
"""
    result = validate_python_ast(code)
    assert not result.valid


def test_class_mro_escape_rejected():
    code = "x = (1).__class__.__bases__[0].__subclasses__()"
    result = validate_python_ast(code)
    assert not result.valid


def test_open_call_rejected():
    result = validate_python_ast("f = open('/etc/passwd')")
    assert not result.valid


def test_syntax_error_reported():
    result = validate_python_ast("def f(:\n  pass")
    assert not result.valid
    assert "SyntaxError" in result.errors[0]


def test_numpy_and_math_imports_allowed():
    code = "import numpy as np\nimport math\nx = np.array([1,2,3])\ny = math.sqrt(4)"
    result = validate_python_ast(code)
    assert result.valid, result.errors
