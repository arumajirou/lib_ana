# ファイルパス: C:\lib_ana\src\models_v4.py
# （この実行環境では /mnt/data/models_v4.py に生成しています）
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass(frozen=True)
class AnalysisConfig:
    # --- 解析スコープ ---
    max_modules: int = 5000
    max_depth: int = 30

    # --- 公開API(ユーザーが使う面) ---
    # "top_level": import <lib> したときに見える名前だけ（最も厳しい）
    # "module_public": 各モジュールの __all__（あれば）/ public名（なければ）を採用
    api_surface: str = "module_public"   # "top_level" | "module_public"
    include_private: bool = False
    include_external_reexports: bool = False
    include_inherited_members: bool = False
    exclude_test_modules: bool = True

    # --- 実行戦略 ---
    dynamic_import: bool = True
    ast_parse: bool = True

    # --- 関連性(グラフ) ---
    add_related_edges: bool = True
    max_related_edges_per_node: int = 8
    related_min_shared_params: int = 2


@dataclass
class Node:
    id: str
    kind: str                 # module / class / function / method / property / external
    name: str
    fqn: str
    parent_id: Optional[str] = None

    origin_module: Optional[str] = None
    origin_file: Optional[str] = None
    lineno: Optional[int] = None
    end_lineno: Optional[int] = None

    signature: str = ""
    doc_summary: str = ""
    loc: int = 0

    # --- 構造化メタ ---
    param_names: List[str] = field(default_factory=list)
    param_types: List[str] = field(default_factory=list)
    return_type: str = ""

    events: List[str] = field(default_factory=list)     # イベント分類タグ
    flags: Dict[str, Any] = field(default_factory=dict)  # is_external, module, bases, etc.


@dataclass
class Edge:
    src: str
    dst: str
    rel: str                 # contains / inherits / related_param / related_event / reexports
    weight: float = 1.0


@dataclass
class AnalysisResult:
    lib_name: str
    nodes: List[Node]
    edges: List[Edge]
    errors: List[str] = field(default_factory=list)

    def to_records(self):
        return [
            {
                "ID": n.id,
                "Type": n.kind,
                "Name": n.name,
                "Path": n.fqn,
                "Parent": n.parent_id or "",
                "Module": (n.flags.get("module") or ""),
                "OriginModule": n.origin_module or "",
                "OriginFile": n.origin_file or "",
                "Line": n.lineno or "",
                "EndLine": n.end_lineno or "",
                "LOC": n.loc,
                "Signature": n.signature,
                "DocSummary": n.doc_summary,
                "ParamNames": n.param_names,
                "ParamTypes": n.param_types,
                "ReturnType": n.return_type,
                "Events": n.events,
                "Flags": n.flags,
            }
            for n in self.nodes
        ]

    def edges_records(self):
        return [
            {"Src": e.src, "Dst": e.dst, "Rel": e.rel, "Weight": e.weight}
            for e in self.edges
        ]
