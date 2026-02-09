# ファイルパス: C:\lib_ana\src\v6\core\atlas_features_v6.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from v6.core.search_v6 import build_documents_for_nodes

try:
    from sklearn.cluster import MiniBatchKMeans  # type: ignore
    from sklearn.preprocessing import normalize  # type: ignore
except Exception:  # pragma: no cover
    MiniBatchKMeans = None
    normalize = None

try:
    from sklearn.feature_extraction.text import TfidfVectorizer  # type: ignore
except Exception:  # pragma: no cover
    TfidfVectorizer = None


def build_atlas_table(
    nodes: pd.DataFrame,
    *,
    include_types: Tuple[str, ...] = ("function", "method", "class", "external"),
) -> pd.DataFrame:
    'Atlas向けの基本テーブル（メトリクス）を作る。'
    if nodes is None or nodes.empty:
        return pd.DataFrame()

    df = nodes.copy()
    if "Type" in df.columns:
        df = df[df["Type"].astype(str).isin(set(include_types))].copy()

    # ParamCount
    if "Params" in df.columns:
        def _pc(p: Any) -> int:
            if p is None:
                return 0
            if isinstance(p, list):
                return int(len(p))
            if isinstance(p, dict):
                return int(len(p.keys()))
            return 0
        df["ParamCount"] = df["Params"].apply(_pc)
    else:
        df["ParamCount"] = 0

    # テキスト（クラスタや意味検索の共通土台）
    docs, meta = build_documents_for_nodes(df, include_params=True)
    meta = meta.copy()
    meta["_doc"] = docs
    return meta


def cluster_nodes_semantic(
    atlas_df: pd.DataFrame,
    *,
    n_clusters: int = 10,
    random_state: int = 42,
    max_features: int = 40000,
) -> Tuple[pd.DataFrame, Optional[Dict[int, List[str]]]]:
    'TF-IDFベクトルでクラスタリング（作業仮説としての“共通機能の塊”）。'
    if atlas_df is None or atlas_df.empty:
        return pd.DataFrame(), None
    if TfidfVectorizer is None or MiniBatchKMeans is None:
        out = atlas_df.copy()
        out["Cluster"] = -1
        return out, None

    docs = atlas_df["_doc"].astype(str).tolist() if "_doc" in atlas_df.columns else []
    if not docs:
        out = atlas_df.copy()
        out["Cluster"] = -1
        return out, None

    vec = TfidfVectorizer(
        analyzer="char_wb",
        ngram_range=(3, 5),
        lowercase=True,
        max_features=max_features,
    )
    X = vec.fit_transform(docs)

    # クラスタ数を現実的にクリップ
    n = X.shape[0]
    k = int(max(2, min(n_clusters, max(2, int(np.sqrt(n)))))) if n > 2 else 1
    if k <= 1:
        out = atlas_df.copy()
        out["Cluster"] = 0
        return out, None

    km = MiniBatchKMeans(n_clusters=k, random_state=random_state, batch_size=2048, n_init="auto")
    labels = km.fit_predict(X)

    out = atlas_df.copy()
    out["Cluster"] = labels.astype(int)

    # 各クラスタの代表語（文字n-gram）を上位で返す
    top_terms: Dict[int, List[str]] = {}
    try:
        centers = km.cluster_centers_
        # 文字n-gramなのでそのまま出すと読みにくいが、特徴の雰囲気が掴める
        terms = np.array(vec.get_feature_names_out())
        for cid in range(k):
            c = centers[cid]
            idx = np.argsort(-c)[:15]
            top_terms[int(cid)] = terms[idx].tolist()
    except Exception:
        top_terms = {}

    return out, top_terms
