# ファイルパス: C:\lib_ana\src\v6\core\analyzer_service_v6.py
from __future__ import annotations

import importlib
import importlib.metadata
import os
import sys
from typing import Any, Dict, List, Tuple, Optional

import pandas as pd
import streamlit as st

from v6.core.classify_v6 import enrich_with_classification
from v6.core.param_map_v6 import build_param_map_tables
from v6.core.inspect_params_v6 import inspect_params_from_path


def _bootstrap_legacy_sys_path() -> None:
    """v4/v5の旧実装がトップレベル import（例: models_v4）を前提にしているケースを吸収する。"""
    # このファイル: .../src/v6/core/analyzer_service_v6.py
    # src_root:    .../src
    src_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))

    legacy_dirs = [
        os.path.join(src_root, "library_explorer_v4"),  # models_v4 / taxonomy_v4 / package_catalog_v4 等
        os.path.join(src_root, "v5"),                   # v5系トップレベルimportの保険
        src_root,
    ]

    for p in legacy_dirs:
        if os.path.isdir(p) and p not in sys.path:
            sys.path.insert(0, p)


_bootstrap_legacy_sys_path()

def list_installed_libraries(limit: int = 4000) -> List[str]:
    try:
        from package_catalog_v4 import build_package_catalog  # type: ignore
        catalog = build_package_catalog(max_items=limit)
        names = sorted({it.import_name for it in catalog if getattr(it, "import_name", None)}, key=lambda s: s.lower())
        return names
    except Exception:
        pass
    names = []
    for d in importlib.metadata.distributions():
        n = d.metadata.get("Name")
        if n:
            names.append(n)
    names = sorted(set(names), key=lambda s: s.lower())
    return names[:limit] if limit else names

def _import_analyzer() -> Any:
    """解析器(Analyzer)クラスを返す。

    まず同一パッケージ内の V6 実装を直接 import します（最も壊れにくい）。
    それでもダメな場合にのみ、互換目的で v5/v4 系を試します。
    """
    # 1) 同一パッケージ内（最優先・最安定）
    try:
        from .analyzer_v6 import LibraryAnalyzerV6  # type: ignore
        return LibraryAnalyzerV6
    except Exception as e:
        last_err: Optional[Exception] = e

    # 2) 互換フォールバック（環境によっては存在しない）
    candidates = [
        ("v6.core.analyzer_v6", "LibraryAnalyzerV6"),
        ("analyzer_v6", "LibraryAnalyzerV6"),
        ("v5.analyzer_v5", "LibraryAnalyzerV5"),
        ("analyzer_v5", "LibraryAnalyzerV5"),
        ("v4.analyzer_v4", "LibraryAnalyzerV4"),
        ("library_explorer_v4.analyzer_v4", "LibraryAnalyzerV4"),
        ("analyzer_v4", "LibraryAnalyzerV4"),
    ]
    for mod, cls in candidates:
        try:
            m = importlib.import_module(mod)
            return getattr(m, cls)
        except Exception as e:
            last_err = e

    raise ImportError(f"Analyzer import failed: {repr(last_err)}")


def _normalize_nodes(df_nodes: pd.DataFrame) -> pd.DataFrame:
    if df_nodes is None or df_nodes.empty:
        return df_nodes
    df = df_nodes.copy()
    ren = {}
    for c in df.columns:
        lc = str(c).lower()
        if lc == "type" and c != "Type":
            ren[c] = "Type"
        elif lc == "path" and c != "Path":
            ren[c] = "Path"
        elif lc == "name" and c != "Name":
            ren[c] = "Name"
        elif lc == "id" and c != "ID":
            ren[c] = "ID"
        elif lc == "parent" and c != "Parent":
            ren[c] = "Parent"
        elif lc == "module" and c != "Module":
            ren[c] = "Module"
        elif lc == "params" and c != "Params":
            ren[c] = "Params"
    if ren:
        df = df.rename(columns=ren)
    return df

def _split_tables(df_nodes: pd.DataFrame) -> Dict[str, pd.DataFrame]:
    if df_nodes is None or df_nodes.empty or "Type" not in df_nodes.columns:
        return {k: pd.DataFrame() for k in ["Modules","Classes","Functions","Methods","External"]}
    return {
        "Modules": df_nodes[df_nodes["Type"] == "module"].copy(),
        "Classes": df_nodes[df_nodes["Type"] == "class"].copy(),
        "Functions": df_nodes[df_nodes["Type"] == "function"].copy(),
        "Methods": df_nodes[df_nodes["Type"].isin(["method","property"])].copy(),
        "External": df_nodes[df_nodes["Type"] == "external"].copy(),
    }


def _to_dataframe(obj: Any, *, allow_scalar: bool = False) -> pd.DataFrame:
    """pandas.DataFrameへ安全に変換する。

    - allow_scalar=False: スカラーは空DFにする（nodes/edges向け）
    - allow_scalar=True : スカラーも1行DFに包む（errors向け）
    """
    if obj is None:
        return pd.DataFrame()
    if isinstance(obj, pd.DataFrame):
        return obj
    if isinstance(obj, (list, tuple)):
        try:
            return pd.DataFrame(obj)
        except Exception:
            return pd.DataFrame()
    if isinstance(obj, dict):
        # dictが全スカラーだと DataFrame(obj) は落ちることがあるので、まず1行化を試す
        try:
            return pd.DataFrame([obj])
        except Exception:
            try:
                return pd.DataFrame(obj)
            except Exception:
                return pd.DataFrame()
    if allow_scalar:
        return pd.DataFrame([{"value": obj}])
    return pd.DataFrame()

