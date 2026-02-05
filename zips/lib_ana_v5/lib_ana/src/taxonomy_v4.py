# ファイルパス: C:\lib_ana\src\taxonomy_v4.py
# （この実行環境では /mnt/data/taxonomy_v4.py に生成しています）
from __future__ import annotations

import re
from typing import List


# “イベント(操作)分類”の簡易タクソノミー（taxonomy: 分類体系）
# ※ 完全自動分類は必ず誤差が出るので、ヒューリスティック(経験則) + UIで修正できる前提が現実的です。
EVENT_RULES = [
    ("load",   [r"\bload\b", r"\bread\b", r"\bfrom_\w+\b", r"open", r"import"]),
    ("save",   [r"\bsave\b", r"\bwrite\b", r"export", r"dump", r"serialize"]),
    ("config", [r"config", r"setting", r"args", r"param", r"option"]),
    ("build",  [r"build", r"create", r"make", r"init", r"construct"]),
    ("train",  [r"\btrain\b", r"\bfit\b", r"optimi", r"backprop", r"loss"]),
    ("predict",[r"\bpredict\b", r"\bforecast\b", r"\binfer\b", r"\bgenerate\b"]),
    ("eval",   [r"\beval\b", r"\bscore\b", r"\bmetric\b", r"validate", r"test"]),
    ("transform",[r"\btransform\b", r"\bpreprocess\b", r"\bencode\b", r"\btokenize\b", r"\bscale\b"]),
    ("plot",   [r"plot", r"visual", r"chart", r"draw", r"render"]),
    ("io",     [r"\bio\b", r"path", r"file", r"dir", r"stream", r"download", r"upload"]),
    ("util",   [r"util", r"helper", r"common", r"misc"]),
]


def classify_events(name: str, doc: str = "") -> List[str]:
    s = f"{name} {doc}".lower()
    tags = []
    for tag, pats in EVENT_RULES:
        for p in pats:
            if re.search(p, s):
                tags.append(tag)
                break
    return tags or ["other"]
