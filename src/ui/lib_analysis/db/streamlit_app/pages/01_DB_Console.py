from __future__ import annotations

import sys
import time
from datetime import datetime
from pathlib import Path

import streamlit as st

APP_DIR = Path(__file__).resolve().parents[1]  # .../streamlit_app
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from bootstrap import ensure_import_path
ensure_import_path()

from ui.lib_analysis.db.streamlit_app.common import sidebar_profile_selector, make_client, connection_test
from ui.lib_analysis.db.streamlit_app.ui_utils import human_bytes

from ui.lib_analysis.db.core.client import DbError
from ui.lib_analysis.db.core.introspect import Introspector
from ui.lib_analysis.db.core.ops import DbOps, SafetyPolicy, UnsafeOperation
from ui.lib_analysis.db.core.audit import AuditLogger
from ui.lib_analysis.db.core.ddl import DdlExtractor, DumpConfig, DdlError

APP_ROOT = Path(__file__).resolve().parents[2]  # .../ui/lib_analysis/db
LOG_PATH = APP_ROOT / "logs" / f"db_admin_{datetime.now().strftime('%Y%m%d')}.jsonl"
audit = AuditLogger(LOG_PATH)

st.set_page_config(page_title="DB Console", layout="wide")
st.title("DB Console")
st.caption("概要表示 + DDL表示 + 安全な作成/削除")

profile, password = sidebar_profile_selector()
if st.sidebar.button("接続テスト"):
    connection_test(profile, password)

# DB一覧
client_default = make_client(profile, password, dbname=profile.default_db)
try:
    insp_default = Introspector(client_default)
    dbs = insp_default.list_databases()
except DbError as e:
    st.error(f"接続に失敗しました: {e}")
    st.stop()

colA, colB = st.columns([2, 3], gap="large")
with colA:
    st.subheader("対象選択")
    db = st.selectbox("Database", dbs, index=dbs.index(profile.default_db) if profile.default_db in dbs else 0)
    client_db = make_client(profile, password, dbname=db)
    insp = Introspector(client_db)

    try:
        schemas = insp.list_schemas()
    except DbError as e:
        st.error(f"スキーマ一覧取得に失敗: {e}")
        st.stop()

    schema = st.selectbox("Schema", schemas, index=schemas.index("public") if "public" in schemas else 0)

    try:
        tables = insp.list_tables(schema)
    except DbError as e:
        st.error(f"テーブル一覧取得に失敗: {e}")
        tables = []

    table = st.selectbox("Table", ["(none)"] + tables, index=0)

    st.divider()
    st.subheader("操作（SQL生成→確認→実行）")

    destructive_allowed = profile.is_host_allowed() and profile.environment_label.upper() not in {"PROD", "PRODUCTION"}
    safety = SafetyPolicy(environment_label=profile.environment_label, allow_destructive=destructive_allowed)

    ops_db = DbOps(make_client(profile, password, dbname=profile.maintenance_db), safety=safety)
    ops_obj = DbOps(client_db, safety=safety)

    with st.expander("DB作成 / DB削除", expanded=False):
        c1, c2 = st.columns(2)
        with c1:
            st.markdown("#### CREATE DATABASE")
            new_db = st.text_input("新DB名", key="new_db_name")
            owner = st.text_input("OWNER（任意）", key="new_db_owner")
            if st.button("SQL生成（CREATE DATABASE）"):
                try:
                    sql = ops_db.sql_create_database(new_db, owner or None)
                    st.session_state["pending_sql"] = sql
                    st.session_state["pending_target"] = new_db
                    st.session_state["pending_action"] = "create_database"
                    st.success("SQL生成OK → 右の Apply タブで実行")
                except Exception as e:
                    st.error(str(e))

        with c2:
            st.markdown("#### DROP DATABASE")
            drop_db = st.text_input("削除DB名", key="drop_db_name")
            force = st.checkbox("WITH (FORCE)（対応バージョンのみ）", key="drop_db_force")
            if st.button("SQL生成（DROP DATABASE）"):
                try:
                    sql = ops_db.sql_drop_database(drop_db, force=bool(force))
                    st.session_state["pending_sql"] = sql
                    st.session_state["pending_target"] = drop_db
                    st.session_state["pending_action"] = "drop_database"
                    st.success("SQL生成OK → 右の Apply タブで実行")
                except Exception as e:
                    st.error(str(e))

    with st.expander("スキーマ作成 / スキーマ削除", expanded=False):
        c1, c2 = st.columns(2)
        with c1:
            st.markdown("#### CREATE SCHEMA")
            new_schema = st.text_input("新スキーマ名", key="new_schema_name")
            if st.button("SQL生成（CREATE SCHEMA）"):
                try:
                    sql = ops_obj.sql_create_schema(new_schema)
                    st.session_state["pending_sql"] = sql
                    st.session_state["pending_target"] = new_schema
                    st.session_state["pending_action"] = "create_schema"
                    st.success("SQL生成OK → 右の Apply タブで実行")
                except Exception as e:
                    st.error(str(e))
        with c2:
            st.markdown("#### DROP SCHEMA")
            drop_schema = st.text_input("削除スキーマ名", key="drop_schema_name")
            cascade = st.checkbox("CASCADE", key="drop_schema_cascade")
            if st.button("SQL生成（DROP SCHEMA）"):
                try:
                    sql = ops_obj.sql_drop_schema(drop_schema, cascade=bool(cascade))
                    st.session_state["pending_sql"] = sql
                    st.session_state["pending_target"] = drop_schema
                    st.session_state["pending_action"] = "drop_schema"
                    st.success("SQL生成OK → 右の Apply タブで実行")
                except Exception as e:
                    st.error(str(e))

    with st.expander("テーブル作成 / テーブル削除", expanded=False):
        c1, c2 = st.columns(2)
        with c1:
            st.markdown("#### CREATE TABLE（自由記述DDL）")
            ddl_sql = st.text_area("DDL（CREATE TABLE ...）", height=140, key="create_table_ddl")
            if st.button("SQL設定（CREATE TABLE）"):
                if ddl_sql.strip():
                    st.session_state["pending_sql"] = ddl_sql.strip()
                    st.session_state["pending_target"] = "(custom ddl)"
                    st.session_state["pending_action"] = "create_table"
                    st.success("DDLセット → 右の Apply タブで実行")
                else:
                    st.error("DDLが空です。")
        with c2:
            st.markdown("#### DROP TABLE")
            drop_table = st.selectbox("削除テーブル", ["(select)"] + tables, key="drop_table_name")
            cascade = st.checkbox("CASCADE", key="drop_table_cascade")
            if st.button("SQL生成（DROP TABLE）"):
                try:
                    if drop_table == "(select)":
                        raise ValueError("削除テーブルを選択してください。")
                    sql = ops_obj.sql_drop_table(schema, drop_table, cascade=bool(cascade))
                    st.session_state["pending_sql"] = sql
                    st.session_state["pending_target"] = f"{schema}.{drop_table}"
                    st.session_state["pending_action"] = "drop_table"
                    st.success("SQL生成OK → 右の Apply タブで実行")
                except Exception as e:
                    st.error(str(e))

