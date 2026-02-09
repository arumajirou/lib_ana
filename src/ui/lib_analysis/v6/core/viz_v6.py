# ファイルパス: C:\lib_ana\src\v6\core\viz_v6.py
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

import pandas as pd


def _pick_edge_cols(edges: pd.DataFrame) -> Optional[Tuple[str, str]]:
    if edges is None or edges.empty:
        return None
    cols = set(map(str, edges.columns))
    for a, b in [
        ("Source", "Target"),
        ("From", "To"),
        ("src", "dst"),
        ("Src", "Dst"),
        ("source", "target"),
        ("from", "to"),
        ("Caller", "Callee"),
        ("caller", "callee"),
    ]:
        if a in cols and b in cols:
            return a, b
    if len(edges.columns) >= 2:
        return str(edges.columns[0]), str(edges.columns[1])
    return None


def _filter_by_prefix(df: pd.DataFrame, prefix: str) -> pd.DataFrame:
    if df is None or df.empty or not prefix:
        return df
    p = str(prefix)
    if "Module" in df.columns:
        m = df["Module"].astype(str).str.startswith(p)
        return df[m].copy()
    if "Path" in df.columns:
        m = df["Path"].astype(str).str.startswith(p)
        return df[m].copy()
    return df


def build_sunburst_frame(
    nodes: pd.DataFrame,
    *,
    prefix: str = "",
    max_nodes: int = 2500,
) -> pd.DataFrame:
    """Plotly Sunburst 用のノード表（ids/parents 形式）を作る。

    Plotly Express の px.sunburst(path=...) は「全行が葉（leaf）」である必要があり、
    モジュール行や深さが不揃いな行が混ざると ValueError になります。
    そこで、ids/parents 形式（内部ノードも含む）に変換して安全に描画できるようにします。

    ルール（作業仮説）:
      - Sunburst は “API（class/function/method/property/external）” を葉として数える
      - 親ノードの count は「その配下の葉の数」
      - 階層は Module + Path（末尾は Name と重複するなら除外） + Type + Name
    """
    if nodes is None or nodes.empty:
        return pd.DataFrame()

    df = _filter_by_prefix(nodes, prefix)
    if df is None or df.empty:
        return pd.DataFrame()

    if "Type" in df.columns:
        leaf_df = df[df["Type"].astype(str) != "module"].copy()
    else:
        leaf_df = df.copy()

    if leaf_df.empty:
        return pd.DataFrame()

    # 重くなりすぎ防止（葉を絞る）
    if len(leaf_df) > max_nodes:
        leaf_df = leaf_df.head(max_nodes).copy()

    def segs_for_row(r: pd.Series) -> List[str]:
        t = str(r.get("Type", "") or "item")
        mod = str(r.get("Module", "") or "")
        path = str(r.get("Path", "") or "")
        name = str(r.get("Name", "") or "")

        mod_segs = [x for x in mod.split(".") if x]
        path_segs = [x for x in path.split(".") if x]

        leaf = name or (path_segs[-1] if path_segs else "") or str(r.get("ID", ""))

        # Path の末尾が Name と同じなら、Path 側は末尾を落として二重化を回避
        if path_segs and leaf and path_segs[-1] == leaf:
            path_segs = path_segs[:-1]

        base = mod_segs + path_segs

        # たまに Path がフルパス（Module 先頭を含む）になっているケースの重複を軽くケア
        if mod_segs and path_segs and path_segs[0] == mod_segs[0]:
            base = mod_segs + path_segs[1:]

        return base + [t, leaf]

    segs: List[List[str]] = leaf_df.apply(segs_for_row, axis=1).tolist()

    counts: Dict[str, int] = {}
    labels: Dict[str, str] = {}
    parents: Dict[str, str] = {}

    # 各“葉”を1カウントとして、prefixノードにも加算（= その配下の葉の数）
    for s in segs:
        prefix_parts: List[str] = []
        for part in s:
            prefix_parts.append(part)
            node_id = "|".join(prefix_parts)
            parent_id = "|".join(prefix_parts[:-1])
            counts[node_id] = counts.get(node_id, 0) + 1
            labels[node_id] = part
            parents[node_id] = parent_id if parent_id else ""

    out = pd.DataFrame({"id": list(counts.keys())})
    out["label"] = out["id"].map(labels)
    out["parent"] = out["id"].map(parents)
    out["count"] = out["id"].map(counts).astype(int)

    # depth順 → 大きい順（俯瞰しやすさ）
    out["_depth"] = out["id"].astype(str).str.count(r"\|") + 1
    out = out.sort_values(["_depth", "count"], ascending=[True, False]).drop(columns=["_depth"])

    return out


