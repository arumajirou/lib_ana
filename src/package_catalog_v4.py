# ファイルパス: C:\lib_ana\src\package_catalog_v4.py
# （この実行環境では /mnt/data/package_catalog_v4.py に生成しています）
from __future__ import annotations

from dataclasses import dataclass
from typing import List

import importlib.metadata


@dataclass(frozen=True)
class PackageItem:
    import_name: str          # importできる名前（例: chronos）
    dist_name: str            # pip表示の配布名（例: chronos-forecasting）
    version: str


def _top_levels_for_dist(dist: importlib.metadata.Distribution) -> List[str]:
    try:
        txt = dist.read_text("top_level.txt")
        if txt:
            names = [x.strip() for x in txt.splitlines() if x.strip() and not x.startswith("#")]
            return names
    except Exception:
        pass
    return []


def build_package_catalog(max_items: int = 2000) -> List[PackageItem]:
    items: List[PackageItem] = []
    for dist in importlib.metadata.distributions():
        try:
            dist_name = dist.metadata.get("Name", "") or ""
            version = dist.version or ""
        except Exception:
            continue

        tops = _top_levels_for_dist(dist)
        if not tops:
            guess = (dist_name or "").replace("-", "_")
            tops = [guess] if guess else []

        for t in tops:
            if len(items) >= max_items:
                break
            items.append(PackageItem(import_name=t, dist_name=dist_name, version=version))

    # dedupe by import_name
    seen = set()
    uniq: List[PackageItem] = []
    for it in sorted(items, key=lambda x: (x.import_name.lower(), len(x.dist_name))):
        k = it.import_name.lower()
        if k in seen:
            continue
        seen.add(k)
        uniq.append(it)
    return uniq
