# C:\lib_ana\src\v6\core\param_map_v6.py
from __future__ import annotations

from typing import Dict, List, Any
import pandas as pd


def build_param_map_tables(df_nodes: pd.DataFrame) -> Dict[str, pd.DataFrame]:
    """
    df_nodes に signature/params 情報があれば最良。
    無い場合は v5 が作っている UniqueParamNames 相当は別途注入する設計に拡張可能。
    ここではまず “Name/Path/Type/Module” から作れる最小の対応表を用意する。
    """
    # 解析器側が params を列として持っているケースを想定（例: Params=[...])
    if df_nodes is None or df_nodes.empty:
        return {"ParamMap": pd.DataFrame(), "ParamOverview": pd.DataFrame()}

    if "Params" not in df_nodes.columns:
        # まだ params を持っていない場合：空で返す（後で analyzer_v6 拡張で埋める）
        return {"ParamMap": pd.DataFrame(), "ParamOverview": pd.DataFrame()}

    rows: List[Dict[str, Any]] = []
    for _, r in df_nodes.iterrows():
        params = r.get("Params")
        if not isinstance(params, list):
            continue
        for p in params:
            # p は dict か str を想定
            if isinstance(p, dict):
                pname = p.get("name")
                ptype = p.get("annotation", "")
                has_default = bool(p.get("has_default"))
                default = p.get("default_repr", "")
            else:
                pname = str(p)
                ptype = ""
                has_default = False
                default = ""
            rows.append(
                {
                    "ParamName": pname,
                    "ParamType": ptype,
                    "HasDefault": has_default,
                    "Default": default,
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
            Types=("ParamType", lambda x: ", ".join(sorted({str(v) for v in x if v}))),
            NodeTypes=(
                "NodeType",
                lambda x: ", ".join(sorted({str(v) for v in x if v})),
            ),
            HasDefaultRate=("HasDefault", "mean"),
        )
        .reset_index()
        .sort_values(["Count", "ParamName"], ascending=[False, True])
    )

    return {"ParamMap": df_map, "ParamOverview": df_over}