@st.cache_data(show_spinner=False)
def _cached_analyze(lib_name: str) -> Tuple[Dict[str, Any], pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    Analyzer = _import_analyzer()
    analyzer = Analyzer(lib_name)
    out = analyzer.analyze()

    summary: Dict[str, Any] = {}
    df_nodes = pd.DataFrame()
    df_edges = pd.DataFrame()
    df_errors = pd.DataFrame()

    if isinstance(out, tuple) and len(out) >= 3:
        summary = out[0] or {}
        df_nodes = _to_dataframe(out[1], allow_scalar=False)
        df_edges = _to_dataframe(out[2], allow_scalar=False)
        if len(out) >= 4:
            raw_err = out[3]
            df_errors = _to_dataframe(raw_err, allow_scalar=True)
            if not isinstance(raw_err, (pd.DataFrame, list, tuple, dict)) and raw_err is not None:
                summary["errors_scalar"] = raw_err
    elif isinstance(out, dict):
        summary = out.get("summary", {}) or {}
        df_nodes = _to_dataframe(out.get("nodes", None), allow_scalar=False)
        df_edges = _to_dataframe(out.get("edges", None), allow_scalar=False)
        df_errors = _to_dataframe(out.get("errors", None), allow_scalar=True)
    else:
        raise RuntimeError("Unknown analyzer output format")

    return summary, _normalize_nodes(df_nodes), df_edges, df_errors

def _inject_params_if_missing(df_nodes: pd.DataFrame, types: List[str], max_rows: int = 1200) -> pd.DataFrame:
    if df_nodes is None or df_nodes.empty:
        return df_nodes
    df = df_nodes.copy()
    if "Params" not in df.columns:
        df["Params"] = None

    nonnull = df["Params"].notna().sum()
    if nonnull >= max(10, int(len(df) * 0.05)):
        return df

    cnt = 0
    for i, r in df.iterrows():
        if cnt >= max_rows:
            break
        if str(r.get("Type","")) not in types:
            continue
        if r.get("Params") not in (None, "", [], {}):
            continue
        path = str(r.get("Path") or "")
        if not path:
            continue
        params = inspect_params_from_path(path)
        if params:
            df.at[i, "Params"] = params
            cnt += 1
    return df

@st.cache_data(show_spinner=False)
def _cached_callgraph(root_module: str, nodes: pd.DataFrame, max_files: int, max_edges: int) -> pd.DataFrame:
    try:
        from v6.core.ast_callgraph_v6 import build_ast_call_edges
        return build_ast_call_edges(nodes, root_module=root_module, max_files=max_files, max_edges=max_edges)
    except Exception:
        return pd.DataFrame()

def _guess_root_module(lib_name: str, df_nodes: pd.DataFrame) -> str:
    """distribution名とimport名がズレる問題に対処するため、nodesのmoduleパスから推定する。"""
    if df_nodes is not None and not df_nodes.empty and "Type" in df_nodes.columns and "Path" in df_nodes.columns:
        mods = df_nodes[df_nodes["Type"] == "module"]["Path"].dropna().astype(str).tolist()
        if mods:
            # 先頭セグメントの多数決
            roots = [m.split(".")[0] for m in mods if m]
            if roots:
                s = pd.Series(roots).value_counts()
                if not s.empty:
                    return str(s.index[0])
    # fallback
    s = str(lib_name or "").strip()
    if s and "-" in s:
        s = s.replace("-", "_")
    return s.split(".")[0] if s else s

def analyze_library_with_progress(
    lib_name: str,
    deep_param_inspect: bool = False,
    *,
    enable_callgraph: bool = False,
    callgraph_max_files: int = 600,
    callgraph_max_edges: int = 30000,
) -> Dict[str, Any]:
    total_steps = 7 if enable_callgraph else 6

    progress = st.progress(0, text="Preparing…")
    with st.status(f"Analyzing: {lib_name}", expanded=True) as status:
        status.write(f"Step 1/{total_steps}: analyzer 実行（キャッシュ有）")
        progress.progress(20)

        summary, df_nodes, df_edges, df_errors = _cached_analyze(lib_name)

        status.write(f"Step 2/{total_steps}: テーブル分割")
        progress.progress(45)
        tables = _split_tables(df_nodes)

        status.write(f"Step 3/{total_steps}: 文字列分類（Role/Event/NameCluster）")
        progress.progress(60)
        df_nodes2 = enrich_with_classification(df_nodes)

        status.write(f"Step 4/{total_steps}: Params 補完（必要なら）")
        progress.progress(70)
        if deep_param_inspect:
            df_nodes2 = _inject_params_if_missing(df_nodes2, types=["function", "method", "class"], max_rows=1200)

        status.write(f"Step 5/{total_steps}: 引数対応表/逆引き作成")
        progress.progress(85)
        param_tables = build_param_map_tables(df_nodes2)

        call_edges = pd.DataFrame()
        if enable_callgraph:
            status.write(f"Step 6/{total_steps}: AST call graph（呼び出し関係の推定）")
            progress.progress(92)
            root_mod = _guess_root_module(lib_name, df_nodes2)
            call_edges = _cached_callgraph(root_mod, df_nodes2, int(callgraph_max_files), int(callgraph_max_edges))

        status.write(f"Step {total_steps}/{total_steps}: 完了")
        progress.progress(100)
        status.update(label="Done", state="complete", expanded=False)

    return {
        "library": lib_name,
        "summary": summary,
        "nodes": df_nodes2,
        "edges": df_edges,
        "errors": df_errors,
        "call_edges": call_edges,
        "tables": tables,
        "param_tables": param_tables,
    }
