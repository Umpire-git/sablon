"""Güvenli aritmetik ifade değerlendirici.

Tasarım ölçüleri sayı ya da ifade olabilir: "kart_g + 2*bosluk + t".
Böylece "6 kartlık yap" gibi bir değişiklik tüm bağlı ölçülere yayılır.
"""
from __future__ import annotations

import ast
import math
import operator
import re

_BIN = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul, ast.Div: operator.truediv,
        ast.Pow: operator.pow, ast.Mod: operator.mod, ast.FloorDiv: operator.floordiv}
_FUN = {"min": min, "max": max, "round": round, "abs": abs, "sqrt": math.sqrt, "ceil": math.ceil,
        "floor": math.floor, "sin": lambda d: math.sin(math.radians(d)), "cos": lambda d: math.cos(math.radians(d)),
        "tan": lambda d: math.tan(math.radians(d))}
_CONST = {"pi": math.pi}


class ExprError(ValueError):
    pass


def evaluate(expr, env: dict[str, float]) -> float:
    if isinstance(expr, (int, float)):
        return float(expr)
    s = str(expr).strip()
    if re.fullmatch(r"-?\d+,\d+", s):  # Türkçe ondalık virgül: "12,5"
        s = s.replace(",", ".")
    if s == "":
        raise ExprError("boş ifade")
    try:
        return float(s)
    except ValueError:
        pass
    try:
        tree = ast.parse(s, mode="eval")
    except SyntaxError as e:
        raise ExprError(f"'{s}' çözümlenemedi") from e

    def ev(n):
        if isinstance(n, ast.Expression):
            return ev(n.body)
        if isinstance(n, ast.Constant) and isinstance(n.value, (int, float)):
            return float(n.value)
        if isinstance(n, ast.BinOp) and type(n.op) in _BIN:
            return _BIN[type(n.op)](ev(n.left), ev(n.right))
        if isinstance(n, ast.UnaryOp) and isinstance(n.op, (ast.USub, ast.UAdd)):
            v = ev(n.operand)
            return -v if isinstance(n.op, ast.USub) else v
        if isinstance(n, ast.Name):
            if n.id in env:
                return float(env[n.id])
            if n.id in _CONST:
                return _CONST[n.id]
            raise ExprError(f"'{s}' içinde tanımsız değişken: {n.id}")
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id in _FUN and not n.keywords:
            return float(_FUN[n.func.id](*[ev(a) for a in n.args]))
        raise ExprError(f"'{s}' içinde izin verilmeyen ifade")

    try:
        v = ev(tree)
    except ZeroDivisionError as e:
        raise ExprError(f"'{s}' sıfıra bölme içeriyor") from e
    except (OverflowError, ValueError, TypeError) as e:
        if isinstance(e, ExprError):
            raise
        raise ExprError(f"'{s}' hesaplanamadı ({e})") from e
    if not math.isfinite(v):
        raise ExprError(f"'{s}' sonlu bir sayı vermiyor")
    return v
