# ファイルパス: C:\lib_ana\src\v6\core\mermaid_v6.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Tuple
import re

import pandas as pd


_EDGE_COL_CANDIDATES: List[Tuple[str, str]] = [
    ("Source", "Target"),
    ("From", "To"),
    ("src", "dst"),
    ("Src", "Dst"),
    ("source", "target"),
    ("from", "to"),
    ("Caller", "Callee"),
    ("caller", "callee"),
]


def _pick_edge_cols(df_edges: pd.DataFrame) -> Optional[Tuple[str, str]]:
    if df_edges is None or df_edges.empty:
        return None
    cols = set(map(str, df_edges.columns))
    for a, b in _EDGE_COL_CANDIDATES:
        if a in cols and b in cols:
            return a, b
    # 最後の手段：先頭2列
    if len(df_edges.columns) >= 2:
        return str(df_edges.columns[0]), str(df_edges.columns[1])
    return None


def _sanitize_id(s: str) -> str:
    s = re.sub(r"[^0-9a-zA-Z_]", "_", s)
    if not s:
        return "n"
    if s[0].isdigit():
        return "n_" + s
    return s


def _build_id_label_map(nodes: pd.DataFrame) -> Dict[str, str]:
    if nodes is None or nodes.empty:
        return {}
    out: Dict[str, str] = {}
    for _, r in nodes.iterrows():
        nid = str(r.get("ID", ""))
        if not nid:
            continue
        t = str(r.get("Type", ""))
        name = str(r.get("Name", ""))
        path = str(r.get("Path", ""))
        label = path or name or nid
        if t:
            label = f"{t}: {label}"
        out[nid] = label
    return out


def _filter_nodes_by_prefix(nodes: pd.DataFrame, prefix: str) -> pd.DataFrame:
    if not prefix or nodes is None or nodes.empty:
        return nodes
    p = str(prefix)
    if "Module" in nodes.columns:
        m = nodes["Module"].astype(str).str.startswith(p)
        return nodes[m].copy()
    if "Path" in nodes.columns:
        m = nodes["Path"].astype(str).str.startswith(p)
        return nodes[m].copy()
    return nodes


def mermaid_flowchart(
    nodes: pd.DataFrame,
    edges: pd.DataFrame,
    *,
    prefix: str = "",
    direction: str = "TD",
    max_nodes: int = 80,
    max_edges: int = 200,
) -> str:
    """関係グラフを Mermaid(mermaid.js) の flowchart にする。

    Notes:
      - 入力の edges 仕様はライブラリごとにブレるので、列名の推定をする。
      - でかすぎるグラフはブラウザが死ぬので上限をかける。
    """
    nodes_scoped = _filter_nodes_by_prefix(nodes, prefix)
    if nodes_scoped is None or nodes_scoped.empty:
        return f"graph {direction}\n  %% no nodes"

    # ノードを優先度順に減らす（module/class/function/method/external）
    if "Type" in nodes_scoped.columns:
        order = {"module": 0, "class": 1, "function": 2, "method": 3, "property": 3, "external": 4}
        nodes_scoped = nodes_scoped.copy()
        nodes_scoped["_tord"] = nodes_scoped["Type"].astype(str).str.lower().map(lambda x: order.get(x, 9))
        nodes_scoped = nodes_scoped.sort_values(["_tord", "Path", "Name"]).drop(columns=["_tord"], errors="ignore")

    if len(nodes_scoped) > max_nodes:
        nodes_scoped = nodes_scoped.head(max_nodes).copy()

    id_to_label = _build_id_label_map(nodes_scoped)
    keep_ids = set(id_to_label.keys())

    edge_cols = _pick_edge_cols(edges)
    if edge_cols is None:
        lines = [f"graph {direction}"]
        for nid, label in list(id_to_label.items())[:max_nodes]:
            sid = _sanitize_id(nid)
            lines.append(f"  {sid}[\"{label}\"]")
        lines.append("  %% no edges")
        return "\n".join(lines)

    src_col, dst_col = edge_cols
    df_e = edges.copy()

    # relation label (任意)
    rel_col = None
    for c in ["Relation", "Type", "relation", "type", "Label", "label"]:
        if c in df_e.columns:
            rel_col = c
            break

    # まずはスコープ内のエッジだけ
    df_e[src_col] = df_e[src_col].astype(str)
    df_e[dst_col] = df_e[dst_col].astype(str)
    df_e = df_e[df_e[src_col].isin(keep_ids) & df_e[dst_col].isin(keep_ids)].copy()

    if len(df_e) > max_edges:
        df_e = df_e.head(max_edges).copy()

    lines = [f"graph {direction}"]
    # ノード定義
    for nid, label in id_to_label.items():
        sid = _sanitize_id(nid)
        safe_label = label.replace('"', "'")
        lines.append(f"  {sid}[\"{safe_label}\"]")

    # エッジ
    for _, r in df_e.iterrows():
        s = _sanitize_id(str(r.get(src_col, "")))
        t = _sanitize_id(str(r.get(dst_col, "")))
        if not s or not t:
            continue
        if rel_col:
            rel = str(r.get(rel_col, "")).strip()
            rel = rel.replace("|", "/")[:40]
            if rel:
                lines.append(f"  {s} -->|{rel}| {t}")
                continue
        lines.append(f"  {s} --> {t}")

    return "\n".join(lines)