with colB:
    tab_over, tab_ddl, tab_apply = st.tabs(["Overview", "DDL", "Apply（確認→実行）"])

    with tab_over:
        st.subheader("概要")
        if table != "(none)":
            try:
                ov = insp.get_table_overview(schema, table)
                st.markdown(f"### {schema}.{table}")
                size = ov.get("size_bytes", {})
                if size:
                    st.write({
                        "total": human_bytes(size.get("total_bytes", 0)),
                        "table": human_bytes(size.get("table_bytes", 0)),
                        "index": human_bytes(size.get("index_bytes", 0)),
                    })
                st.markdown("#### Columns")
                st.dataframe(ov.get("columns", []), use_container_width=True)
                st.markdown("#### Constraints")
                st.dataframe(ov.get("constraints", []), use_container_width=True)
                st.markdown("#### Indexes")
                st.dataframe(ov.get("indexes", []), use_container_width=True)
                st.markdown("#### Stats（推定/統計）")
                st.json(ov.get("stats", {}))
            except DbError as e:
                st.error(f"概要取得に失敗: {e}")
        else:
            st.info("左でテーブルを選択してください。")

    with tab_ddl:
        st.subheader("DDL（pg_dump）")
        dump_scope = st.radio("範囲", ["schema", "table"], horizontal=True)
        if st.button("DDL取得（pg_dump）"):
            try:
                cfg = DumpConfig(
                    host=profile.host,
                    port=profile.port,
                    user=profile.user,
                    password=password,
                    dbname=db,
                    pg_dump_bin=None,
                )
                ex = DdlExtractor(cfg)
                if dump_scope == "schema":
                    ddl = ex.dump_schema_only(schema=schema)
                else:
                    if table == "(none)":
                        st.warning("テーブルを選択してください。")
                        ddl = ""
                    else:
                        ddl = ex.dump_schema_only(schema=schema, table=table)
                if ddl:
                    st.code(ddl, language="sql")
                    st.download_button("DDLをダウンロード（.sql）", data=ddl, file_name=f"{db}_{schema}_{dump_scope}.sql")
            except DdlError as e:
                st.error(f"DDL取得に失敗: {e}")
            except Exception as e:
                st.error(str(e))

    with tab_apply:
        st.subheader("実行（確認フロー）")
        pending_sql = st.session_state.get("pending_sql")
        pending_target = st.session_state.get("pending_target")
        pending_action = st.session_state.get("pending_action")

        if not pending_sql:
            st.info("左の操作パネルで SQL を生成してください。")
        else:
            st.markdown("#### 実行予定SQL（Dry-run）")
            st.code(pending_sql, language="sql")
            st.warning("対象名のタイピング確認が必須です。")
            confirm_text = st.text_input("対象名を正確に入力", key="confirm_text")
            ack = st.checkbox("内容を理解し、実行の影響を受け入れます", key="confirm_ack")

            can_apply = bool(ack and confirm_text and pending_target and (confirm_text == str(pending_target) or pending_target == "(custom ddl)"))
            apply = st.button("Apply（実行）", disabled=not can_apply)

            if apply:
                t0 = time.time()
                status = "ok"
                err = None
                try:
                    if pending_action in {"create_database", "drop_database"}:
                        ops_db.client.execute_ddl(pending_sql)
                    elif pending_action in {"create_schema", "drop_schema", "create_table", "drop_table"}:
                        ops_obj.client.execute_ddl(pending_sql)
                    else:
                        raise UnsafeOperation(f"不明な action: {pending_action}")
                    st.success("実行しました。")
                except (DbError, UnsafeOperation) as e:
                    status = "ng"
                    err = str(e)
                    st.error(f"失敗: {err}")
                finally:
                    elapsed = int((time.time() - t0) * 1000)
                    audit.log(
                        action=str(pending_action),
                        target=str(pending_target),
                        sql=str(pending_sql),
                        status=status,
                        profile=profile.name,
                        error=err,
                        elapsed_ms=elapsed,
                        meta={"db": db, "schema": schema, "table": table},
                    )
                    st.session_state.pop("pending_sql", None)
                    st.session_state.pop("pending_target", None)
                    st.session_state.pop("pending_action", None)
