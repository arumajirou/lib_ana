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
    """Plotly sunburst 用のフラットなDFを作る。

    ルール（作業仮説）:
      - module はそのまま階層
      - class/function/method/property は module階層の下に type を挟んで葉にする
      - external は module階層の下に external を挟んで葉にする
    """
    if nodes is None or nodes.empty:
        return pd.DataFrame()
    df = _filter_by_prefix(nodes, prefix)
    if df.empty:
        return pd.DataFrame()

    # 重くなりすぎ防止
    if len(df) > max_nodes:
        df = df.head(max_nodes).copy()


    # plotly.express.sunburst(path=...) は「葉(leaf)行のみ」前提。
    # module行をそのまま入れると、同じ階層に子がある場合に
    # "Non-leaves rows are not permitted" で落ちる。
    if "Type" in df.columns:
        t = df["Type"].astype(str).str.lower()
        df = df[t != "module"].copy()
    if df.empty:
        return pd.DataFrame()

    def segs_for_row(r: pd.Series) -> List[str]:
        t = str(r.get("Type", ""))
        mod = str(r.get("Module", ""))
        path = str(r.get("Path", ""))
        name = str(r.get("Name", ""))
        base = (mod or path or "").split(".") if (mod or path) else []
        base = [x for x in base if x]
        if t == "module":
            base = (path or mod).split(".")
            base = [x for x in base if x]
            return base
        leaf = name or (path.split(".")[-1] if path else "")
        if not leaf:
            leaf = str(r.get("ID", ""))
        return base + [t or "item", leaf]

    segs = df.apply(segs_for_row, axis=1).tolist()
    max_depth = max((len(x) for x in segs), default=1)
    cols = [f"L{i+1}" for i in range(max_depth)]

    rows: List[Dict[str, Any]] = []
    for s in segs:
        row: Dict[str, Any] = {c: None for c in cols}
        for i, v in enumerate(s):
            row[f"L{i+1}"] = v
        rows.append(row)

    out = pd.DataFrame(rows)
    out["count"] = 1
    return out




def build_sunburst_tree(
    nodes: pd.DataFrame,
    *,
    prefix: str = "",
    max_nodes: int = 2500,
) -> pd.DataFrame:
    """Sunburst用のツリーDF（ids/parents方式）を作る。

    plotly.express.sunburst(path=...) は「葉のみ」制約が厳しく、
    深さが混在する/中間ノード行が混ざると落ちやすい。
    そこで ids/parents 形式のDFを返して、非葉も含めて安全に描けるようにする。

    返却DF: columns = ["id","parent","label","value","depth"]
    """
    if nodes is None or nodes.empty:
        return pd.DataFrame()

    df = _filter_by_prefix(nodes, prefix)
    if df.empty:
        return pd.DataFrame()

    if len(df) > max_nodes:
        df = df.head(max_nodes).copy()

    if "Type" not in df.columns:
        return pd.DataFrame()

    def segs_for_row(r: pd.Series) -> List[str]:
        t = str(r.get("Type", "")).lower()
        mod = str(r.get("Module", "") or "")
        path = str(r.get("Path", "") or "")
        name = str(r.get("Name", "") or "")

        base = (mod or path or "").split(".") if (mod or path) else []
        base = [x for x in base if x]

        # module自体は葉として入れない（内部ノードとしてパスに自然に現れる）
        leaf = name or (path.split(".")[-1] if path else "")
        if not leaf:
            leaf = str(r.get("ID", ""))

        return base + [t or "item", leaf]

    segs_list = df.apply(segs_for_row, axis=1).tolist()

    from collections import defaultdict

    parent: Dict[str, str] = {}
    label: Dict[str, str] = {}
    depth: Dict[str, int] = {}
    value = defaultdict(int)

    for segs in segs_list:
        segs = [s for s in segs if s not in (None, "", "nan")]
        if not segs:
            continue
        for i in range(1, len(segs) + 1):
            nid = "/".join(segs[:i])
            pid = "/".join(segs[:i - 1]) if i > 1 else ""
            parent[nid] = pid
            label[nid] = segs[i - 1]
            depth[nid] = i
        # 葉にカウントを足す
        value["/".join(segs)] += 1

    # 子の値を親に集約（branchvalues="total" 用）
    for nid in sorted(depth.keys(), key=lambda k: depth[k], reverse=True):
        pid = parent.get(nid, "")
        if pid:
            value[pid] += value[nid]

    rows = []
    for nid in depth.keys():
        rows.append(
            {
                "id": nid,
                "parent": parent.get(nid, ""),
                "label": label.get(nid, nid.split("/")[-1]),
                "value": int(value.get(nid, 0)),
                "depth": int(depth.get(nid, 1)),
            }
        )
    out = pd.DataFrame(rows)
    # value=0 の孤立ノードは落とす（ノイズ低減）
    out = out[out["value"] > 0].copy()
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