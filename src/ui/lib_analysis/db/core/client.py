from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence, Tuple

_PSYCO = None
_PSYCO2 = None
try:
    import psycopg  # type: ignore
    _PSYCO = psycopg
except Exception:
    _PSYCO = None

try:
    import psycopg2  # type: ignore
    import psycopg2.extras  # type: ignore
    _PSYCO2 = psycopg2
except Exception:
    _PSYCO2 = None

class DbError(RuntimeError):
    pass

@dataclass
class PgConnInfo:
    host: str
    port: int
    user: str
    password: Optional[str]
    dbname: str
    connect_timeout_sec: int = 5

def _format_error(e: Exception) -> str:
    msg = str(e)
    return msg if msg else e.__class__.__name__

class PgClient:
    """PostgreSQL 最小クライアント（psycopg3/psycopg2 自動切替）。"""

    def __init__(self, conn_info: PgConnInfo):
        self.conn_info = conn_info

    def _dsn(self) -> str:
        pw = self.conn_info.password or ""
        return (
            f"host={self.conn_info.host} port={self.conn_info.port} "
            f"user={self.conn_info.user} password={pw} dbname={self.conn_info.dbname} "
            f"connect_timeout={self.conn_info.connect_timeout_sec}"
        )

    def server_version(self) -> Tuple[int, int]:
        rows = self.execute("SHOW server_version_num;")
        if not rows:
            return (0, 0)
        n = int(rows[0].get("server_version_num", 0))
        return (n // 10000, (n % 10000) // 100)

    def execute(self, sql: str, params: Optional[Sequence[Any]] = None) -> List[Dict[str, Any]]:
        try:
            if _PSYCO is not None:
                with _PSYCO.connect(self._dsn()) as conn:
                    with conn.cursor() as cur:
                        cur.execute(sql, params or ())
                        if cur.description is None:
                            return []
                        cols = [c.name for c in cur.description]
                        rows = cur.fetchall()
                        return [dict(zip(cols, r)) for r in rows]

            if _PSYCO2 is not None:
                with _PSYCO2.connect(self._dsn()) as conn:
                    with conn.cursor(cursor_factory=_PSYCO2.extras.RealDictCursor) as cur:
                        cur.execute(sql, params or ())
                        if cur.description is None:
                            return []
                        return list(cur.fetchall())

            raise DbError("psycopg/psycopg2 が見つかりません。requirements を確認してください。")

        except Exception as e:
            raise DbError(_format_error(e)) from e

    def execute_ddl(self, sql: str, params: Optional[Sequence[Any]] = None) -> None:
        """DDL は autocommit が必要なケースがあるため分離。"""
        try:
            if _PSYCO is not None:
                conn = _PSYCO.connect(self._dsn(), autocommit=True)
                try:
                    with conn.cursor() as cur:
                        cur.execute(sql, params or ())
                finally:
                    conn.close()
                return

            if _PSYCO2 is not None:
                conn = _PSYCO2.connect(self._dsn())
                try:
                    conn.autocommit = True
                    with conn.cursor() as cur:
                        cur.execute(sql, params or ())
                finally:
                    conn.close()
                return

            raise DbError("psycopg/psycopg2 が見つかりません。requirements を確認してください。")

        except Exception as e:
            raise DbError(_format_error(e)) from e
