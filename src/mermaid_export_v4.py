# ファイルパス: C:\lib_ana\src\mermaid_export_v4.py
# （この実行環境では /mnt/data/mermaid_export_v4.py に生成しています）
from __future__ import annotations

from typing import Dict, List

import pandas as pd


def to_mermaid_flowchart(df_nodes: pd.DataFrame, df_edges: pd.DataFrame, lib_name: str,
                         max_nodes: int = 250) -> str:
    if df_nodes.empty:
        return "flowchart TD\n  %% empty\n"

    df = df_nodes.copy()
    df["ParamCount"] = df["ParamNames"].apply(lambda x: len(x) if isinstance(x, list) else 0)
    df["Score"] = df["LOC"].fillna(0).astype(float) + df["ParamCount"].astype(float) * 3.0

    mods = df[df["Type"] == "module"]
    others = df[df["Type"] != "module"].sort_values("Score", ascending=False)
    keep = pd.concat([mods, others]).head(max_nodes)
    keep_ids = set(keep["ID"].tolist())

    def safe_id(x: str) -> str:
        s = "".join(ch if ch.isalnum() else "_" for ch in x)
        if s and s[0].isdigit():
            s = "n_" + s
        return s

    id_map: Dict[str, str] = {rid: safe_id(rid) for rid in keep["ID"].tolist()}

    lines: List[str] = []
    lines.append("flowchart TD")
    lines.append(f"  %% Library: {lib_name}")

    for _, r in keep.iterrows():
        nid = id_map[r["ID"]]
        label = str(r["Name"]).replace('"', "'")
        t = r["Type"]
        if t == "module":
            lines.append(f'  {nid}["{label}"]')
        elif t in ["class", "external"]:
            lines.append(f'  {nid}["{label}"]')
        else:
            lines.append(f'  {nid}("{label}")')

    for _, e in df_edges.iterrows():
        s = e["Src"]; d = e["Dst"]; rel = e["Rel"]
        if s not in keep_ids or d not in keep_ids:
            continue
        sid = id_map[s]; did = id_map[d]
        if rel == "contains":
            lines.append(f"  {sid} --> {did}")
        elif rel == "inherits":
            lines.append(f"  {sid} -. inherits .-> {did}")
        elif rel == "reexports":
            lines.append(f"  {sid} -. reexports .-> {did}")
        elif rel == "related_param":
            lines.append(f"  {sid} == shared_param ==> {did}")
        elif rel == "related_event":
            lines.append(f"  {sid} == shared_event ==> {did}")
        else:
            lines.append(f"  {sid} --- {did}")

    return "\n".join(lines) + "\n"
