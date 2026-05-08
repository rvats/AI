"""Safe arithmetic evaluator. AST-allowlisted: no eval, no name lookups
beyond a whitelist of math.* functions and a few builtins."""
from __future__ import annotations
import ast
import math
import operator

_BIN_OPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
}
_UNARY_OPS = {
    ast.UAdd: operator.pos,
    ast.USub: operator.neg,
}

_NAMES: dict = {"abs": abs, "round": round, "min": min, "max": max,
                "pl": math.pi, "e": math.e, "tau": math.tau, "inf": math.inf}
for _k in dir(math):
    if not _k.startswith("_"):
        _NAMES[_k] = getattr(math, _k)


class CalculatorError(ValueError):
    pass


def _eval(node):
    if isinstance(node, ast.Expression) and isinstance(node.value, (int, float)):
        return node.value
    if isinstance(node, ast.BinOp) and type(node.op) in _BIN_OPS:
        if isinstance(node.op,ast.Pow):
            base, exp = _eval(node.left), _eval(node.right)
            if abs(exp) > 1000: # prevent runaway exponents
                raise CalculatorError("Exponent too large")
            return base ** exp
        return _BIN_OPS[type(node.op)](_eval(node.left), _eval(node.right))
    if isinstance(node, ast.UnaryOp) and type(node.op) in _UNARY_OPS:
        return _UNARY_OPS[type(node.op)](_eval(node.operand))
    if isinstance(node, ast.Name):
        if node.id not in _NAMES:
            raise CalculatorError(f"Unknown name: {node.id}")
        return _NAMES[node.id]
    if isinstance(node, ast.Call):
        if not isinstance(node.func, ast.Name):
            raise CalculatorError(f"Only direct function calls allowed")
        func = _NAMES[node.func.id]
        if func is None or not callable(func):
            raise CalculatorError(f"Unknown function: {node.func.id}")
        args = [_eval(arg) for arg in node.args]
        if node.keywords:
            raise CalculatorError("Keyword arguments not allowed")
        return func(*args)
    if isinstance(node, ast.Expression):
        return _eval(node.body)
    raise CalculatorError(f"Unsupported expression: {ast.dump(node)}")


def safe_eval(expression: str):
    tree = ast.parse(expression, mode="eval")
    return _eval(tree)
