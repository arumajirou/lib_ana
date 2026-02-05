# ファイルパス: C:\lib_ana\src\v6\code_executor.py
from __future__ import annotations

import ast
import builtins
from contextlib import redirect_stdout, redirect_stderr
import io
from typing import Any, Dict, Tuple

SAFE_BUILTINS = {
    "print": print,
    "len": len,
    "range": range,
    "min": min,
    "max": max,
    "sum": sum,
    "sorted": sorted,
    "enumerate": enumerate,
    "zip": zip,
    "map": map,
    "filter": filter,
    "list": list,
    "dict": dict,
    "set": set,
    "tuple": tuple,
    "float": float,
    "int": int,
    "str": str,
    "bool": bool,
}

def compile_only(code: str) -> Tuple[bool, str]:
    try:
        ast.parse(code)
        compile(code, "<generated>", "exec")
        return True, "OK"
    except Exception as e:
        return False, f"{type(e).__name__}: {e}"

def run_code(code: str, extra_globals: Dict[str, Any] | None = None, safe_mode: bool = True) -> Dict[str, Any]:
    """生成コードの実行（安全優先の“軽量サンドボックス”）。

    注意:
    - 完全なサンドボックスではありません（Python は本質的に隔離が難しい）。
    - safe_mode=True では builtins と globals を最小化して事故を減らします。
    """
    buf_out = io.StringIO()
    buf_err = io.StringIO()
    glb: Dict[str, Any] = {}
    if safe_mode:
        glb["__builtins__"] = SAFE_BUILTINS
    else:
        glb["__builtins__"] = builtins.__dict__

    if extra_globals:
        glb.update(extra_globals)

    ok, msg = compile_only(code)
    if not ok:
        return {"ok": False, "compile": msg, "stdout": "", "stderr": ""}

    try:
        with redirect_stdout(buf_out), redirect_stderr(buf_err):
            exec(compile(code, "<generated>", "exec"), glb, glb)
        return {"ok": True, "compile": "OK", "stdout": buf_out.getvalue(), "stderr": buf_err.getvalue(), "globals": glb}
    except Exception as e:
        return {"ok": False, "compile": "OK", "stdout": buf_out.getvalue(), "stderr": buf_err.getvalue() + f"\n{type(e).__name__}: {e}"}
