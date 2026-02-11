from __future__ import annotations
from dataclasses import replace
from pathlib import Path
from typing import Optional, Tuple, List

import streamlit as st

from ui.lib_analysis.db.core.config import load_profiles, get_password, mask, ConnectionProfile
from ui.lib_analysis.db.core.client import PgClient, PgConnInfo, DbError

DEFAULT_PROFILES_PATH = str(Path(__file__).resolve().parents[1] / "configs" / "db_admin_profiles.example.json")

def load_profiles_cached(path: str) -> List[ConnectionProfile]:
    @st.cache_data(ttl=60)
    def _load(p: str):
        return load_profiles(p)
    return _load(path)

def sidebar_profile_selector() -> Tuple[ConnectionProfile, str]:
    st.sidebar.header("接続")
    profiles_path = st.sidebar.text_input("profiles.json のパス", value=DEFAULT_PROFILES_PATH)
    profiles = load_profiles_cached(profiles_path)
    if not profiles:
        st.sidebar.error("profiles が空です。json を確認してください。")
        st.stop()

    names = [p.name for p in profiles]
    name = st.sidebar.selectbox("プロファイル", names, index=0)
    prof = next(p for p in profiles if p.name == name)

    with st.sidebar.expander("接続情報を一時変更", expanded=False):
        override_on = st.checkbox(
            "一時変更を有効化",
            value=bool(st.session_state.get(f"conn_override_on::{name}", False)),
            key=f"conn_override_on::{name}",
        )
        o_host = st.text_input("host", value=str(st.session_state.get(f"conn_override_host::{name}", prof.host)), key=f"conn_override_host::{name}")
        o_port = st.number_input(
            "port",
            min_value=1,
            max_value=65535,
            value=int(st.session_state.get(f"conn_override_port::{name}", int(prof.port))),
            step=1,
            key=f"conn_override_port::{name}",
        )
        o_user = st.text_input("user", value=str(st.session_state.get(f"conn_override_user::{name}", prof.user)), key=f"conn_override_user::{name}")
        o_default_db = st.text_input(
            "default_db",
            value=str(st.session_state.get(f"conn_override_default_db::{name}", prof.default_db)),
            key=f"conn_override_default_db::{name}",
        )

    if st.session_state.get(f"conn_override_on::{name}", False):
        prof = replace(
            prof,
            host=str(st.session_state.get(f"conn_override_host::{name}", prof.host)).strip() or prof.host,
            port=int(st.session_state.get(f"conn_override_port::{name}", int(prof.port))),
            user=str(st.session_state.get(f"conn_override_user::{name}", prof.user)).strip() or prof.user,
            default_db=str(st.session_state.get(f"conn_override_default_db::{name}", prof.default_db)).strip() or prof.default_db,
        )

    password = get_password(prof.name) or ""
    st.sidebar.caption(f"env: {prof.environment_label} | host={prof.host}:{prof.port} | user={prof.user}")
    st.sidebar.caption(f"password: {mask(password) if password else '(not set)'}")

    destructive_allowed = prof.is_host_allowed() and prof.environment_label.upper() not in {"PROD", "PRODUCTION"}
    if not destructive_allowed:
        st.sidebar.warning("この接続は破壊操作が無効です（allow_hosts / env_label を確認）")

    return prof, password

def make_client(profile: ConnectionProfile, password: str, dbname: Optional[str] = None) -> PgClient:
    info = PgConnInfo(
        host=profile.host,
        port=profile.port,
        user=profile.user,
        password=password,
        dbname=dbname or profile.default_db,
        connect_timeout_sec=profile.connect_timeout_sec,
    )
    return PgClient(info)

def connection_test(profile: ConnectionProfile, password: str) -> None:
    client = make_client(profile, password, dbname=profile.default_db)
    try:
        ver = client.server_version()
        st.success(f"接続OK / server_version={ver[0]}.{ver[1]}")
    except DbError as e:
        st.error(f"接続NG: {e}")
