from __future__ import annotations

from dataclasses import dataclass, field
from typing import List


@dataclass
class ParamInfo:
    """関数/メソッドの 1 引数情報."""

    name: str
    kind: str
    annotation: str
    has_default: bool
    default_repr: str


@dataclass
class ValueCandidate:
    """引数に与える値候補."""

    code: str
    description: str = ""
    score: float = 0.5
    setup_lines: List[str] = field(default_factory=list)


def suggest_values_for_param(param: ParamInfo) -> List[ValueCandidate]:
    """ParamInfo から素朴な値候補を推定する."""
    ann = (param.annotation or "").lower()
    name = param.name.lower()
    cands: List[ValueCandidate] = []

    # 1. デフォルト値がある場合は最有力候補
    if param.has_default and param.default_repr not in ("<empty>", ""):
        cands.append(
            ValueCandidate(
                code=param.default_repr,
                description="default value from signature",
                score=0.9,
                setup_lines=[],
            )
        )

    # 2. ブール値
    if "bool" in ann or name.startswith("is_") or name.startswith("has_"):
        cands.append(ValueCandidate(code="True", description="boolean True", score=0.7))
        cands.append(ValueCandidate(code="False", description="boolean False", score=0.7))

    # 3. 数値っぽいもの
    if "int" in ann or "float" in ann or name in {"n", "k", "num", "count", "size", "epochs", "steps"}:
        cands.append(ValueCandidate(code="0", description="zero", score=0.6))
        cands.append(ValueCandidate(code="1", description="one", score=0.6))

    # 4. 文字列 / パス
    if "str" in ann or "path" in name or "file" in name:
        cands.append(ValueCandidate(code="'./sample.csv'", description="path string", score=0.6))
        cands.append(ValueCandidate(code="'example'", description="simple string", score=0.5))

    # 5. pandas.DataFrame
    if "dataframe" in ann or name in {"df", "frame", "data", "dataset"}:
        setup = [
            "import pandas as pd",
            "df = pd.DataFrame({'col1': [1, 2, 3], 'col2': [10, 20, 30]})",
        ]
        cands.append(
            ValueCandidate(
                code="df",
                description="sample pandas DataFrame",
                score=0.8,
                setup_lines=setup,
            )
        )

    # 6. numpy.ndarray
    if "ndarray" in ann or "array" in name:
        setup = [
            "import numpy as np",
            "x = np.array([0.0, 1.0, 2.0])",
        ]
        cands.append(
            ValueCandidate(
                code="x",
                description="sample numpy array",
                score=0.8,
                setup_lines=setup,
            )
        )

    # 7. フォールバック None
    cands.append(ValueCandidate(code="None", description="placeholder", score=0.3))

    # code ごとに統合
    uniq: dict[str, ValueCandidate] = {}
    for c in cands:
        if c.code not in uniq:
            uniq[c.code] = c
        else:
            existing = uniq[c.code]
            if c.score > existing.score:
                existing.score = c.score
                if c.description:
                    existing.description = c.description
            merged = list(dict.fromkeys(existing.setup_lines + c.setup_lines))
            existing.setup_lines = merged

    return list(uniq.values())
