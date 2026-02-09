# ファイルパス: C:\lib_ana\src\v6\core\semantic_index_v6.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from v6.core.search_v6 import build_documents_for_nodes

try:
    from sklearn.feature_extraction.text import TfidfVectorizer  # type: ignore
    from sklearn.metrics.pairwise import cosine_similarity  # type: ignore
except Exception:  # pragma: no cover
    TfidfVectorizer = None
    cosine_similarity = None


@dataclass
class SemanticIndex:
    vectorizer: Any
    matrix: Any
    meta: pd.DataFrame


def build_tfidf_index(
    nodes: pd.DataFrame,
    *,
    text_cols: Tuple[str, ...] = ("Path", "Name", "Docstring", "Module"),
    include_params: bool = True,
    max_features: int = 60000,
) -> Optional[SemanticIndex]:
    'TF-IDF(単語の重み付け)で軽量な意味検索インデックスを作る。'
    if nodes is None or nodes.empty:
        return None
    if TfidfVectorizer is None:
        return None

    docs, meta = build_documents_for_nodes(nodes, text_cols=text_cols, include_params=include_params)
    if not docs:
        return None

    # コード・英語・日本語が混ざる前提なので、文字n-gram(3-5)が頑健。
    vec = TfidfVectorizer(
        analyzer="char_wb",
        ngram_range=(3, 5),
        lowercase=True,
        max_features=max_features,
    )
    X = vec.fit_transform(docs)
    return SemanticIndex(vectorizer=vec, matrix=X, meta=meta)


def query_tfidf_index(
    index: SemanticIndex,
    query: str,
    *,
    top_k: int = 50,
) -> pd.DataFrame:
    'TF-IDFインデックスをクエリして上位を返す。'
    if index is None or not query or not str(query).strip():
        return pd.DataFrame()
    if cosine_similarity is None:
        return pd.DataFrame()

    q = str(query).strip()
    qv = index.vectorizer.transform([q])
    sims = cosine_similarity(qv, index.matrix).ravel()
    if sims.size == 0:
        return pd.DataFrame()

    k = min(int(top_k), int(sims.size))
    idx = np.argpartition(-sims, k - 1)[:k]
    idx = idx[np.argsort(-sims[idx])]
    df = index.meta.iloc[idx].copy()
    df["Score"] = sims[idx].astype(float)
    return df
