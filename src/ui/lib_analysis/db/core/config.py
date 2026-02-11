from __future__ import annotations
import json, os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional

try:
    import streamlit as st  # type: ignore
except Exception:  # pragma: no cover
    st = None

@dataclass(frozen=True)
class ConnectionProfile:
    name: str
    host: str = "127.0.0.1"
    port: int = 5432
    user: str = "postgres"
    default_db: str = "postgres"
    maintenance_db: str = "postgres"
    environment_label: str = "LOCAL"  # LOCAL/DEV/STG/PROD
    allow_hosts: list[str] = None  # type: ignore
    connect_timeout_sec: int = 5

    def is_host_allowed(self) -> bool:
        allow = self.allow_hosts or ["127.0.0.1", "localhost"]
        return self.host in allow

def _read_json(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)

def load_profiles(json_path: str) -> list[ConnectionProfile]:
    p = Path(json_path)
    data = _read_json(p)
    profiles = []
    for item in data.get("profiles", []):
        profiles.append(ConnectionProfile(
            name=item["name"],
            host=item.get("host", "127.0.0.1"),
            port=int(item.get("port", 5432)),
            user=item.get("user", "postgres"),
            default_db=item.get("default_db", "postgres"),
            maintenance_db=item.get("maintenance_db", "postgres"),
            environment_label=item.get("environment_label", "LOCAL"),
            allow_hosts=item.get("allow_hosts", ["127.0.0.1", "localhost"]),
            connect_timeout_sec=int(item.get("connect_timeout_sec", 5)),
        ))
    return profiles

def get_password(profile_name: str, secret_key_prefix: str = "DB_ADMIN_") -> Optional[str]:
    """パスワードを secrets / 環境変数から取得する。"""
    if st is not None:
        try:
            key = f"{secret_key_prefix}{profile_name}".upper()
            if key in st.secrets:
                return str(st.secrets[key])
        except Exception:
            pass
    env_key = f"{secret_key_prefix}{profile_name}".upper()
    return os.environ.get(env_key)

def mask(s: str, show_last: int = 2) -> str:
    if not s:
        return ""
    if len(s) <= show_last:
        return "*" * len(s)
    return "*" * (len(s) - show_last) + s[-show_last:]
