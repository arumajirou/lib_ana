# C:\lib_ana\src\v6\core\analyzer_service_v6.py
from __future__ import annotations

import importlib
import importlib.metadata
from dataclasses import dataclass
from typing import Any, Dict, List, Tuple

import pandas as pd
import streamlit as st

from v6.core.classify_v6 import enrich_with_classification
from v6.core.param_map_v6 import build_param_map_tables


def list_installed_libraries(limit: int = 3000) -> List[str]:
    # pip list 相当：上位の名前だけ
    names = []
    for d in importlib.metadata.distributions():
        n = d.metadata.get("Name")
        if n:
            names.append(n)
    # 重複排除＋ソート
    names = sorted(set(names), key=lambda s: s.lower())
    return names[:limit] if limit else names


def _import_analyzer(lib_name: str):
    """
    既存資産を最大限流用：
      - 可能なら v5 analyzer -> analyzer_v4
      - ダメなら analyzer_v4 を直 import
    """
    # プロジェクト内の import パスに合わせて適宜調整してください
    candidates = [
        ("v5.analyzer_v5", "LibraryAnalyzerV5"),
        ("analyzer_v5", "LibraryAnalyzerV5"),
        ("analyzer_v4", "LibraryAnalyzerV4"),
    ]
    last_err = None
    for mod, cls in candidates:
        try:
            m = importlib.import_module(mod)
            return getattr(m, cls)
        except Exception as e:
            last_err = e
            continue
    raise ImportError(f"Analyzer import failed for {lib_name}: {repr(last_err)}")


def _split_tables(df_nodes: pd.DataFrame) -> Dict[str, pd.DataFrame]:
    if df_nodes is None or df_nodes.empty:
        return {
            k: pd.DataFrame()
            for k in ["Modules", "Classes", "Functions", "Methods", "External"]
        }

    def _pick(t: str) -> pd.DataFrame:
        if "Type" not in df_nodes.columns:
            return pd.DataFrame()
        return df_nodes[df_nodes["Type"] == t].copy()

    def _pick_in(types: List[str]) -> pd.DataFrame:
        if "Type" not in df_nodes.columns:
            return pd.DataFrame()
        return df_nodes[df_nodes["Type"].isin(types)].copy()

    return {
        "Modules": _pick("module"),
        "Classes": _pick("class"),
        "Functions": _pick("function"),
        "Methods": _pick_in(["method", "property"]),
        "External": _pick("external"),
    }


@st.cache_data(show_spinner=False)
def _cached_analyze(lib_name: str) -> Tuple[Dict[str, Any], pd.DataFrame, pd.DataFrame]:
    Analyzer = _import_analyzer(lib_name)
    analyzer = Analyzer(lib_name)  # cfgは必要なら追加
    summary, df_nodes, df_edges, _ = analyzer.analyze()
    return summary, df_nodes, df_edges


def analyze_library_with_progress(lib_name: str) -> Dict[str, Any]:
    """
    Streamlit上で進捗を見せながら解析する。
    """
    progress = st.progress(0, text="Preparing...")
    with st.status(f"Analyzing: {lib_name}", expanded=True) as status:
        status.write("Step 1/5: load & cache")
        progress.progress(10)

        status.write("Step 2/5: run analyzer (df_nodes/df_edges)")
        progress.progress(30)
        summary, df_nodes, df_edges = _cached_analyze(lib_name)

        status.write("Step 3/5: split tables (Modules/Classes/...)")
        progress.progress(60)
        tables = _split_tables(df_nodes)

        status.write("Step 4/5: classification (role/event/similar-name clusters)")
        progress.progress(75)
        df_nodes2 = enrich_with_classification(df_nodes)

        status.write("Step 5/5: build param mapping tables")
        progress.progress(90)
        param_tables = build_param_map_tables(df_nodes2)

        progress.progress(100)
        status.update(label="Done", state="complete", expanded=False)

    return {
        "library": lib_name,
        "summary": summary,
        "nodes": df_nodes2,
        "edges": df_edges,
        "tables": tables,
        "param_tables": param_tables,
    }
