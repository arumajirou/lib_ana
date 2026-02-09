# ファイルパス: C:\lib_ana\src\v6\core\ast_callgraph_v6.py
from __future__ import annotations

import ast
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple

import pandas as pd


@dataclass
class DefInfo:
    qname: str
    file: str
    lineno: int


def _module_name_from_file(root_module: str, root_dir: Path, file_path: Path) -> str:
    rel = file_path.relative_to(root_dir).as_posix()
    if rel.endswith("__init__.py"):
        rel = rel[: -len("__init__.py")]
    if rel.endswith(".py"):
        rel = rel[: -3]
    rel = rel.strip("/")
    if not rel:
        return root_module
    return root_module + "." + rel.replace("/", ".")


def _iter_py_files(root_dir: Path, *, max_files: int = 800) -> List[Path]:
    out: List[Path] = []
    for p in root_dir.rglob("*.py"):
        sp = p.as_posix().lower()
        if "/tests/" in sp or "/test/" in sp or "/.venv/" in sp or "/site-packages/" in sp:
            continue
        out.append(p)
        if len(out) >= max_files:
            break
    return out


class _DefCollector(ast.NodeVisitor):
    def __init__(self, module_name: str):
        self.module_name = module_name
        self.class_stack: List[str] = []
        self.defs: List[DefInfo] = []

    def visit_ClassDef(self, node: ast.ClassDef) -> Any:
        self.class_stack.append(node.name)
        self.generic_visit(node)
        self.class_stack.pop()

    def visit_FunctionDef(self, node: ast.FunctionDef) -> Any:
        q = self.module_name
        if self.class_stack:
            q += "." + ".".join(self.class_stack)
        q += "." + node.name
        self.defs.append(DefInfo(qname=q, file="", lineno=getattr(node, "lineno", 0)))
        self.generic_visit(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> Any:
        self.visit_FunctionDef(node)  # 同様扱い


class _CallCollector(ast.NodeVisitor):
    def __init__(self, module_name: str, *, known_defs: Set[str]):
        self.module_name = module_name
        self.known_defs = known_defs
        self.class_stack: List[str] = []
        self.func_stack: List[str] = []
        self.edges: List[Tuple[str, str, int]] = []  # caller, callee, lineno

    def visit_ClassDef(self, node: ast.ClassDef) -> Any:
        self.class_stack.append(node.name)
        self.generic_visit(node)
        self.class_stack.pop()

    def visit_FunctionDef(self, node: ast.FunctionDef) -> Any:
        self.func_stack.append(node.name)
        self.generic_visit(node)
        self.func_stack.pop()

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> Any:
        self.visit_FunctionDef(node)

    def _current_caller(self) -> Optional[str]:
        if not self.func_stack:
            return None
        q = self.module_name
        if self.class_stack:
            q += "." + ".".join(self.class_stack)
        q += "." + self.func_stack[-1]
        return q

    def _attr_chain(self, node: ast.AST) -> Optional[List[str]]:
        # a.b.c -> ["a","b","c"]
        if isinstance(node, ast.Name):
            return [node.id]
        if isinstance(node, ast.Attribute):
            base = self._attr_chain(node.value)
            if not base:
                return None
            return base + [node.attr]
        return None

    def visit_Call(self, node: ast.Call) -> Any:
        caller = self._current_caller()
        if not caller:
            return self.generic_visit(node)

        callee: Optional[str] = None
        # 1) foo(...)
        if isinstance(node.func, ast.Name):
            name = node.func.id
            # 同一モジュールのトップレベル関数を想定
            cand = f"{self.module_name}.{name}"
            if cand in self.known_defs:
                callee = cand

        # 2) self.method(...) / cls.method(...)
        if callee is None and isinstance(node.func, ast.Attribute):
            chain = self._attr_chain(node.func)
            if chain and len(chain) >= 2:
                base = chain[0]
                meth = chain[-1]
                if base in {"self", "cls"} and self.class_stack:
                    cand = f"{self.module_name}." + ".".join(self.class_stack) + f".{meth}"
                    if cand in self.known_defs:
                        callee = cand

        if callee and caller in self.known_defs:
            self.edges.append((caller, callee, int(getattr(node, "lineno", 0))))

        self.generic_visit(node)


def build_ast_call_edges(
    nodes: pd.DataFrame,
    *,
    root_module: str,
    max_files: int = 600,
    max_edges: int = 30000,
) -> pd.DataFrame:
    'AST(抽象構文木)で「同一ライブラリ内」の呼び出し関係を推定する。'
    try:
        import importlib
        m = importlib.import_module(root_module)
    except Exception:
        return pd.DataFrame()

    mod_file = getattr(m, "__file__", None)
    if not mod_file:
        return pd.DataFrame()
    root_dir = Path(mod_file).parent

    py_files = _iter_py_files(root_dir, max_files=max_files)
    if not py_files:
        return pd.DataFrame()

    defs: List[DefInfo] = []
    # Pass1: defs
    for fp in py_files:
        try:
            src = fp.read_text(encoding="utf-8", errors="replace")
            tree = ast.parse(src)
        except Exception:
            continue
        mod_name = _module_name_from_file(root_module, root_dir, fp)
        dc = _DefCollector(mod_name)
        try:
            dc.visit(tree)
        except Exception:
            continue
        for d in dc.defs:
            defs.append(DefInfo(qname=d.qname, file=str(fp), lineno=d.lineno))

    known = {d.qname for d in defs}
    if not known:
        return pd.DataFrame()

    # ノードPath -> ID のマップ（存在するものだけ）
    path_to_id: Dict[str, str] = {}
    if nodes is not None and not nodes.empty and "Path" in nodes.columns and "ID" in nodes.columns:
        for _, r in nodes[["Path", "ID"]].dropna().iterrows():
            path_to_id[str(r["Path"])] = str(r["ID"])

    # Pass2: edges
    edges: List[Dict[str, Any]] = []
    seen: Set[Tuple[str, str, str, int]] = set()

    for fp in py_files:
        if len(edges) >= max_edges:
            break
        try:
            src = fp.read_text(encoding="utf-8", errors="replace")
            tree = ast.parse(src)
        except Exception:
            continue
        mod_name = _module_name_from_file(root_module, root_dir, fp)
        cc = _CallCollector(mod_name, known_defs=known)
        try:
            cc.visit(tree)
        except Exception:
            continue

        for caller, callee, ln in cc.edges:
            key = (caller, callee, str(fp), int(ln))
            if key in seen:
                continue
            seen.add(key)
            edges.append(
                {
                    "Caller": path_to_id.get(caller, caller),
                    "Callee": path_to_id.get(callee, callee),
                    "CallerPath": caller,
                    "CalleePath": callee,
                    "File": str(fp),
                    "Line": int(ln),
                }
            )
            if len(edges) >= max_edges:
                break

    return pd.DataFrame(edges)
