# ファイルパス: C:\lib_ana\src\v6\core\param_map_v6.py
from __future__ import annotations
from typing import Any, Dict, List, Tuple
import pandas as pd

def build_param_map_tables(df_nodes: pd.DataFrame) -> Dict[str, pd.DataFrame]:
    if df_nodes is None or df_nodes.empty:
        return {"ParamMap": pd.DataFrame(), "ParamOverview": pd.DataFrame()}
    if "Params" not in df_nodes.columns:
        return {"ParamMap": pd.DataFrame(), "ParamOverview": pd.DataFrame()}

    rows: List[Dict[str, Any]] = []
    for _, r in df_nodes.iterrows():
        params = r.get("Params")
        if not params:
            continue
        if isinstance(params, dict):
            iterable = [{"name": k, "annotation": str(v)} for k, v in params.items()]
        elif isinstance(params, list):
            iterable = params
        else:
            continue

        for p in iterable:
            if isinstance(p, dict):
                pname = p.get("name")
                ptype = p.get("annotation", "")
                kind = p.get("kind", "")
                has_default = bool(p.get("has_default", False))
                default = p.get("default_repr", "")
            else:
                pname = str(p)
                ptype = ""
                kind = ""
                has_default = False
                default = ""
            if not pname:
                continue
            rows.append(
                {
                    "ParamName": str(pname),
                    "Kind": str(kind),
                    "ParamType": str(ptype),
                    "HasDefault": bool(has_default),
                    "Default": str(default),
                    "NodeType": r.get("Type"),
                    "NodeName": r.get("Name"),
                    "Path": r.get("Path"),
                    "Module": r.get("Module"),
                }
            )

    df_map = pd.DataFrame(rows)
    if df_map.empty:
        return {"ParamMap": df_map, "ParamOverview": pd.DataFrame()}

    df_over = (
        df_map.groupby("ParamName")
        .agg(
            Count=("ParamName", "size"),
            Types=("ParamType", lambda x: ", ".join(sorted({str(v) for v in x if v and v != 'None'}))),
            NodeTypes=("NodeType", lambda x: ", ".join(sorted({str(v) for v in x if v}))),
            HasDefaultRate=("HasDefault", "mean"),
        )
        .reset_index()
        .sort_values(["Count", "ParamName"], ascending=[False, True])
    )
    return {"ParamMap": df_map, "ParamOverview": df_over}

def build_param_reverse_index(df_map: pd.DataFrame) -> Tuple[pd.DataFrame, Dict[str, List[str]]]:
    if df_map is None or df_map.empty:
        return pd.DataFrame(columns=["ParamName","Count"]), {}
    rev: Dict[str, List[str]] = {}
    for _, r in df_map.iterrows():
        p = str(r.get("ParamName") or "")
        path = str(r.get("Path") or "")
        if not p or not path:
            continue
        rev.setdefault(p, []).append(path)
    rows = [{"ParamName": k, "Count": len(v)} for k, v in rev.items()]
    df_idx = pd.DataFrame(rows).sort_values("Count", ascending=False)
    return df_idx, rev
