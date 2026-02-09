# ファイルパス: C:\lib_ana\src\v6\core\hierarchy_v6.py
from __future__ import annotations
from dataclasses import dataclass
from typing import List, Tuple

@dataclass(frozen=True)
class HierarchySelection:
    levels: List[str]
    prefix: str

def split_segments(path: str) -> List[str]:
    return [p for p in (path or "").split(".") if p]

def build_options(module_paths: List[str], selected_levels: List[str]) -> Tuple[List[str], List[str]]:
    prefix = ".".join([s for s in selected_levels if s])
    if prefix:
        scoped = [m for m in module_paths if m.startswith(prefix + ".") or m == prefix]
    else:
        scoped = module_paths[:]

    next_segments = set()
    for m in scoped:
        segs = split_segments(m)
        if len(segs) <= len(selected_levels):
            continue
        next_segments.add(segs[len(selected_levels)])
    return sorted(next_segments), scoped

def auto_depth(
    module_paths: List[str],
    max_depth: int = 8,
    target_groups: int = 60,
    target_avg: int = 200,
    min_depth: int = 2,
) -> int:
    """モジュール階層の「ほどよい深さ」を推定する。

    旧版は「条件を満たした最初の深さ」で打ち切っていたため、
    timesfm のようにモジュール数が少ないケースで depth=1 になりやすかった。

    ここでは「条件を満たす範囲で、できるだけ深い depth」を返す。
    """
    n = len(module_paths)
    if n <= 0:
        return 1

    best = 1
    for depth in range(1, max_depth + 1):
        groups: dict[str, int] = {}
        for m in module_paths:
            segs = split_segments(m)
            key = ".".join(segs[:depth])
            groups[key] = groups.get(key, 0) + 1
        g = len(groups)
        avg = int(round(n / max(g, 1)))
        if g <= target_groups and avg <= target_avg:
            best = depth

    best = max(best, min_depth)
    return min(best, max_depth)
