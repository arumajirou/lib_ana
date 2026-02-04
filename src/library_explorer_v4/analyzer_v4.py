# ファイルパス: C:\lib_ana\src\analyzer_v4.py
# （この実行環境では /mnt/data/analyzer_v4.py に生成しています）
from __future__ import annotations

import ast
import inspect
import importlib
import importlib.util
import pkgutil
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple

import pandas as pd

from models_v4 import AnalysisConfig, AnalysisResult, Node, Edge
from taxonomy_v4 import classify_events


def _safe_doc(obj: Any, limit: int = 140) -> str:
    doc = inspect.getdoc(obj) or ""
    doc = doc.replace("\n", " ").strip()
    return doc[:limit]


def _safe_sig(obj: Any) -> str:
    try:
        return str(inspect.signature(obj))
    except Exception:
        return ""


def _safe_loc(obj: Any) -> int:
    try:
        src = inspect.getsource(obj)
        return len(src.splitlines())
    except Exception:
        return 0


def _ann_to_str(x: Any) -> str:
    if x is None:
        return ""
    try:
        if x is inspect._empty:
            return ""
    except Exception:
        pass
    try:
        return getattr(x, "__name__", str(x))
    except Exception:
        return str(x)


def _split_parent(name: str) -> Optional[str]:
    if "." not in name:
        return None
    return name.rsplit(".", 1)[0]


def _is_public(name: str, include_private: bool) -> bool:
    return include_private or (not name.startswith("_"))


def _looks_like_test_module(mod_name: str) -> bool:
    lower = mod_name.lower()
    return (".tests" in lower) or lower.endswith(".test") or ".testing" in lower


