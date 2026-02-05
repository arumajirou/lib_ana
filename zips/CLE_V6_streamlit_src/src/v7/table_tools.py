# ファイルパス: C:\lib_ana\src\v6\table_tools.py
from __future__ import annotations

from typing import Dict, List, Tuple
import pandas as pd

TYPE_COLOR = {
    "module": "#eef2ff",
    "class": "#ecfeff",
    "function": "#f0fdf4",
    "method": "#fff7ed",
    "property": "#fefce8",
    "external": "#fdf2f8",
}

def style_by_type(df: pd.DataFrame) -> "pd.io.formats.style.Styler":
    if df is None or df.empty or "Type" not in df.columns:
        return df.style
    def _row_style(row):
        t = str(row.get("Type","")).lower()
        bg = TYPE_COLOR.get(t, "")
        return [f"background-color: {bg}" if bg else "" for _ in row]
    return df.style.apply(_row_style, axis=1)

def build_param_reverse_index(nodes: pd.DataFrame) -> Tuple[pd.DataFrame, Dict[str, List[str]]]:
    """一意引数名→API(パス) 逆引き.

    analyzer_v4 の Nodes に Params 列（dict/list）が入っている想定。
    無い場合は空で返す（落とさない）。
    """
    if nodes is None or nodes.empty:
        return pd.DataFrame(columns=["ParamName","Count"]), {}

    if "Params" not in nodes.columns:
        return pd.DataFrame(columns=["ParamName","Count"]), {}

    rev: Dict[str, List[str]] = {}
    for _, r in nodes.iterrows():
        params = r.get("Params", None)
        path = str(r.get("Path") or r.get("Name") or "")
        if not params:
            continue
        # params が list[dict] or list[str] or dict などの揺れに対応
        if isinstance(params, dict):
            names = list(params.keys())
        elif isinstance(params, list):
            names = []
            for it in params:
                if isinstance(it, dict) and "name" in it:
                    names.append(str(it["name"]))
                elif isinstance(it, str):
                    names.append(it)
        else:
            names = []
        for p in names:
            p = str(p)
            if not p:
                continue
            rev.setdefault(p, []).append(path)

    rows = [{"ParamName": k, "Count": len(v)} for k, v in rev.items()]
    df = pd.DataFrame(rows).sort_values("Count", ascending=False)
    return df, rev

def metric_summary_table(summary: dict) -> pd.DataFrame:
    keys = ["Modules","Classes","Functions","Methods/Props","External","UniqueParamNames","UniqueReturnTypes","Errors"]
    return pd.DataFrame({"Metric": keys, "Value": [summary.get(k,0) for k in keys]})
