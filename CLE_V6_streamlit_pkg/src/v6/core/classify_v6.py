# ファイルパス: C:\lib_ana\src\v6\core\classify_v6.py
from __future__ import annotations
import re
from typing import List, Tuple
import pandas as pd

_ROLE_RULES: List[Tuple[str, str]] = [
    (r"\b(load|read|open|parse|decode|fetch|download)\b", "io_read"),
    (r"\b(save|dump|write|export|encode|upload)\b", "io_write"),
    (r"\b(plot|heatmap|bar|chart|draw|render|viz|visual)\b", "visualize"),
    (r"\b(train|fit|learn|optimi[sz]e|tune)\b", "model_fit"),
    (r"\b(eval|evaluate|score|metric|benchmark)\b", "evaluate"),
    (r"\b(sample|sampler|random|seed|bootstrap)\b", "sampling"),
    (r"\b(analy[sz]e|analysis|sobol|morris|pawn|rsa|dgsm|hdmr)\b", "analysis"),
    (r"\b(cli|command|args|main)\b", "cli"),
    (r"\b(test|mock|fixture)\b", "test"),
]

_EVENT_RULES = [
    r"\bon_[a-z0-9_]+\b",
    r"\b(before|after)_[a-z0-9_]+\b",
    r"\b(callback|hook|listener|signal|event)\b",
    r"\b(handler)\b",
]

def _split_tokens(s: str) -> List[str]:
    s = s or ""
    s = s.replace(".", "_")
    s = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", s)
    parts = re.split(r"[^a-zA-Z0-9]+", s)
    return [p.lower() for p in parts if p]

def infer_role(path_or_name: str) -> str:
    toks = _split_tokens(path_or_name)
    joined = " ".join(toks)
    for pat, role in _ROLE_RULES:
        if re.search(pat, joined):
            return role
    return "other"

def infer_event_like(path_or_name: str) -> bool:
    s = (path_or_name or "").lower()
    return any(re.search(p, s) for p in _EVENT_RULES)

def _normalize_name(name: str) -> str:
    toks = _split_tokens(name)
    toks = [t for t in toks if len(t) >= 2]
    return "_".join(toks)

def _cluster_by_similarity(norm_names: List[str], threshold: int = 92) -> List[int]:
    try:
        from rapidfuzz import fuzz
        scorer = lambda a, b: fuzz.ratio(a, b)
    except Exception:
        import difflib
        scorer = lambda a, b: int(difflib.SequenceMatcher(None, a, b).ratio() * 100)

    n = len(norm_names)
    parent = list(range(n))

    def find(x: int) -> int:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a: int, b: int) -> None:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[rb] = ra

    for i in range(n):
        for j in range(i + 1, n):
            if not norm_names[i] or not norm_names[j]:
                continue
            if scorer(norm_names[i], norm_names[j]) >= threshold:
                union(i, j)

    roots = {}
    cluster_ids = []
    next_id = 0
    for i in range(n):
        r = find(i)
        if r not in roots:
            roots[r] = next_id
            next_id += 1
        cluster_ids.append(roots[r])
    return cluster_ids

def enrich_with_classification(df_nodes: pd.DataFrame) -> pd.DataFrame:
    if df_nodes is None or df_nodes.empty:
        return df_nodes
    df = df_nodes.copy()
    src = [str(row.get("Path") or row.get("Name") or "") for _, row in df.iterrows()]
    df["Role"] = [infer_role(s) for s in src]
    df["EventLike"] = [infer_event_like(s) for s in src]
    df["NormName"] = [_normalize_name(str(row.get("Name") or "")) for _, row in df.iterrows()]

    cluster_ids = [-1] * len(df)
    if "Type" in df.columns:
        for t in sorted(df["Type"].dropna().unique()):
            idx = df.index[df["Type"] == t].tolist()
            names = [df.loc[i, "NormName"] for i in idx]
            ids = _cluster_by_similarity(names, threshold=92)
            for k, i in enumerate(idx):
                cluster_ids[df.index.get_loc(i)] = ids[k]
        df["NameCluster"] = cluster_ids
    else:
        df["NameCluster"] = _cluster_by_similarity(df["NormName"].tolist(), threshold=92)

    def top_group(path: str) -> str:
        parts = (path or "").split(".")
        return ".".join(parts[:2]) if len(parts) >= 2 else (parts[0] if parts else "")

    if "Path" in df.columns:
        df["TopGroup"] = [top_group(str(p)) for p in df["Path"].astype(str).tolist()]
    else:
        df["TopGroup"] = ""
    return df
