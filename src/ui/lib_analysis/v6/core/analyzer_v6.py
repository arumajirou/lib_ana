# ファイルパス: C:\lib_ana\src\v6\core\analyzer_v6.py
from __future__ import annotations

import ast
import os
import re
import importlib.util
import importlib.metadata
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple


def _safe_read_text(fp: Path) -> str:
    try:
        return fp.read_text(encoding="utf-8", errors="replace")
    except Exception:
        try:
            return fp.read_text(encoding="utf-8-sig", errors="replace")
        except Exception:
            return ""


def _is_probably_test_path(p: str) -> bool:
    s = p.replace("\\", "/").lower()
    return any(x in s for x in ["/tests/", "/test/", "/testing/", "/__pycache__/"])


def _iter_py_files(root_dir: Path, *, max_files: int = 5000) -> List[Path]:
    out: List[Path] = []
    try:
        for fp in root_dir.rglob("*.py"):
            if _is_probably_test_path(fp.as_posix()):
                continue
            out.append(fp)
            if len(out) >= max_files:
                break
    except Exception:
        pass
    return out


def _ast_unparse(node: Optional[ast.AST]) -> str:
    if node is None:
        return ""
    try:
        # Python 3.9+
        return ast.unparse(node)  # type: ignore[attr-defined]
    except Exception:
        return ""


def _ann_to_str(ann: Optional[ast.AST]) -> str:
    s = _ast_unparse(ann)
    return s.strip() if s else ""


def _kind_strings_for_args(args: ast.arguments) -> List[Tuple[str, str, Optional[ast.AST], bool, str]]:
    """ASTから inspect.Parameter っぽい形式へ寄せる。
    返り値: (name, kind, annotation, has_default, default_repr)
    """
    rows: List[Tuple[str, str, Optional[ast.AST], bool, str]] = []

    # defaults: args.args の末尾側に対応、posonlyargs + args にも跨る
    pos = list(args.posonlyargs) + list(args.args)
    defaults = list(args.defaults)
    n_pos = len(pos)
    n_def = len(defaults)
    # 末尾n_def個がデフォルトあり
    def_start = max(0, n_pos - n_def)

    for i, a in enumerate(args.posonlyargs):
        has_def = i >= def_start
        d = defaults[i - def_start] if has_def else None
        rows.append((a.arg, "POSITIONAL_ONLY", a.annotation, has_def, _ast_unparse(d)))

    # args.args は POSITIONAL_OR_KEYWORD
    for j, a in enumerate(args.args):
        idx = len(args.posonlyargs) + j
        has_def = idx >= def_start
        d = defaults[idx - def_start] if has_def else None
        rows.append((a.arg, "POSITIONAL_OR_KEYWORD", a.annotation, has_def, _ast_unparse(d)))

    # *args
    if args.vararg is not None:
        rows.append((args.vararg.arg, "VAR_POSITIONAL", args.vararg.annotation, False, ""))

    # kwonlyargs / kw_defaults は同じ長さ
    for a, d in zip(args.kwonlyargs, args.kw_defaults):
        has_def = d is not None
        rows.append((a.arg, "KEYWORD_ONLY", a.annotation, has_def, _ast_unparse(d)))

    # **kwargs
    if args.kwarg is not None:
        rows.append((args.kwarg.arg, "VAR_KEYWORD", args.kwarg.annotation, False, ""))

    return rows


def _params_from_funcdef(node: ast.AST) -> List[Dict[str, Any]]:
    if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
        return []
    out: List[Dict[str, Any]] = []
    for name, kind, ann, has_def, drepr in _kind_strings_for_args(node.args):
        out.append(
            {
                "name": name,
                "kind": kind,
                "annotation": _ann_to_str(ann),
                "has_default": bool(has_def),
                "default_repr": (drepr or "").strip(),
            }
        )
    return out


def _return_type_from_funcdef(node: ast.AST) -> str:
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
        return _ann_to_str(getattr(node, "returns", None))
    return ""


def _is_property_like(node: ast.FunctionDef) -> bool:
    for d in getattr(node, "decorator_list", []) or []:
        # @property / @cached_property / @something.property 的なものを雑に拾う
        if isinstance(d, ast.Name) and d.id in {"property", "cached_property"}:
            return True
        if isinstance(d, ast.Attribute) and d.attr in {"setter", "deleter"}:
            return True
    return False


def _resolve_from_import(current_mod: str, module: Optional[str], level: int) -> str:
    """from .x import y の相対importをざっくり絶対名へ寄せる。"""
    if not level:
        return module or ""
    cur_parts = current_mod.split(".")
    base = cur_parts[: max(0, len(cur_parts) - level)]
    if module:
        return ".".join(base + module.split("."))
    return ".".join(base)


