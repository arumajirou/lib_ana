from __future__ import annotations
import re
from dataclasses import dataclass
from typing import Optional

from .client import PgClient

_IDENT_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")

class UnsafeOperation(RuntimeError):
    pass

def validate_ident(name: str, kind: str = "identifier") -> None:
    if not name or not _IDENT_RE.match(name):
        raise UnsafeOperation(f"{kind} が不正です: {name!r}")

@dataclass(frozen=True)
class SafetyPolicy:
    environment_label: str = "LOCAL"  # LOCAL/DEV/STG/PROD
    allow_destructive: bool = True

    def can_destruct(self) -> bool:
        if self.environment_label.upper() in {"PROD", "PRODUCTION"}:
            return False
        return bool(self.allow_destructive)

class DbOps:
    def __init__(self, client: PgClient, safety: SafetyPolicy):
        self.client = client
        self.safety = safety

    def sql_create_database(self, name: str, owner: Optional[str] = None) -> str:
        validate_ident(name, "database")
        if owner:
            validate_ident(owner, "owner")
            return f'CREATE DATABASE "{name}" OWNER "{owner}";'
        return f'CREATE DATABASE "{name}";'

    def sql_drop_database(self, name: str, force: bool = False) -> str:
        validate_ident(name, "database")
        if force:
            return f'DROP DATABASE "{name}" WITH (FORCE);'
        return f'DROP DATABASE "{name}";'

    def sql_create_schema(self, schema: str) -> str:
        validate_ident(schema, "schema")
        return f'CREATE SCHEMA "{schema}";'

    def sql_drop_schema(self, schema: str, cascade: bool = False) -> str:
        validate_ident(schema, "schema")
        return f'DROP SCHEMA "{schema}" {"CASCADE" if cascade else "RESTRICT"};'

    def sql_drop_table(self, schema: str, table: str, cascade: bool = False) -> str:
        validate_ident(schema, "schema")
        validate_ident(table, "table")
        return f'DROP TABLE "{schema}"."{table}" {"CASCADE" if cascade else "RESTRICT"};'

    def create_database(self, name: str, owner: Optional[str] = None) -> None:
        if not self.safety.can_destruct():
            raise UnsafeOperation("この環境では破壊操作が禁止されています。")
        self.client.execute_ddl(self.sql_create_database(name, owner))

    def drop_database(self, name: str, force: bool = False) -> None:
        if not self.safety.can_destruct():
            raise UnsafeOperation("この環境では破壊操作が禁止されています。")
        self.client.execute_ddl(self.sql_drop_database(name, force=force))

    def create_schema(self, schema: str) -> None:
        if not self.safety.can_destruct():
            raise UnsafeOperation("この環境では破壊操作が禁止されています。")
        self.client.execute_ddl(self.sql_create_schema(schema))

    def drop_schema(self, schema: str, cascade: bool = False) -> None:
        if not self.safety.can_destruct():
            raise UnsafeOperation("この環境では破壊操作が禁止されています。")
        self.client.execute_ddl(self.sql_drop_schema(schema, cascade=cascade))

    def drop_table(self, schema: str, table: str, cascade: bool = False) -> None:
        if not self.safety.can_destruct():
            raise UnsafeOperation("この環境では破壊操作が禁止されています。")
        self.client.execute_ddl(self.sql_drop_table(schema, table, cascade=cascade))

    def create_table_from_sql(self, ddl_sql: str) -> None:
        if not self.safety.can_destruct():
            raise UnsafeOperation("この環境では破壊操作が禁止されています。")
        self.client.execute_ddl(ddl_sql)
