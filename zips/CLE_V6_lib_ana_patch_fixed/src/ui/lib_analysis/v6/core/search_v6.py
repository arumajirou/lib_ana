# ファイルパス: C:\lib_ana\src\v6\core\search_v6.py
from __future__ import annotations

from typing import Any, List, Sequence, Tuple

import re
import pandas as pd

try:
    from rapidfuzz import fuzz, process  # type: ignore
except Exception:  # pragma: no cover
    fuzz = None
    process = None


def _safe_str(x: Any) -> str:
    try:
        return "" if x is None else str(x)
    except Exception:
        return ""


def _make_text_row(row: pd.Series, cols: Sequence[str]) -> str:
    parts: List[str] = []
    for c in cols:
        if c in row.index:
            s = _safe_str(row.get(c))
            if s:
                parts.append(s)
    return "\n".join(parts)


def search_nodes_text(
    nodes: pd.DataFrame,
    query: str,
    *,
    cols: Sequence[str] = ("Path", "Name", "Docstring", "Module"),
    limit: int = 100,
) -> pd.DataFrame:
    'シンプル文字検索（部分一致）。高速・確実。'
    if nodes is None or nodes.empty:
        return pd.DataFrame()

    q = (query or "").strip()
    if not q:
        return pd.DataFrame()

    ql = q.lower()
    df = nodes.copy()

    use_cols = [c for c in cols if c in df.columns]
    if not use_cols:
        return pd.DataFrame()

    mask = False
    for c in use_cols:
        s = df[c].astype(str).str.lower()
        mask = mask | s.str.contains(ql, na=False)
    df = df[mask].copy()
    if df.empty:
        return df

    # スコア（雑：出現回数の合計）
    score = 0
    for c in use_cols:
        s = df[c].astype(str).str.lower()
        score = score + s.str.count(re.escape(ql))
    df["Score"] = score
    df = df.sort_values("Score", ascending=False)
    return df.head(limit)


def search_nodes_fuzzy(
    nodes: pd.DataFrame,
    query: str,
    *,
    key_col: str = "Path",
    limit: int = 80,
) -> pd.DataFrame:
    '曖昧検索（fuzzy：綴り違いに強い）。'
    if nodes is None or nodes.empty:
        return pd.DataFrame()

    q = (query or "").strip()
    if not q:
        return pd.DataFrame()

    if process is None:
        return search_nodes_text(nodes, query, limit=limit)

    df = nodes.copy()
    if key_col not in df.columns:
        key_col = "Name" if "Name" in df.columns else df.columns[0]

    keys = df[key_col].astype(str).tolist()
    hits = process.extract(q, keys, scorer=fuzz.WRatio, limit=limit)
    if not hits:
        return pd.DataFrame()

    idx = [h[2] for h in hits]
    out = df.iloc[idx].copy()
    out["Score"] = [float(h[1]) for h in hits]
    out = out.sort_values("Score", ascending=False)
    return out


def build_documents_for_nodes(
    nodes: pd.DataFrame,
    *,
    text_cols: Sequence[str] = ("Path", "Name", "Docstring", "Module"),
    include_params: bool = True,
) -> Tuple[List[str], pd.DataFrame]:
    'semantic index用の「文書」(テキスト)をノードから作る。'
    if nodes is None or nodes.empty:
        return [], pd.DataFrame()

    df = nodes.copy()

    if include_params and "Params" in df.columns:
        def _p2s(p: Any) -> str:
            if p is None:
                return ""
            if isinstance(p, list):
                names = []
                for it in p:
                    if isinstance(it, dict) and it.get("name"):
                        names.append(str(it["name"]))
                    elif isinstance(it, str):
                        names.append(it)
                return " ".join(names)
            if isinstance(p, dict):
                return " ".join(map(str, p.keys()))
            return ""
        df["_ParamsText"] = df["Params"].apply(_p2s)
        cols = list(text_cols) + ["_ParamsText"]
    else:
        cols = list(text_cols)

    use_cols = [c for c in cols if c in df.columns]
    docs = [_make_text_row(r, use_cols) for _, r in df.iterrows()]
    return docs, df