def extract_unique_param_names(nodes: pd.DataFrame) -> pd.DataFrame:
    if nodes is None or nodes.empty or "Params" not in nodes.columns:
        return pd.DataFrame(columns=["ParamName", "Count"])
    names: List[str] = []
    for p in nodes["Params"]:
        if isinstance(p, list):
            for it in p:
                if isinstance(it, dict) and it.get("name"):
                    names.append(str(it["name"]))
                elif isinstance(it, str):
                    names.append(it)
        elif isinstance(p, dict):
            names += [str(k) for k in p.keys()]
    if not names:
        return pd.DataFrame(columns=["ParamName", "Count"])
    s = pd.Series(names)
    df = s.value_counts().reset_index()
    df.columns = ["ParamName", "Count"]
    return df


def extract_unique_return_types(nodes: pd.DataFrame) -> pd.DataFrame:
    if nodes is None or nodes.empty:
        return pd.DataFrame(columns=["ReturnType", "Count"])
    col = None
    for c in ["ReturnType", "Returns", "Return", "return_type", "returns"]:
        if c in nodes.columns:
            col = c
            break
    if not col:
        return pd.DataFrame(columns=["ReturnType", "Count"])
    s = nodes[col].dropna().astype(str)
    if s.empty:
        return pd.DataFrame(columns=["ReturnType", "Count"])
    df = s.value_counts().reset_index()
    df.columns = ["ReturnType", "Count"]
    return df


def filter_errors(errors: pd.DataFrame, *, prefix: str = "") -> pd.DataFrame:
    if errors is None or errors.empty or not prefix:
        return errors
    p = str(prefix)
    for c in ["Path", "Module", "Where", "location", "Location"]:
        if c in errors.columns:
            m = errors[c].astype(str).str.contains(p, na=False)
            return errors[m].copy()
    return errors


def build_scoped_graph(
    nodes: pd.DataFrame,
    edges: pd.DataFrame,
    *,
    prefix: str = "",
    max_nodes: int = 120,
    max_edges: int = 300,
) -> Tuple[Optional["Any"], Dict[str, str], Optional[Tuple[str, str]]]:
    """networkx グラフ(有向)とラベル辞書を返す（見つからない/未インストールなら None）。"""
    try:
        import networkx as nx  # type: ignore
    except Exception:
        return None, {}, None

    if nodes is None or nodes.empty:
        return nx.DiGraph(), {}, _pick_edge_cols(edges)

    df_n = _filter_by_prefix(nodes, prefix) if prefix else nodes
    if df_n.empty:
        df_n = nodes.head(max_nodes).copy()

    if len(df_n) > max_nodes:
        # Typeで優先度を付けて間引く
        order = {"module": 0, "class": 1, "function": 2, "method": 3, "property": 3, "external": 4}
        if "Type" in df_n.columns:
            df_n = df_n.copy()
            df_n["_tord"] = df_n["Type"].astype(str).str.lower().map(lambda x: order.get(x, 9))
            df_n = df_n.sort_values(["_tord", "Path", "Name"]).drop(columns=["_tord"], errors="ignore")
        df_n = df_n.head(max_nodes).copy()

    id_to_label: Dict[str, str] = {}
    for _, r in df_n.iterrows():
        nid = str(r.get("ID", ""))
        if not nid:
            continue
        t = str(r.get("Type", ""))
        label = str(r.get("Path") or r.get("Name") or nid)
        id_to_label[nid] = (f"{t}: {label}" if t else label)

    keep = set(id_to_label.keys())
    g = nx.DiGraph()
    for nid, lab in id_to_label.items():
        g.add_node(nid, label=lab)

    edge_cols = _pick_edge_cols(edges)
    if edge_cols is None or edges is None or edges.empty:
        return g, id_to_label, edge_cols

    src_col, dst_col = edge_cols
    df_e = edges.copy()
    df_e[src_col] = df_e[src_col].astype(str)
    df_e[dst_col] = df_e[dst_col].astype(str)
    df_e = df_e[df_e[src_col].isin(keep) & df_e[dst_col].isin(keep)].copy()
    if len(df_e) > max_edges:
        df_e = df_e.head(max_edges).copy()

    rel_col = None
    for c in ["Relation", "Type", "relation", "type", "Label", "label"]:
        if c in df_e.columns:
            rel_col = c
            break

    for _, r in df_e.iterrows():
        a = str(r.get(src_col, ""))
        b = str(r.get(dst_col, ""))
        if not a or not b:
            continue
        rel = str(r.get(rel_col, ""))[:40] if rel_col else ""
        g.add_edge(a, b, relation=rel)

    return g, id_to_label, edge_cols
