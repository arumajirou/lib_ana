# ファイルパス: C:\lib_ana\src\v6\analysis_service.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple

import pandas as pd

# 既存 V4 解析器を利用（src 直下にある想定）
from analyzer_v4 import LibraryAnalyzerV4
from models_v4 import AnalysisConfig

@dataclass
class AnalysisResult:
    summary: Dict[str, Any]
    nodes: pd.DataFrame
    edges: pd.DataFrame
    errors: pd.DataFrame

def default_config() -> AnalysisConfig:
    return AnalysisConfig(
        api_surface="module_public",
        include_private=False,
        include_external_reexports=False,
        include_inherited_members=False,
        add_related_edges=True,
    )

def analyze_library(lib_name: str, cfg: Optional[AnalysisConfig] = None) -> AnalysisResult:
    analyzer = LibraryAnalyzerV4(lib_name, cfg or default_config())
    summary, df_nodes, df_edges, df_errors = analyzer.analyze()
    return AnalysisResult(summary=summary, nodes=df_nodes, edges=df_edges, errors=df_errors)

def split_tables(nodes: pd.DataFrame) -> Dict[str, pd.DataFrame]:
    if nodes is None or nodes.empty or "Type" not in nodes.columns:
        return {}
    out: Dict[str, pd.DataFrame] = {}
    out["Modules"] = nodes[nodes["Type"] == "module"].copy()
    out["Classes"] = nodes[nodes["Type"] == "class"].copy()
    out["Functions"] = nodes[nodes["Type"] == "function"].copy()
    out["Methods"] = nodes[nodes["Type"] == "method"].copy()
    out["Properties"] = nodes[nodes["Type"] == "property"].copy()
    out["External"] = nodes[nodes["Type"] == "external"].copy()
    return out
