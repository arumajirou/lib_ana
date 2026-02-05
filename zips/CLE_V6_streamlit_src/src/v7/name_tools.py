# ファイルパス: C:\lib_ana\src\v6\name_tools.py
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Dict, List, Tuple

_CAMEL_RE = re.compile(r"([a-z0-9])([A-Z])")
_NONWORD_RE = re.compile(r"[^A-Za-z0-9]+")

@dataclass(frozen=True)
class NameFeatures:
    raw: str
    parts_dot: List[str]
    tokens: List[str]
    stem: str
    keywords: List[str]
    category: str

def split_camel(s: str) -> str:
    return _CAMEL_RE.sub(r"\1_\2", s)

def tokenize(name: str) -> List[str]:
    s = split_camel(name)
    s = s.replace(".", "_")
    s = _NONWORD_RE.sub("_", s)
    toks = [t.lower() for t in s.split("_") if t]
    return toks

def build_keywords(tokens: List[str]) -> List[str]:
    # “分類に効く”短い語（heuristic）
    stop = {"a","an","the","of","to","and","or","in","on","for","with","by","from"}
    out = [t for t in tokens if t not in stop and len(t) >= 2]
    return out[:20]

def categorize(path_or_name: str) -> str:
    # 近似カテゴリ（モジュール/関数名の文字列から推定）
    s = path_or_name.lower()
    rules = [
        ("plot", "plot/visualization"),
        ("visual", "plot/visualization"),
        ("graph", "plot/visualization"),
        ("chart", "plot/visualization"),
        ("sample", "sampling"),
        ("sampler", "sampling"),
        ("analy", "analysis"),
        ("metric", "analysis"),
        ("loss", "analysis"),
        ("test", "tests"),
        ("cli", "cli/scripts"),
        ("script", "cli/scripts"),
        ("util", "utils"),
        ("helper", "utils"),
        ("io", "io"),
        ("export", "export"),
        ("dataset", "data"),
        ("data", "data"),
        ("train", "training"),
        ("fit", "training"),
        ("predict", "inference"),
        ("infer", "inference"),
        ("callback", "events/hooks"),
        ("handler", "events/hooks"),
        ("event", "events/hooks"),
    ]
    for key, cat in rules:
        if key in s:
            return cat
    return "other"

def extract_features(path_or_name: str) -> NameFeatures:
    parts_dot = [p for p in (path_or_name or "").split(".") if p]
    toks = tokenize(path_or_name or "")
    kws = build_keywords(toks)
    stem = "_".join(kws[:4]) if kws else (toks[0] if toks else "")
    cat = categorize(path_or_name or "")
    return NameFeatures(
        raw=path_or_name or "",
        parts_dot=parts_dot,
        tokens=toks,
        stem=stem,
        keywords=kws,
        category=cat,
    )

def group_key(module_path: str, depth: int = 2) -> str:
    parts = (module_path or "").split(".")
    if len(parts) <= depth:
        return ".".join(parts)
    return ".".join(parts[:depth])

def nearest_names(query: str, candidates: List[str], k: int = 12) -> List[Tuple[str, float]]:
    # difflib で近さ（0..1）
    import difflib
    q = (query or "").strip().lower()
    if not q:
        return []
    scored = []
    for c in candidates:
        r = difflib.SequenceMatcher(a=q, b=(c or "").lower()).ratio()
        if r > 0.35:
            scored.append((c, r))
    scored.sort(key=lambda x: x[1], reverse=True)
    return scored[:k]
