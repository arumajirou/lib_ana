from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import pandas as pd

from .config import DbConfig


def _safe_ident(value: str) -> str:
    if not value.replace("_", "").isalnum():
        raise ValueError(f"unsafe identifier: {value}")
    return value


@dataclass
class TimesFmDatasetRepository:
    """Repository for fetching TimesFM verification datasets from PostgreSQL."""

    config: DbConfig

    def _connect(self):
        try:
            import psycopg

            return psycopg.connect(self.config.to_dsn())
        except ImportError:
            import psycopg2

            return psycopg2.connect(self.config.to_dsn())

    def load_target_series(self, limit: Optional[int] = None) -> pd.DataFrame:
        schema = _safe_ident(self.config.schema)
        table = _safe_ident(self.config.y_table)
        lim = f"LIMIT {int(limit)}" if limit is not None else ""
        sql = f"""
            SELECT unique_id, ds, y
            FROM {schema}.{table}
            ORDER BY unique_id, ds
            {lim}
        """
        with self._connect() as conn:
            return pd.read_sql_query(sql, conn)

    def load_hist_features(self, limit: Optional[int] = None) -> pd.DataFrame:
        schema = _safe_ident(self.config.schema)
        table = _safe_ident(self.config.feat_table)
        lim = f"LIMIT {int(limit)}" if limit is not None else ""
        sql = f"""
            SELECT *
            FROM {schema}.{table}
            ORDER BY unique_id, ds
            {lim}
        """
        with self._connect() as conn:
            return pd.read_sql_query(sql, conn)
