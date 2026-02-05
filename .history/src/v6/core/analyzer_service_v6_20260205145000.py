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


# --- v4/v5のトップレベルimport前提を成立させる ---
def _bootstrap_legacy_sys_path() -> None:
    """
    v4/v5の旧実装が `models_v4` のようなトップレベルimport前提なので、
    それらの実体が置かれているディレクトリを sys.path に追加する。
    """
    src_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))

    legacy_dirs = [
        os.path.join(
            src_root, "library_explorer_v4"
        ),  # models_v4 / taxonomy_v4 / package_catalog_v4 等
        os.path.join(src_root, "v5"),  # v5系をトップレベルimportするケースの保険
        src_root,  # 念のため
    ]

    for p in legacy_dirs:
        if os.path.isdir(p) and p not in sys.path:
            sys.path.insert(0, p)


_bootstrap_legacy_sys_path()
# --- ここまで ---


def list_installed_libraries(limit: int = 4000) -> List[str]:
    try:
        from package_catalog_v4 import build_package_catalog  # type: ignore

        catalog = build_package_catalog(max_items=limit)
        names = sorted(
            {it.import_name for it in catalog if getattr(it, "import_name", None)},
            key=lambda s: s.lower(),
        )
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
    candidates = [
        ("v5.analyzer_v5", "LibraryAnalyzerV5"),
        ("analyzer_v5", "LibraryAnalyzerV5"),
        ("analyzer_v4", "LibraryAnalyzerV4"),
    ]
    last_err: Optional[Exception] = None
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
        return {
            k: pd.DataFrame()
            for k in ["Modules", "Classes", "Functions", "Methods", "External"]
        }
    return {
        "Modules": df_nodes[df_nodes["Type"] == "module"].copy(),
        "Classes": df_nodes[df_nodes["Type"] == "class"].copy(),
        "Functions": df_nodes[df_nodes["Type"] == "function"].copy(),
        "Methods": df_nodes[df_nodes["Type"].isin(["method", "property"])].copy(),
        "External": df_nodes[df_nodes["Type"] == "external"].copy(),
    }


def _to_dataframe(obj: Any, *, allow_scalar: bool = False) -> pd.DataFrame:
    """
    pandas.DataFrameに安全に変換する。
    - allow_scalar=False: スカラーは空DataFrameにする（nodes/edges向け）
    - allow_scalar=True : スカラーも1行DataFrameに包む（errors向け）
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
        # dictが「全部スカラー」だと DataFrame(obj) はコケやすいので、まず1行化を試す
        try:
            return pd.DataFrame([obj])
        except Exception:
            try:
                return pd.DataFrame(obj)
            except Exception:
                return pd.DataFrame()

    # ここからはスカラーっぽいもの
    if allow_scalar:
        return pd.DataFrame([{"value": obj}])

    return pd.DataFrame()


@st.cache_data(show_spinner=False)
def _cached_analyze(
    lib_name: str,
) -> Tuple[Dict[str, Any], pd.DataFrame, pd.DataFrame, pd.DataFrame]:
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
            # ★ここが今回の本丸：errorsはスカラーでも受ける
            raw_err = out[3]
            df_errors = _to_dataframe(raw_err, allow_scalar=True)

            # スカラーだった場合はsummaryにも残す（原因究明用）
            if (
                not isinstance(raw_err, (pd.DataFrame, list, tuple, dict))
                and raw_err is not None
            ):
                summary["errors_scalar"] = raw_err

    elif isinstance(out, dict):
        summary = out.get("summary", {}) or {}
        df_nodes = _to_dataframe(out.get("nodes", None), allow_scalar=False)
        df_edges = _to_dataframe(out.get("edges", None), allow_scalar=False)
        df_errors = _to_dataframe(out.get("errors", None), allow_scalar=True)

    else:
        raise RuntimeError("Unknown analyzer output format")

    return summary, _normalize_nodes(df_nodes), df_edges, df_errors


def _inject_params_if_missing(
    df_nodes: pd.DataFrame, types: List[str], max_rows: int = 1200
) -> pd.DataFrame:
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
        if str(r.get("Type", "")) not in types:
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


def analyze_library_with_progress(
    lib_name: str, deep_param_inspect: bool = False
) -> Dict[str, Any]:
    progress = st.progress(0, text="Preparing…")
    with st.status(f"Analyzing: {lib_name}", expanded=True) as status:
        status.write("Step 1/6: analyzer 実行（キャッシュ有）")
        progress.progress(20)

        summary, df_nodes, df_edges, df_errors = _cached_analyze(lib_name)

        status.write("Step 2/6: テーブル分割")
        progress.progress(45)
        tables = _split_tables(df_nodes)

        status.write("Step 3/6: 文字列分類（Role/Event/NameCluster）")
        progress.progress(60)
        df_nodes2 = enrich_with_classification(df_nodes)

        status.write("Step 4/6: Params 補完（必要なら）")
        progress.progress(70)
        if deep_param_inspect:
            df_nodes2 = _inject_params_if_missing(
                df_nodes2, types=["function", "method", "class"], max_rows=1200
            )

        status.write("Step 5/6: 引数対応表/逆引き作成")
        progress.progress(85)
        param_tables = build_param_map_tables(df_nodes2)

        status.write("Step 6/6: 完了")
        progress.progress(100)
        status.update(label="Done", state="complete", expanded=False)

    return {
        "library": lib_name,
        "summary": summary,
        "nodes": df_nodes2,
        "edges": df_edges,
        "errors": df_errors,
        "tables": tables,
        "param_tables": param_tables,
    }
