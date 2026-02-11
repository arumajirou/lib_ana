from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class DbConfig:
    """Database settings for TimesFM verification."""

    host: str = "127.0.0.1"
    port: int = 5432
    user: str = "loto"
    password: str = ""
    database: str = "loto"
    schema: str = "dataset"
    y_table: str = "loto_y_ts"
    feat_table: str = "loto_hist_feat"

    @classmethod
    def from_env(cls) -> "DbConfig":
        return cls(
            host=os.getenv("TIMESFM_DB_HOST", "127.0.0.1"),
            port=int(os.getenv("TIMESFM_DB_PORT", "5432")),
            user=os.getenv("TIMESFM_DB_USER", "loto"),
            password=os.getenv("TIMESFM_DB_PASSWORD", ""),
            database=os.getenv("TIMESFM_DB_NAME", "loto"),
            schema=os.getenv("TIMESFM_DB_SCHEMA", "dataset"),
            y_table=os.getenv("TIMESFM_DB_Y_TABLE", "loto_y_ts"),
            feat_table=os.getenv("TIMESFM_DB_FEAT_TABLE", "loto_hist_feat"),
        )

    def to_dsn(self) -> str:
        return (
            f"host={self.host} port={self.port} user={self.user} "
            f"dbname={self.database} password={self.password}"
        )