class LibraryAnalyzerV4:
    def __init__(self, lib_name: str, config: Optional[AnalysisConfig] = None):
        self.lib_name = lib_name
        self.cfg = config or AnalysisConfig()
        self.errors: List[str] = []
        self.root_module = None
        try:
            self.root_module = importlib.import_module(lib_name)
        except Exception as e:
            self.errors.append(f"[import root] {lib_name}: {e}")

        self.module_all: Dict[str, Set[str]] = {}

    def discover_modules(self) -> List[str]:
        if not self.root_module:
            return []
        modules = [self.lib_name]
        if hasattr(self.root_module, "__path__"):
            try:
                for m in pkgutil.walk_packages(self.root_module.__path__, prefix=f"{self.lib_name}."):
                    if len(modules) >= self.cfg.max_modules:
                        self.errors.append("[discover] max_modules reached; truncated")
                        break
                    mn = m.name
                    if self.cfg.exclude_test_modules and _looks_like_test_module(mn):
                        continue
                    if mn.count(".") <= self.cfg.max_depth:
                        modules.append(mn)
            except Exception as e:
                self.errors.append(f"[discover] walk_packages failed: {e}")
        return sorted(set(modules))

    def _spec_origin(self, mod_name: str) -> Optional[str]:
        try:
            spec = importlib.util.find_spec(mod_name)
            if spec and spec.origin and spec.origin != "built-in":
                return spec.origin
        except Exception:
            return None
        return None

    def _ast_defs(self, py_file: str) -> Dict[str, Dict[str, Any]]:
        out: Dict[str, Dict[str, Any]] = {}
        try:
            src = Path(py_file).read_text(encoding="utf-8")
        except Exception:
            try:
                src = Path(py_file).read_text(encoding="latin-1")
            except Exception as e:
                self.errors.append(f"[ast read] {py_file}: {e}")
                return out

        try:
            tree = ast.parse(src)
        except Exception as e:
            self.errors.append(f"[ast parse] {py_file}: {e}")
            return out

        for node in tree.body:
            if isinstance(node, ast.ClassDef):
                out[node.name] = {"kind": "class", "lineno": getattr(node, "lineno", None), "end_lineno": getattr(node, "end_lineno", None)}
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                out[node.name] = {"kind": "function", "lineno": getattr(node, "lineno", None), "end_lineno": getattr(node, "end_lineno", None)}
        return out

    def _collect_module_all(self, mod_name: str, mod_obj: Any):
        try:
            a = getattr(mod_obj, "__all__", None)
            if isinstance(a, (list, tuple, set)):
                self.module_all[mod_name] = set(str(x) for x in a)
        except Exception:
            pass

    def _is_in_api_surface(self, module_name: str, symbol_name: str) -> bool:
        if self.cfg.api_surface == "top_level":
            root = self.module_all.get(self.lib_name, None)
            if root is not None:
                return symbol_name in root
            if not self.root_module:
                return False
            return hasattr(self.root_module, symbol_name) and _is_public(symbol_name, self.cfg.include_private)

        a = self.module_all.get(module_name, None)
        if a is not None:
            return symbol_name in a
        return _is_public(symbol_name, self.cfg.include_private)

    def _iter_class_members_defined(self, cls: type) -> Iterable[Tuple[str, Any, str]]:
        for name, raw in cls.__dict__.items():
            if not _is_public(name, self.cfg.include_private):
                continue
            if isinstance(raw, property):
                if raw.fget:
                    yield name, raw.fget, "property"
                continue
            if isinstance(raw, staticmethod):
                yield name, raw.__func__, "method"
                continue
            if isinstance(raw, classmethod):
                yield name, raw.__func__, "method"
                continue
            if inspect.isfunction(raw) or inspect.isbuiltin(raw) or inspect.ismethoddescriptor(raw):
                yield name, raw, "method"
                continue

    def _iter_class_members_all(self, cls: type) -> Iterable[Tuple[str, Any, str]]:
        for name, obj in inspect.getmembers(cls):
            if not _is_public(name, self.cfg.include_private):
                continue
            if inspect.isfunction(obj) or inspect.ismethod(obj) or inspect.isbuiltin(obj) or inspect.ismethoddescriptor(obj):
                yield name, obj, "method"
            elif isinstance(obj, property) and obj.fget:
                yield name, obj.fget, "property"

    def _extract_signature_parts(self, obj: Any) -> Tuple[List[str], List[str], str]:
        try:
            sig = inspect.signature(obj)
        except Exception:
            return [], [], ""
        p_names: List[str] = []
        p_types: List[str] = []
        for p in sig.parameters.values():
            p_names.append(p.name)
            p_types.append(_ann_to_str(p.annotation))
        rtype = _ann_to_str(sig.return_annotation)
        return p_names, p_types, rtype

    def analyze(self) -> Tuple[Dict[str, Any], pd.DataFrame, pd.DataFrame, AnalysisResult]:
        nodes: List[Node] = []
        edges: List[Edge] = []
        mod_names = self.discover_modules()

        # import modules to collect __all__
        mod_objs: Dict[str, Any] = {}
        if self.cfg.dynamic_import:
            for mn in mod_names:
                try:
                    mo = importlib.import_module(mn)
                    mod_objs[mn] = mo
                    self._collect_module_all(mn, mo)
                except Exception as e:
                    self.errors.append(f"[import] {mn}: {e}")

        if self.root_module:
            self._collect_module_all(self.lib_name, self.root_module)

        # module nodes
        for mn in mod_names:
            parent = _split_parent(mn)
            if mn == self.lib_name:
                parent = None
            nodes.append(
                Node(
                    id=mn, kind="module", name=mn.split(".")[-1], fqn=mn, parent_id=parent,
                    origin_module=mn, origin_file=self._spec_origin(mn),
                    flags={"module": mn, "is_external": False, "api_surface": self.cfg.api_surface},
                )
            )
            if parent:
                edges.append(Edge(src=parent, dst=mn, rel="contains", weight=1.0))

        # contents
        for mn in mod_names:
            origin = self._spec_origin(mn)
            ast_defs: Dict[str, Dict[str, Any]] = {}
            if self.cfg.ast_parse and origin and origin.endswith(".py") and Path(origin).exists():
                ast_defs = self._ast_defs(origin)

            mod_obj = mod_objs.get(mn) if self.cfg.dynamic_import else None

            if not mod_obj:
                for sym, meta in ast_defs.items():
                    if not self._is_in_api_surface(mn, sym):
                        continue
                    fqn = f"{mn}.{sym}"
                    nodes.append(
                        Node(
                            id=fqn, kind=meta["kind"], name=sym, fqn=fqn, parent_id=mn,
                            origin_module=mn, origin_file=origin,
                            lineno=meta.get("lineno"), end_lineno=meta.get("end_lineno"),
                            doc_summary="(AST only)",
                            events=classify_events(sym, ""),
                            flags={"module": mn, "analysis_mode": "ast", "is_external": False},
                        )
                    )
                    edges.append(Edge(src=mn, dst=fqn, rel="contains", weight=1.0))
                continue

            try:
                members = inspect.getmembers(mod_obj)
            except Exception as e:
                self.errors.append(f"[members] {mn}: {e}")
                continue

            for name, obj in members:
                if inspect.ismodule(obj):
                    continue
                if not self._is_in_api_surface(mn, name):
                    continue

                origin_module = getattr(obj, "__module__", None) or ""
                is_external = not origin_module.startswith(self.lib_name)

                if is_external and (not self.cfg.include_external_reexports):
                    continue

                if inspect.isclass(obj):
                    kind = "external" if is_external else "class"
                    fqn = f"{mn}.{name}"
                    nodes.append(
                        Node(
                            id=fqn, kind=kind, name=name, fqn=fqn, parent_id=mn,
                            origin_module=origin_module,
                            origin_file=(inspect.getsourcefile(obj) or origin),
                            lineno=ast_defs.get(name, {}).get("lineno"),
                            end_lineno=ast_defs.get(name, {}).get("end_lineno"),
                            loc=_safe_loc(obj),
                            doc_summary=_safe_doc(obj),
                            events=classify_events(name, _safe_doc(obj)),
                            flags={
                                "module": mn,
                                "is_external": is_external,
                                "bases": [getattr(b, "__name__", str(b)) for b in getattr(obj, "__bases__", ())],
                            },
                        )
                    )
                    edges.append(Edge(src=mn, dst=fqn, rel="contains", weight=1.0))

                    for b in getattr(obj, "__bases__", ()):
                        bmod = getattr(b, "__module__", "") or ""
                        bname = getattr(b, "__name__", str(b))
                        base_id = f"{bmod}.{bname}"
                        edges.append(Edge(src=fqn, dst=base_id, rel="inherits", weight=1.0))

                    iter_members = self._iter_class_members_all(obj) if self.cfg.include_inherited_members else self._iter_class_members_defined(obj)
                    for m_name, m_obj, m_kind in iter_members:
                        if not _is_public(m_name, self.cfg.include_private):
                            continue
                        m_origin = getattr(m_obj, "__module__", "") or ""
                        m_is_external = not m_origin.startswith(self.lib_name)
                        if m_is_external and (not self.cfg.include_external_reexports):
                            continue

                        mfqn = f"{fqn}.{m_name}"
                        p_names, p_types, r_type = self._extract_signature_parts(m_obj)
                        nodes.append(
                            Node(
                                id=mfqn, kind=m_kind, name=m_name, fqn=mfqn, parent_id=fqn,
                                origin_module=m_origin,
                                origin_file=(inspect.getsourcefile(m_obj) or ""),
                                loc=_safe_loc(m_obj),
                                doc_summary=_safe_doc(m_obj),
                                signature=_safe_sig(m_obj),
                                param_names=p_names, param_types=p_types, return_type=r_type,
                                events=classify_events(m_name, _safe_doc(m_obj)),
                                flags={"module": mn, "is_external": m_is_external, "member_of": fqn},
                            )
                        )
                        edges.append(Edge(src=fqn, dst=mfqn, rel="contains", weight=1.0))
                    continue

                if inspect.isfunction(obj) or inspect.isbuiltin(obj):
                    kind = "external" if is_external else "function"
                    fqn = f"{mn}.{name}"
                    p_names, p_types, r_type = self._extract_signature_parts(obj)
                    nodes.append(
                        Node(
                            id=fqn, kind=kind, name=name, fqn=fqn, parent_id=mn,
                            origin_module=origin_module,
                            origin_file=(inspect.getsourcefile(obj) or origin),
                            lineno=ast_defs.get(name, {}).get("lineno"),
                            end_lineno=ast_defs.get(name, {}).get("end_lineno"),
                            loc=_safe_loc(obj),
                            doc_summary=_safe_doc(obj),
                            signature=_safe_sig(obj),
                            param_names=p_names, param_types=p_types, return_type=r_type,
                            events=classify_events(name, _safe_doc(obj)),
                            flags={"module": mn, "is_external": is_external},
                        )
                    )
                    edges.append(Edge(src=mn, dst=fqn, rel="contains", weight=1.0))
                    continue

                continue

        if self.cfg.add_related_edges:
            edges.extend(self._build_related_edges(nodes))

        result = AnalysisResult(self.lib_name, nodes, edges, self.errors)
        df_nodes = pd.DataFrame(result.to_records())
        df_edges = pd.DataFrame(result.edges_records())

        core = df_nodes[df_nodes["Flags"].apply(lambda x: not (x or {}).get("is_external", False))] if not df_nodes.empty else df_nodes
        unique_params = set()
        unique_returns = set()
        if not core.empty:
            for lst in core["ParamNames"].tolist():
                if isinstance(lst, list):
                    unique_params.update(lst)
            for rt in core["ReturnType"].tolist():
                if isinstance(rt, str) and rt.strip():
                    unique_returns.add(rt.strip())

        summary = {
            "Name": self.lib_name,
            "Modules": int((core["Type"] == "module").sum()) if not core.empty else 0,
            "Classes": int((core["Type"] == "class").sum()) if not core.empty else 0,
            "Functions": int((core["Type"] == "function").sum()) if not core.empty else 0,
            "Methods/Props": int(core["Type"].isin(["method", "property"]).sum()) if not core.empty else 0,
            "External": int((df_nodes["Type"] == "external").sum()) if not df_nodes.empty else 0,
            "UniqueParamNames": len(unique_params),
            "UniqueReturnTypes": len(unique_returns),
            "Errors": len(self.errors),
            "ApiSurface": self.cfg.api_surface,
        }

        return summary, df_nodes, df_edges, result

    def _build_related_edges(self, nodes: List[Node]) -> List[Edge]:
        out: List[Edge] = []
        callables = [n for n in nodes if n.kind in ["function", "method", "property"] and not n.flags.get("is_external", False)]
        if len(callables) > 4000:
            self.errors.append("[related] too many callables; skipped related edges")
            return out

        param_index: Dict[str, List[str]] = {}
        event_index: Dict[str, List[str]] = {}
        node_params = {}

        for n in callables:
            ps = set([p for p in n.param_names if p])
            node_params[n.id] = ps
            for p in ps:
                param_index.setdefault(p, []).append(n.id)
            for ev in n.events:
                if ev:
                    event_index.setdefault(ev, []).append(n.id)

        for n in callables:
            base = node_params.get(n.id, set())
            if len(base) < self.cfg.related_min_shared_params:
                continue
            cand: Set[str] = set()
            for p in base:
                cand.update(param_index.get(p, []))
            cand.discard(n.id)

            scored: List[Tuple[str, int]] = []
            for cid in cand:
                inter = base.intersection(node_params.get(cid, set()))
                if len(inter) >= self.cfg.related_min_shared_params:
                    scored.append((cid, len(inter)))

            scored.sort(key=lambda x: x[1], reverse=True)
            for cid, score in scored[: self.cfg.max_related_edges_per_node]:
                out.append(Edge(src=n.id, dst=cid, rel="related_param", weight=float(score)))

        for ev, ids in event_index.items():
            if len(ids) < 2:
                continue
            ids = ids[:80]
            for a, b in zip(ids, ids[1:]):
                out.append(Edge(src=a, dst=b, rel="related_event", weight=1.0))

        return out