def _candidate_import_names(lib_name: str) -> List[str]:
    out: List[str] = []
    raw = (lib_name or "").strip()
    if raw:
        out.append(raw)
        out.append(raw.replace("-", "_"))
        out.append(raw.split(".")[0])

    # distribution -> top_level.txt があることが多い
    try:
        dist = importlib.metadata.distribution(raw)
        tl = dist.read_text("top_level.txt")
        if tl:
            for line in tl.splitlines():
                s = line.strip()
                if s and re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", s):
                    out.append(s)
    except Exception:
        pass

    # ユニーク化（順序維持）
    uniq: List[str] = []
    seen = set()
    for n in out:
        n = (n or "").strip()
        if not n or n in seen:
            continue
        seen.add(n)
        uniq.append(n)
    return uniq


@dataclass
class _Node:
    id: str
    parent: str
    type: str
    name: str
    path: str
    module: str
    docstring: str = ""
    return_type: str = ""
    params: Optional[List[Dict[str, Any]]] = None


class LibraryAnalyzerV6:
    """V6用の軽量アナライザ。

    目的（作業仮説）:
      - 旧 v4/v5 の Analyzer 実装が同梱されていない環境でも動くこと
      - なるべく「import実行」を避け、AST解析で安全にノード/エッジを作ること

    出力:
      summary: dict
      nodes  : List[dict]
      edges  : List[dict]
      errors : List[dict]
    """

    def __init__(self, lib_name: str, *, max_files: int = 5000, max_external_per_module: int = 40):
        self.lib_name = (lib_name or "").strip()
        self.max_files = int(max_files)
        self.max_external_per_module = int(max_external_per_module)

        self._next_id = 1
        self._nodes: List[_Node] = []
        self._edges: List[Dict[str, Any]] = []
        self._errors: List[Dict[str, Any]] = []

        # lookup maps
        self._path_to_id: Dict[str, str] = {}   # dotted path -> id
        self._module_to_id: Dict[str, str] = {} # module path -> id

    def _new_id(self) -> str:
        nid = str(self._next_id)
        self._next_id += 1
        return nid

    def _add_node(self, node: _Node) -> None:
        self._nodes.append(node)
        if node.path:
            self._path_to_id.setdefault(node.path, node.id)
        if node.type == "module" and node.path:
            self._module_to_id.setdefault(node.path, node.id)

    def _add_edge(self, src: str, dst: str, rel: str) -> None:
        if not src or not dst:
            return
        self._edges.append({"Source": str(src), "Target": str(dst), "Type": str(rel)})

    def _module_name_from_file(self, root_mod: str, root_dir: Path, file_path: Path) -> str:
        rel = file_path.relative_to(root_dir).as_posix()
        if rel.endswith("__init__.py"):
            rel = rel[: -len("__init__.py")]
        if rel.endswith(".py"):
            rel = rel[: -3]
        rel = rel.strip("/")
        if not rel:
            return root_mod
        return root_mod + "." + rel.replace("/", ".")

    def _choose_root(self) -> Tuple[List[str], List[Tuple[str, Path]]]:
        """候補 import 名と、それに対応する (root_mod, root_dir) を返す。"""
        cands = _candidate_import_names(self.lib_name)
        roots: List[Tuple[str, Path]] = []
        for name in cands:
            try:
                spec = importlib.util.find_spec(name)
            except Exception:
                spec = None
            if spec is None:
                continue

            # package
            if spec.submodule_search_locations:
                for p in spec.submodule_search_locations:
                    if p and os.path.isdir(p):
                        roots.append((name, Path(p)))
                continue

            # single-file module
            origin = getattr(spec, "origin", None)
            if origin and os.path.isfile(origin):
                roots.append((name, Path(origin).parent))
        # 重複除去（root_dirで）
        uniq: List[Tuple[str, Path]] = []
        seen = set()
        for m, d in roots:
            key = (m, str(d.resolve()))
            if key in seen:
                continue
            seen.add(key)
            uniq.append((m, d))
        return cands, uniq

    def analyze(self) -> Tuple[Dict[str, Any], List[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, Any]]]:
        cand_names, roots = self._choose_root()
        if not roots:
            self._errors.append(
                {
                    "stage": "resolve_root",
                    "library": self.lib_name,
                    "candidates": cand_names,
                    "error": "importlib.util.find_spec() did not find a package/module",
                }
            )
            summary = {
                "library": self.lib_name,
                "root_modules": [],
                "files_parsed": 0,
                "nodes": 0,
                "edges": 0,
                "errors": len(self._errors),
            }
            return summary, [], [], self._errors

        total_files = 0
        for root_mod, root_dir in roots:
            py_files = _iter_py_files(root_dir, max_files=max(1, self.max_files - total_files))
            total_files += len(py_files)

            for fp in py_files:
                if total_files > self.max_files:
                    break
                self._analyze_file(root_mod, root_dir, fp)

        # 内部import edge の解決（module名 -> id）
        self._finalize_import_edges()

        summary = {
            "library": self.lib_name,
            "root_modules": [m for m, _ in roots],
            "files_parsed": int(total_files),
            "modules": int(sum(1 for n in self._nodes if n.type == "module")),
            "classes": int(sum(1 for n in self._nodes if n.type == "class")),
            "functions": int(sum(1 for n in self._nodes if n.type == "function")),
            "methods": int(sum(1 for n in self._nodes if n.type in {"method", "property"})),
            "external": int(sum(1 for n in self._nodes if n.type == "external")),
            "nodes": int(len(self._nodes)),
            "edges": int(len(self._edges)),
            "errors": int(len(self._errors)),
        }

        nodes_dicts = []
        for n in self._nodes:
            d: Dict[str, Any] = {
                "ID": n.id,
                "Parent": n.parent,
                "Type": n.type,
                "Name": n.name,
                "Path": n.path,
                "Module": n.module,
            }
            if n.docstring:
                d["Docstring"] = n.docstring
            if n.return_type:
                d["ReturnType"] = n.return_type
            if n.params is not None:
                d["Params"] = n.params
            nodes_dicts.append(d)

        return summary, nodes_dicts, self._edges, self._errors

    # --- internal: file analysis -------------------------------------------------

    def _analyze_file(self, root_mod: str, root_dir: Path, fp: Path) -> None:
        try:
            mod_name = self._module_name_from_file(root_mod, root_dir, fp)
        except Exception as e:
            self._errors.append({"stage": "module_name", "file": str(fp), "error": repr(e)})
            return

        src = _safe_read_text(fp)
        if not src.strip():
            return

        try:
            tree = ast.parse(src)
        except Exception as e:
            self._errors.append({"stage": "ast_parse", "module": mod_name, "file": str(fp), "error": repr(e)})
            return

        # module node
        mod_id = self._module_to_id.get(mod_name)
        if not mod_id:
            mod_id = self._new_id()
            self._add_node(
                _Node(
                    id=mod_id,
                    parent="",
                    type="module",
                    name=mod_name.split(".")[-1],
                    path=mod_name,
                    module=mod_name,  # module行もModuleに入れておくと絞り込みが安定
                    docstring=(ast.get_docstring(tree) or ""),
                )
            )

        # 1) contains: class / function
        for node in tree.body:
            if isinstance(node, ast.ClassDef):
                self._add_class(mod_id, mod_name, node)
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                self._add_function(mod_id, mod_name, node)

        # 2) imports -> provisional store in edges as module string, resolve later
        self._collect_imports(mod_id, mod_name, tree)

    def _add_class(self, mod_id: str, mod_name: str, node: ast.ClassDef) -> None:
        cls_path = f"{mod_name}.{node.name}"
        cls_id = self._path_to_id.get(cls_path)
        if not cls_id:
            cls_id = self._new_id()
            self._add_node(
                _Node(
                    id=cls_id,
                    parent=mod_id,
                    type="class",
                    name=node.name,
                    path=cls_path,
                    module=mod_name,
                    docstring=(ast.get_docstring(node) or ""),
                    params=None,  # class自体はParamsなし（Deep inspectで __init__ を拾う想定）
                )
            )
            self._add_edge(mod_id, cls_id, "contains")

        # methods
        for b in node.body:
            if isinstance(b, (ast.FunctionDef, ast.AsyncFunctionDef)):
                self._add_method(cls_id, mod_name, node.name, b)

    def _add_function(self, mod_id: str, mod_name: str, node: ast.AST) -> None:
        fname = getattr(node, "name", "")
        if not fname:
            return
        fpath = f"{mod_name}.{fname}"
        fid = self._path_to_id.get(fpath)
        if fid:
            return
        fid = self._new_id()
        self._add_node(
            _Node(
                id=fid,
                parent=mod_id,
                type="function",
                name=fname,
                path=fpath,
                module=mod_name,
                docstring=(ast.get_docstring(node) or ""),
                return_type=_return_type_from_funcdef(node),
                params=_params_from_funcdef(node),
            )
        )
        self._add_edge(mod_id, fid, "contains")

    def _add_method(self, cls_id: str, mod_name: str, cls_name: str, node: ast.AST) -> None:
        mname = getattr(node, "name", "")
        if not mname:
            return
        mpath = f"{mod_name}.{cls_name}.{mname}"
        mid = self._path_to_id.get(mpath)
        if mid:
            return
        mid = self._new_id()
        typ = "property" if isinstance(node, ast.FunctionDef) and _is_property_like(node) else "method"
        self._add_node(
            _Node(
                id=mid,
                parent=cls_id,
                type=typ,
                name=mname,
                path=mpath,
                module=mod_name,
                docstring=(ast.get_docstring(node) or ""),
                return_type=_return_type_from_funcdef(node),
                params=_params_from_funcdef(node),
            )
        )
        self._add_edge(cls_id, mid, "contains")

    # --- imports ----------------------------------------------------------------

    def _collect_imports(self, mod_id: str, mod_name: str, tree: ast.AST) -> None:
        """import文を走査し、エッジ解決用に一旦 edges に 'TargetModule' を持たせる。"""
        external_added = 0
        seen_ext: set[str] = set()

        for node in getattr(tree, "body", []) or []:
            if isinstance(node, ast.Import):
                for alias in node.names:
                    tgt = (alias.name or "").strip()
                    if not tgt:
                        continue
                    self._queue_import(mod_id, mod_name, tgt, seen_ext, external_added)
                    if tgt.split(".")[0] not in self._root_prefixes():
                        external_added = min(self.max_external_per_module, external_added + 1)
            elif isinstance(node, ast.ImportFrom):
                tgt_mod = _resolve_from_import(mod_name, node.module, int(getattr(node, "level", 0) or 0))
                if not tgt_mod:
                    continue
                self._queue_import(mod_id, mod_name, tgt_mod, seen_ext, external_added)
                if tgt_mod.split(".")[0] not in self._root_prefixes():
                    external_added = min(self.max_external_per_module, external_added + 1)

    def _queue_import(self, mod_id: str, mod_name: str, tgt_mod: str, seen_ext: set[str], external_added: int) -> None:
        top = (tgt_mod or "").split(".")[0]
        internal = top in self._root_prefixes()

        if internal:
            # 後で module_to_id を引けるように "TargetModule" を保持
            self._edges.append({"Source": str(mod_id), "TargetModule": str(tgt_mod), "Type": "imports"})
            return

        # external: ノード化（上限付き）
        if external_added >= self.max_external_per_module:
            return
        key = tgt_mod
        if key in seen_ext:
            return
        seen_ext.add(key)

        ext_id = self._new_id()
        self._add_node(
            _Node(
                id=ext_id,
                parent=mod_id,
                type="external",
                name=tgt_mod.split(".")[-1],
                path=tgt_mod,   # externalのPathは "外部モジュール名"
                module=mod_name,
                docstring="",
                params=None,
            )
        )
        self._add_edge(mod_id, ext_id, "contains")
        # 外部importとしても残す（可視化用）
        self._add_edge(mod_id, ext_id, "external_import")

    def _root_prefixes(self) -> set[str]:
        # rootsは module_to_id からトップを推測
        tops = {m.split(".")[0] for m in self._module_to_id.keys() if m}
        # まだmoduleが少ない初期は lib_name候補も含める
        for c in _candidate_import_names(self.lib_name):
            tops.add(c.split(".")[0])
        return {t for t in tops if t}

    def _finalize_import_edges(self) -> None:
        """TargetModule を持つ provisional edge を module_id に解決する。"""
        resolved: List[Dict[str, Any]] = []
        for e in self._edges:
            if "TargetModule" not in e:
                resolved.append(e)
                continue
            src = str(e.get("Source", ""))
            tgt_mod = str(e.get("TargetModule", ""))
            if not src or not tgt_mod:
                continue

            # できるだけ近い解（完全一致→prefix短縮）
            tgt_id = self._module_to_id.get(tgt_mod)
            if tgt_id is None:
                parts = tgt_mod.split(".")
                for cut in range(len(parts) - 1, 0, -1):
                    cand = ".".join(parts[:cut])
                    if cand in self._module_to_id:
                        tgt_id = self._module_to_id[cand]
                        break

            if tgt_id is None:
                # 解決できない場合は外部扱いに落とす（ノードを増やしすぎないため edge は捨てる）
                continue

            resolved.append({"Source": src, "Target": str(tgt_id), "Type": "imports"})

        self._edges = resolved