def mermaid_sequence(
    nodes: pd.DataFrame,
    edges: pd.DataFrame,
    *,
    start_id: str,
    depth: int = 2,
    max_steps: int = 50,
) -> str:
    """選択ノードからの呼び出し/依存の流れを Mermaid sequenceDiagram にする。

    edges の「向き」が呼び出し方向と一致している保証はないので、
    ここでは “start_id から辿れる有向エッジ” をそのまま並べる（作業仮説）。
    """
    if not start_id:
        return "sequenceDiagram\n  %% no start"

    edge_cols = _pick_edge_cols(edges)
    if edge_cols is None or edges is None or edges.empty:
        return "sequenceDiagram\n  %% no edges"

    src_col, dst_col = edge_cols
    df_e = edges.copy()
    df_e[src_col] = df_e[src_col].astype(str)
    df_e[dst_col] = df_e[dst_col].astype(str)

    # relation label
    rel_col = None
    for c in ["Relation", "Type", "relation", "type", "Label", "label"]:
        if c in df_e.columns:
            rel_col = c
            break

    id_to_label = _build_id_label_map(nodes)

    # BFSで辿る
    frontier = [str(start_id)]
    seen = {str(start_id)}
    steps: List[Tuple[str, str, str]] = []
    for _ in range(depth):
        next_frontier: List[str] = []
        for cur in frontier:
            out = df_e[df_e[src_col] == cur]
            for _, r in out.iterrows():
                if len(steps) >= max_steps:
                    break
                a = str(r.get(src_col, ""))
                b = str(r.get(dst_col, ""))
                rel = str(r.get(rel_col, ""))[:40] if rel_col else ""
                steps.append((a, b, rel))
                if b and b not in seen:
                    seen.add(b)
                    next_frontier.append(b)
            if len(steps) >= max_steps:
                break
        frontier = next_frontier
        if not frontier or len(steps) >= max_steps:
            break

    # 参加者
    participants: List[str] = []
    for a, b, _ in steps:
        if a not in participants:
            participants.append(a)
        if b not in participants:
            participants.append(b)
    participants = participants[:30]

    def label(nid: str) -> str:
        t = id_to_label.get(nid, nid)
        # participant名は記号に弱いので短縮
        t = re.sub(r"[^0-9a-zA-Z_.:/ -]", "_", t)
        return t[:60]

    lines = ["sequenceDiagram"]
    for pid in participants:
        pname = _sanitize_id(pid)
        lines.append(f"  participant {pname} as \"{label(pid)}\"")
    for a, b, rel in steps:
        pa = _sanitize_id(a)
        pb = _sanitize_id(b)
        msg = (rel or "call")
        msg = msg.replace('"', "'")
        lines.append(f"  {pa}->>{pb}: {msg}")

    if not steps:
        lines.append("  %% no reachable steps")
    return "\n".join(lines)
