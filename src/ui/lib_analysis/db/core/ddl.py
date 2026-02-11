from __future__ import annotations
import os
import subprocess
from dataclasses import dataclass
from typing import Optional

from .runtime import find_pg_binaries

class DdlError(RuntimeError):
    pass

@dataclass(frozen=True)
class DumpConfig:
    host: str
    port: int
    user: str
    password: Optional[str]
    dbname: str
    pg_dump_bin: Optional[str] = None

class DdlExtractor:
    """pg_dump で schema-only のDDLを抽出する（正確性優先）。"""

    def __init__(self, dump_cfg: DumpConfig):
        self.cfg = dump_cfg
        bins = find_pg_binaries(pg_dump_win=None)
        self.pg_dump = self.cfg.pg_dump_bin or bins.pg_dump
        if not self.pg_dump:
            raise DdlError("pg_dump が見つかりません（PATH または設定を確認）。")

    def dump_schema_only(self, schema: Optional[str] = None, table: Optional[str] = None) -> str:
        cmd = [
            self.pg_dump,
            "--schema-only",
            "--no-owner",
            "--no-privileges",
            "-h", self.cfg.host,
            "-p", str(self.cfg.port),
            "-U", self.cfg.user,
            self.cfg.dbname,
        ]
        if schema:
            cmd += ["-n", schema]
        if table:
            if schema and "." not in table:
                cmd += ["-t", f"{schema}.{table}"]
            else:
                cmd += ["-t", table]

        env = dict(os.environ)
        if self.cfg.password:
            env["PGPASSWORD"] = self.cfg.password

        p = subprocess.run(
            cmd,
            env=env,
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        if p.returncode != 0:
            raise DdlError(p.stderr.strip() or "pg_dump failed")
        return p.stdout
