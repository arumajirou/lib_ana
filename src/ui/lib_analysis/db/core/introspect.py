from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from .client import PgClient

@dataclass(frozen=True)
class TableRef:
    schema: str
    table: str

    @property
    def fqtn(self) -> str:
        return f"{self.schema}.{self.table}"

class Introspector:
    def __init__(self, client: PgClient):
        self.client = client

    def list_databases(self) -> List[str]:
        rows = self.client.execute(
            """SELECT datname
                 FROM pg_database
                 WHERE datistemplate = false
                 ORDER BY 1;"""
        )
        return [r["datname"] for r in rows]

    def list_schemas(self) -> List[str]:
        rows = self.client.execute(
            """SELECT nspname
                 FROM pg_namespace
                 WHERE nspname NOT LIKE 'pg_%'
                   AND nspname <> 'information_schema'
                 ORDER BY 1;"""
        )
        return [r["nspname"] for r in rows]

    def list_tables(self, schema: str) -> List[str]:
        rows = self.client.execute(
            """SELECT tablename
                 FROM pg_tables
                 WHERE schemaname = %s
                 ORDER BY 1;""",
            (schema,),
        )
        return [r["tablename"] for r in rows]

    def get_columns(self, schema: str, table: str) -> List[Dict[str, Any]]:
        rows = self.client.execute(
            """SELECT
                    ordinal_position,
                    column_name,
                    data_type,
                    is_nullable,
                    column_default
                FROM information_schema.columns
                WHERE table_schema = %s AND table_name = %s
                ORDER BY ordinal_position;""",
            (schema, table),
        )
        return rows

    def get_constraints(self, schema: str, table: str) -> List[Dict[str, Any]]:
        rows = self.client.execute(
            """SELECT
                    con.conname AS name,
                    con.contype AS type,
                    pg_get_constraintdef(con.oid) AS definition
                FROM pg_constraint con
                JOIN pg_class rel ON rel.oid = con.conrelid
                JOIN pg_namespace nsp ON nsp.oid = rel.relnamespace
                WHERE nsp.nspname = %s AND rel.relname = %s
                ORDER BY con.contype, con.conname;""",
            (schema, table),
        )
        return rows

    def get_indexes(self, schema: str, table: str) -> List[Dict[str, Any]]:
        rows = self.client.execute(
            """SELECT
                    idx.indexname,
                    idx.indexdef
                FROM pg_indexes idx
                WHERE idx.schemaname = %s AND idx.tablename = %s
                ORDER BY idx.indexname;""",
            (schema, table),
        )
        return rows

    def get_stats(self, schema: str, table: str) -> Dict[str, Any]:
        rows = self.client.execute(
            """SELECT
                    schemaname,
                    relname,
                    seq_scan,
                    idx_scan,
                    n_tup_ins,
                    n_tup_upd,
                    n_tup_del,
                    n_live_tup,
                    n_dead_tup,
                    last_vacuum,
                    last_autovacuum,
                    last_analyze,
                    last_autoanalyze
                FROM pg_stat_user_tables
                WHERE schemaname = %s AND relname = %s;""",
            (schema, table),
        )
        return rows[0] if rows else {}

    def get_size_bytes(self, schema: str, table: str) -> Dict[str, int]:
        rows = self.client.execute(
            """SELECT
                    pg_total_relation_size(format('%I.%I', %s, %s)) AS total_bytes,
                    pg_relation_size(format('%I.%I', %s, %s)) AS table_bytes,
                    pg_indexes_size(format('%I.%I', %s, %s)) AS index_bytes;""",
            (schema, table, schema, table, schema, table),
        )
        if not rows:
            return {"total_bytes": 0, "table_bytes": 0, "index_bytes": 0}
        r = rows[0]
        return {k: int(r[k]) for k in ["total_bytes", "table_bytes", "index_bytes"]}

    def get_fk_edges(self, schema: Optional[str] = None) -> List[Dict[str, Any]]:
        sql = """WITH fk AS (
                SELECT
                    con.oid AS con_oid,
                    con.conname AS fk_name,
                    con.conrelid AS child_oid,
                    con.confrelid AS parent_oid,
                    con.conkey AS child_keys,
                    con.confkey AS parent_keys
                FROM pg_constraint con
                WHERE con.contype = 'f'
            ),
            rels AS (
                SELECT
                    c_child.oid AS child_oid,
                    n_child.nspname AS child_schema,
                    c_child.relname AS child_table,
                    c_parent.oid AS parent_oid,
                    n_parent.nspname AS parent_schema,
                    c_parent.relname AS parent_table,
                    fk.fk_name,
                    fk.child_keys,
                    fk.parent_keys
                FROM fk
                JOIN pg_class c_child ON c_child.oid = fk.child_oid
                JOIN pg_namespace n_child ON n_child.oid = c_child.relnamespace
                JOIN pg_class c_parent ON c_parent.oid = fk.parent_oid
                JOIN pg_namespace n_parent ON n_parent.oid = c_parent.relnamespace
            )
            SELECT
                child_schema, child_table, parent_schema, parent_table, fk_name,
                child_keys, parent_keys
            FROM rels
            WHERE (%s IS NULL OR child_schema = %s OR parent_schema = %s)
            ORDER BY child_schema, child_table, fk_name;"""
        return self.client.execute(sql, (schema, schema, schema))

    def get_table_overview(self, schema: str, table: str) -> Dict[str, Any]:
        return {
            "columns": self.get_columns(schema, table),
            "constraints": self.get_constraints(schema, table),
            "indexes": self.get_indexes(schema, table),
            "stats": self.get_stats(schema, table),
            "size_bytes": self.get_size_bytes(schema, table),
        }

    def top_tables_by_size(self, schema: str, limit: int = 20) -> List[Dict[str, Any]]:
        rows = self.client.execute(
            """SELECT
                    schemaname,
                    relname,
                    pg_total_relation_size(format('%I.%I', schemaname, relname)) AS total_bytes
                FROM pg_stat_user_tables
                WHERE schemaname = %s
                ORDER BY total_bytes DESC
                LIMIT %s;""",
            (schema, limit),
        )
        for r in rows:
            r["total_bytes"] = int(r["total_bytes"])
        return rows

    def top_tables_by_updates(self, schema: str, limit: int = 20) -> List[Dict[str, Any]]:
        rows = self.client.execute(
            """SELECT
                    schemaname,
                    relname,
                    (n_tup_ins + n_tup_upd + n_tup_del) AS writes
                FROM pg_stat_user_tables
                WHERE schemaname = %s
                ORDER BY writes DESC
                LIMIT %s;""",
            (schema, limit),
        )
        for r in rows:
            r["writes"] = int(r["writes"])
        return rows
