from __future__ import annotations

import csv
import json
from dataclasses import asdict
from pathlib import Path
from typing import Any, Dict, List, Optional

from ui.lib_analysis.db.core.client import PgClient
from ui.lib_analysis.db.core.config import ConnectionProfile, load_profiles
from ui.lib_analysis.db.core.introspect import Introspector


def get_profile(profiles_path: str, name: str) -> ConnectionProfile:
    profiles = load_profiles(profiles_path)
    for p in profiles:
        if p.name == name:
            return p
    raise ValueError(f"profile not found: {name}")


def make_client(profile: ConnectionProfile, password: str, dbname: Optional[str] = None) -> PgClient:
    from ui.lib_analysis.db.core.client import PgConnInfo

    return PgClient(
        PgConnInfo(
            host=profile.host,
            port=int(profile.port),
            user=profile.user,
            password=password,
            dbname=dbname or profile.default_db,
            connect_timeout_sec=int(profile.connect_timeout_sec),
        )
    )


def get_introspector(profiles_path: str, profile_name: str, password: str, dbname: Optional[str] = None) -> Introspector:
    prof = get_profile(profiles_path, profile_name)
    client = make_client(prof, password, dbname=dbname)
    return Introspector(client)


def _parse_pg_array(val: Any) -> List[Any]:
    if val is None:
        return []
    if isinstance(val, (list, tuple)):
        return list(val)
    if isinstance(val, str):
        s = val.strip()
        if s.startswith("{") and s.endswith("}"):
            inner = s[1:-1]
            if inner == "":
                return []
            reader = csv.reader([inner], delimiter=",", quotechar='"', escapechar="\\")
            return next(reader, [])
        return [s]
    return [val]


def unique_values_from_stats(
    insp: Introspector,
    schema: str,
    table: str,
    column: str,
    *,
    assist_distinct: bool = False,
    distinct_limit: int = 50,
) -> Dict[str, Any]:
    stats = {r.get("column_name"): r for r in insp.get_column_stats(schema, table)}
    row = stats.get(column, {})
    most_vals = _parse_pg_array(row.get("most_common_vals"))
    if most_vals:
        return {
            "source": "pg_stats.most_common_vals",
            "values": [str(v) for v in most_vals],
        }
    if assist_distinct:
        rows = insp.get_distinct_values(schema, table, column, limit=int(distinct_limit))
        return {
            "source": "SELECT DISTINCT (live)",
            "values": [str(r.get("value")) for r in rows],
        }
    return {"source": "none", "values": []}


def connection_info(profile: ConnectionProfile, db: str, schema: str, table: str) -> Dict[str, Any]:
    info = asdict(profile)
    info.update({"database": db, "schema": schema, "table": table})
    return info


def dump_list(values: List[str], fmt: str = "text") -> str:
    if fmt == "json":
        return json.dumps(values, ensure_ascii=False, indent=2)
    if fmt == "csv":
        import io

        buf = io.StringIO()
        writer = csv.writer(buf)
        for v in values:
            writer.writerow([v])
        return buf.getvalue()
    return "\n".join(values)
