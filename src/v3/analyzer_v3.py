# ファイルパス: C:\lib_ana\src\analyzer_v3.py
# （このノートブック環境では /mnt/data/analyzer_v3.py に置いています）
from __future__ import annotations

import ast
import inspect
import importlib
import importlib.util
import pkgutil
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

import pandas as pd

from models import AnalysisConfig, AnalysisResult, Node


def _safe_doc(obj: Any, limit: int = 120) -> str:
    doc = inspect.getdoc(obj) or ""
    doc = doc.replace("\n", " ").strip()
    return doc[:limit]


def _safe_sig(obj: Any) -> str:
    try:
        return str(inspect.signature(obj))
    except Exception:
        return ""


def _safe_source_loc(obj: Any) -> int:
    try:
        src = inspect.getsource(obj)
        return len(src.splitlines())
    except Exception:
        return 0


def _is_public(name: str, include_private: bool) -> bool:
    return include_private or (not name.startswith("_"))


def _split_module_parent(mod_name: str) -> Optional[str]:
    if "." not in mod_name:
        return None
    return mod_name.rsplit(".", 1)[0]


class LibraryAnalyzerV3:
    """
    目的:
      - 「定義元(origin)」と「公開面(API surface)」を分離し、分類ノイズを劇的に減らす
      - module → (class/function) → (method/property) の階層を崩さずUIに渡す
      - import副作用を抑えたい場合は AST モードに寄せる

    出力:
      AnalysisResult(nodes=Node[])  → DataFrame(records)
    """

    def __init__(self, lib_name: str, config: Optional[AnalysisConfig] = None):
        self.lib_name = lib_name
        self.cfg = config or AnalysisConfig()
        self.errors: List[str] = []

        self.root_module = None
        try:
            self.root_module = importlib.import_module(lib_name)
        except Exception as e:
            self.errors.append(f"[import root] {lib_name}: {e}")

    # -------- module discovery --------

    def discover_modules(self) -> List[str]:
        """
        pkgutil.walk_packages で lib 配下のモジュール名を列挙。
        """
        if not self.root_module:
            return []
        modules = [self.lib_name]

        # パッケージでない（__path__ がない）場合もあり得る
        if not hasattr(self.root_module, "__path__"):
            return modules

        try:
            for m in pkgutil.walk_packages(self.root_module.__path__, prefix=f"{self.lib_name}."):
                if len(modules) >= self.cfg.max_modules:
                    self.errors.append("[discover] max_modules reached; truncated")
                    break
                modules.append(m.name)
        except Exception as e:
            self.errors.append(f"[discover] walk_packages failed: {e}")

        # 深さ制限
        limited: List[str] = []
        for mn in modules:
            depth = mn.count(".")
            if depth <= self.cfg.max_depth:
                limited.append(mn)
        return sorted(set(limited))

    # -------- AST helpers --------

    def _spec_origin(self, mod_name: str) -> Optional[str]:
        try:
            spec = importlib.util.find_spec(mod_name)
            if spec and spec.origin and spec.origin != "built-in":
                return spec.origin
        except Exception:
            return None
        return None

    def _ast_defs(self, py_file: str) -> Dict[str, Dict[str, Any]]:
        """
        .py を AST で解析してトップレベル定義を抽出（クラス/関数）。
        """
        out: Dict[str, Dict[str, Any]] = {}
        try:
            src = Path(py_file).read_text(encoding="utf-8")
        except Exception:
            # encoding不明な場合など
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
                out[node.name] = {
                    "kind": "class",
                    "lineno": getattr(node, "lineno", None),
                    "end_lineno": getattr(node, "end_lineno", None),
                }
            elif isinstance(node, ast.FunctionDef):
                out[node.name] = {
                    "kind": "function",
                    "lineno": getattr(node, "lineno", None),
                    "end_lineno": getattr(node, "end_lineno", None),
                }
            elif isinstance(node, ast.AsyncFunctionDef):
                out[node.name] = {
                    "kind": "function",
                    "lineno": getattr(node, "lineno", None),
                    "end_lineno": getattr(node, "end_lineno", None),
                }
        return out

    # -------- dynamic introspection helpers --------

    def _safe_import(self, mod_name: str):
        try:
            return importlib.import_module(mod_name)
        except Exception as e:
            self.errors.append(f"[import] {mod_name}: {e}")
            return None

    def _iter_class_members_defined(self, cls: type) -> Iterable[Tuple[str, Any, str]]:
        """
        継承ノイズを除く:
          - cls.__dict__ のみを見る（=そのクラスに「定義されている」メンバー）
          - staticmethod/classmethod/property を解決して、実体を返す
        """
        for name, raw in cls.__dict__.items():
            if not _is_public(name, self.cfg.include_private):
                continue

            # property
            if isinstance(raw, property):
                fget = raw.fget
                if fget:
                    yield name, fget, "property"
                continue

            # staticmethod/classmethod
            if isinstance(raw, staticmethod):
                yield name, raw.__func__, "method"
                continue
            if isinstance(raw, classmethod):
                yield name, raw.__func__, "method"
                continue

            # plain function (instance method)
            if inspect.isfunction(raw):
                yield name, raw, "method"
                continue

            # C拡張っぽい/descriptor
            if inspect.isbuiltin(raw) or inspect.ismethoddescriptor(raw):
                yield name, raw, "method"
                continue

    def _iter_class_members_all(self, cls: type) -> Iterable[Tuple[str, Any, str]]:
        """
        すべて（継承込み）。ノイズは増えるが、必要な場合もある。
        """
        for name, obj in inspect.getmembers(cls):
            if not _is_public(name, self.cfg.include_private):
                continue
            if inspect.isfunction(obj) or inspect.ismethod(obj) or inspect.isbuiltin(obj):
                yield name, obj, "method"
            elif isinstance(obj, property):
                if obj.fget:
                    yield name, obj.fget, "property"

    # -------- core analysis --------

    def analyze(self) -> Tuple[Dict[str, Any], pd.DataFrame, AnalysisResult]:
        """
        return: (summary, df, result)
        """
        nodes: List[Node] = []
        mod_names = self.discover_modules()

        # 1) モジュールノードを先に作る（階層が安定する）
        for mn in mod_names:
            parent = _split_module_parent(mn) or self.lib_name
            if mn == self.lib_name:
                parent = None
            nodes.append(
                Node(
                    id=mn,
                    kind="module",
                    name=mn.split(".")[-1],
                    fqn=mn,
                    parent_id=parent,
                    origin_module=mn,
                    origin_file=self._spec_origin(mn),
                    flags={"module": mn, "is_external": False},
                )
            )

        # 2) 各モジュールの中身
        for mn in mod_names:
            origin = self._spec_origin(mn)
            ast_defs: Dict[str, Dict[str, Any]] = {}
            if self.cfg.ast_parse and origin and origin.endswith(".py") and Path(origin).exists():
                ast_defs = self._ast_defs(origin)

            mod_obj = self._safe_import(mn) if self.cfg.dynamic_import else None
            if not mod_obj:
                # importできない場合でも、ASTで得た定義だけを薄く載せる
                for sym, meta in ast_defs.items():
                    if not _is_public(sym, self.cfg.include_private):
                        continue
                    fqn = f"{mn}.{sym}"
                    nodes.append(
                        Node(
                            id=fqn,
                            kind=meta["kind"],
                            name=sym,
                            fqn=fqn,
                            parent_id=mn,
                            origin_module=mn,
                            origin_file=origin,
                            lineno=meta.get("lineno"),
                            end_lineno=meta.get("end_lineno"),
                            doc_summary="(AST only) dynamic import disabled or failed",
                            flags={"module": mn, "analysis_mode": "ast"},
                        )
                    )
                continue

            # moduleメンバーを列挙（ただし「定義元」を見て内部/外部を分ける）
            try:
                members = inspect.getmembers(mod_obj)
            except Exception as e:
                self.errors.append(f"[members] {mn}: {e}")
                continue

            for name, obj in members:
                if not _is_public(name, self.cfg.include_private):
                    continue

                # モジュール内部のsubmoduleは module discovery 側で扱う（重複/循環が増えるため）
                if inspect.ismodule(obj):
                    continue

                # 定義元（origin_module）を推定
                origin_module = getattr(obj, "__module__", None)
                is_external = not (origin_module or "").startswith(self.lib_name)

                # 外部を基本は除外（ただし再エクスポートとして見たい場合は残す）
                if is_external and (not self.cfg.include_external_reexports):
                    continue

                # 1) class
                if inspect.isclass(obj):
                    # クラス自体が外部由来なら external 扱い（include_external_reexports=True のときだけここに来る）
                    kind = "class" if not is_external else "external"
                    fqn = f"{mn}.{name}"
                    nodes.append(
                        Node(
                            id=fqn,
                            kind=kind,
                            name=name,
                            fqn=fqn,
                            parent_id=mn,
                            origin_module=origin_module,
                            origin_file=(inspect.getsourcefile(obj) or origin),
                            lineno=ast_defs.get(name, {}).get("lineno"),
                            end_lineno=ast_defs.get(name, {}).get("end_lineno"),
                            loc=_safe_source_loc(obj),
                            doc_summary=_safe_doc(obj),
                            signature="",
                            flags={
                                "module": mn,
                                "is_external": is_external,
                                "bases": [b.__name__ for b in getattr(obj, "__bases__", ())],
                            },
                        )
                    )

                    # メンバー（method/property）
                    iter_members = (
                        self._iter_class_members_all(obj)
                        if self.cfg.include_inherited_members
                        else self._iter_class_members_defined(obj)
                    )

                    for m_name, m_obj, m_kind in iter_members:
                        m_origin = getattr(m_obj, "__module__", None)
                        m_is_external = not (m_origin or "").startswith(self.lib_name)

                        # 継承込みの場合でも「外部由来メソッド」を落とすとノイズが減る
                        if m_is_external and (not self.cfg.include_external_reexports):
                            continue

                        mfqn = f"{fqn}.{m_name}"
                        nodes.append(
                            Node(
                                id=mfqn,
                                kind=m_kind,
                                name=m_name,
                                fqn=mfqn,
                                parent_id=fqn,
                                origin_module=m_origin,
                                origin_file=(inspect.getsourcefile(m_obj) or ""),
                                lineno=None,
                                end_lineno=None,
                                loc=_safe_source_loc(m_obj),
                                doc_summary=_safe_doc(m_obj, limit=120),
                                signature=_safe_sig(m_obj),
                                flags={
                                    "module": mn,
                                    "is_external": m_is_external,
                                    "member_of": fqn,
                                },
                            )
                        )
                    continue

                # 2) function
                if inspect.isfunction(obj) or inspect.isbuiltin(obj):
                    # 由来が外部なら external 扱い
                    kind = "function" if not is_external else "external"
                    fqn = f"{mn}.{name}"
                    nodes.append(
                        Node(
                            id=fqn,
                            kind=kind,
                            name=name,
                            fqn=fqn,
                            parent_id=mn,
                            origin_module=origin_module,
                            origin_file=(inspect.getsourcefile(obj) or origin),
                            lineno=ast_defs.get(name, {}).get("lineno"),
                            end_lineno=ast_defs.get(name, {}).get("end_lineno"),
                            loc=_safe_source_loc(obj),
                            doc_summary=_safe_doc(obj),
                            signature=_safe_sig(obj),
                            flags={"module": mn, "is_external": is_external},
                        )
                    )
                    continue

                # 3) その他（定数・型エイリアスなど）
                # UIを汚すなら落とす。必要になったら kind='attribute' を追加する。
                # ここではスキップ。
                continue

        result = AnalysisResult(self.lib_name, nodes, self.errors)

        df = pd.DataFrame(result.to_records())

        # summary（API surfaceのみを既定で数える）
        df_core = df[df["Flags"].apply(lambda x: not (x or {}).get("is_external", False))]
        summary = {
            "Name": self.lib_name,
            "Modules": int((df_core["Type"] == "module").sum()),
            "Classes": int((df_core["Type"] == "class").sum()),
            "Functions": int((df_core["Type"] == "function").sum()),
            "Methods/Properties": int(df_core["Type"].isin(["method", "property"]).sum()),
            "ExternalReexports": int((df["Type"] == "external").sum()),
            "Errors": len(self.errors),
        }

        return summary, df, result
