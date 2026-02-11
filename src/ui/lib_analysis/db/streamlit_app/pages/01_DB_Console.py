from __future__ import annotations

import sys
import time
from datetime import datetime
import csv
import io
import json
import html
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
OUTPUT_DIR = APP_ROOT / "output"
audit = AuditLogger(LOG_PATH)

st.set_page_config(page_title="DB Console", layout="wide")
st.title("DB Console")
st.caption("概要表示 + DDL表示 + 安全な作成/削除")
st.markdown(
    """
<style>
.db-chip {
  display: inline-block;
  padding: 4px 10px;
  border-radius: 999px;
  background: #f8fafc;
  color: #0f172a;
  font-size: 0.8rem;
  border: 1px solid #e2e8f0;
  margin-right: 6px;
}
.db-kpi {
  background: #0f172a;
  color: #e2e8f0;
  padding: 12px 14px;
  border-radius: 12px;
  border: 1px solid #1e293b;
}
.db-kpi .label {
  font-size: 0.72rem;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: #94a3b8;
  margin-bottom: 6px;
}
.db-kpi .value {
  font-size: 1.25rem;
  font-weight: 600;
  line-height: 1.3;
}
.db-tag {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 4px 10px;
  margin: 4px 6px 0 0;
  border-radius: 10px;
  background: #0b1220;
  color: #e2e8f0;
  border: 1px solid #1e293b;
  font-size: 0.8rem;
  max-width: 100%;
}
.db-tag.num { border-color: #0ea5e9; color: #e0f2fe; }
.db-tag.num .freq { background: #0b4f6b; color: #bae6fd; }
.db-tag.dt { border-color: #22c55e; color: #dcfce7; }
.db-tag.dt .freq { background: #14532d; color: #bbf7d0; }
.db-tag.text { border-color: #f97316; color: #ffedd5; }
.db-tag.text .freq { background: #7c2d12; color: #fed7aa; }
.db-tag.bool { border-color: #a855f7; color: #f3e8ff; }
.db-tag.bool .freq { background: #5b21b6; color: #e9d5ff; }
.db-tag.other { border-color: #64748b; color: #e2e8f0; }
.db-tag.other .freq { background: #1f2937; color: #cbd5f5; }
.db-tag .freq {
  padding: 1px 6px;
  border-radius: 999px;
  background: #1f2937;
  color: #93c5fd;
  font-size: 0.72rem;
  white-space: nowrap;
}
.db-muted {
  color: #94a3b8;
  font-size: 0.8rem;
}
.db-subtle {
  color: #94a3b8;
  font-size: 0.8rem;
  margin-top: 4px;
}
.db-card {
  background: linear-gradient(135deg, #0b1220 0%, #111827 100%);
  border: 1px solid #1f2937;
  border-radius: 14px;
  padding: 14px 16px;
}
.db-card h4 {
  margin: 0 0 6px 0;
  color: #e2e8f0;
  font-size: 0.95rem;
}
.db-card pre {
  margin: 0;
  color: #94a3b8;
  font-size: 0.8rem;
}
</style>
""",
    unsafe_allow_html=True,
)


def _json_default(o):
    if isinstance(o, (datetime, Path)):
        return str(o)
    return str(o)


def _build_export_payload(
    *,
    profile_name: str,
    db: str,
    schema: str,
    selected_tables: list[str],
    insp: Introspector,
    include_sample: bool,
    sample_limit: int,
) -> dict:
    payload: dict = {
        "meta": {
            "profile": profile_name,
            "database": db,
            "schema": schema,
            "selected_tables": selected_tables,
            "generated_at": datetime.now().isoformat(),
            "include_sample": bool(include_sample),
            "sample_limit": int(sample_limit),
        },
        "fk_edges_schema": [],
        "tables": [],
        "errors": [],
    }

    try:
        fk_rows = insp.get_fk_edges(schema)
    except Exception as e:
        fk_rows = []
        payload["errors"].append({"scope": "fk_edges", "error": str(e)})
    payload["fk_edges_schema"] = fk_rows

    for t in selected_tables:
        rec = {"table": t}
        try:
            ov = insp.get_table_overview(schema, t)
            rec["overview"] = ov
            if include_sample:
                rec["sample_rows"] = insp.get_table_sample(schema, t, limit=int(sample_limit))
        except Exception as e:
            rec["error"] = str(e)
            payload["errors"].append({"scope": f"{schema}.{t}", "error": str(e)})
        payload["tables"].append(rec)
    return payload


def _payload_to_markdown(payload: dict) -> str:
    meta = payload.get("meta", {})
    lines: list[str] = []
    lines.append("# DB Table Analysis Report")
    lines.append("")
    lines.append("## Meta")
    lines.append(f"- profile: {meta.get('profile')}")
    lines.append(f"- database: {meta.get('database')}")
    lines.append(f"- schema: {meta.get('schema')}")
    lines.append(f"- generated_at: {meta.get('generated_at')}")
    lines.append(f"- selected_tables: {', '.join(meta.get('selected_tables', []))}")
    lines.append("")
    lines.append("## FK Edges (schema)")
    lines.append("```json")
    lines.append(json.dumps(payload.get("fk_edges_schema", []), ensure_ascii=False, indent=2, default=_json_default))
    lines.append("```")
    lines.append("")
    lines.append("## Tables")
    for rec in payload.get("tables", []):
        tbl = rec.get("table")
        lines.append(f"### {meta.get('schema')}.{tbl}")
        if rec.get("error"):
            lines.append(f"- error: {rec.get('error')}")
            lines.append("")
            continue
        lines.append("#### overview")
        lines.append("```json")
        lines.append(json.dumps(rec.get("overview", {}), ensure_ascii=False, indent=2, default=_json_default))
        lines.append("```")
        if "sample_rows" in rec:
            lines.append("#### sample_rows")
            lines.append("```json")
            lines.append(json.dumps(rec.get("sample_rows", []), ensure_ascii=False, indent=2, default=_json_default))
            lines.append("```")
        lines.append("")

    if payload.get("errors"):
        lines.append("## Errors")
        lines.append("```json")
        lines.append(json.dumps(payload.get("errors", []), ensure_ascii=False, indent=2, default=_json_default))
        lines.append("```")
    return "\n".join(lines)


def _payload_to_html(payload: dict) -> str:
    meta = payload.get("meta", {})
    parts: list[str] = []
    parts.append("<h1>DB Table Analysis Report</h1>")
    parts.append("<h2>Meta</h2>")
    parts.append("<pre>" + html.escape(json.dumps(meta, ensure_ascii=False, indent=2, default=_json_default)) + "</pre>")
    parts.append("<h2>FK Edges (schema)</h2>")
    parts.append("<pre>" + html.escape(json.dumps(payload.get("fk_edges_schema", []), ensure_ascii=False, indent=2, default=_json_default)) + "</pre>")
    parts.append("<h2>Tables</h2>")
    for rec in payload.get("tables", []):
        tbl = rec.get("table")
        parts.append(f"<h3>{html.escape(str(meta.get('schema')))}.{html.escape(str(tbl))}</h3>")
        if rec.get("error"):
            parts.append(f"<p><b>error:</b> {html.escape(str(rec.get('error')))}</p>")
            continue
        parts.append("<h4>overview</h4>")
        parts.append("<pre>" + html.escape(json.dumps(rec.get("overview", {}), ensure_ascii=False, indent=2, default=_json_default)) + "</pre>")
        if "sample_rows" in rec:
            parts.append("<h4>sample_rows</h4>")
            parts.append("<pre>" + html.escape(json.dumps(rec.get("sample_rows", []), ensure_ascii=False, indent=2, default=_json_default)) + "</pre>")

    if payload.get("errors"):
        parts.append("<h2>Errors</h2>")
        parts.append("<pre>" + html.escape(json.dumps(payload.get("errors", []), ensure_ascii=False, indent=2, default=_json_default)) + "</pre>")

    body = "\n".join(parts)
    return f"""<!doctype html>
<html lang="ja">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>DB Table Analysis Report</title>
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; margin: 20px; line-height: 1.4; }}
    pre {{ background: #f7f7f7; border: 1px solid #ddd; padding: 10px; white-space: pre-wrap; }}
  </style>
</head>
<body>
{body}
</body>
</html>
"""

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

    # Keep the last selected table per db/schema and auto-select a real table when possible.
    table_state_key = f"selected_table::{db}::{schema}"
    prev_table = st.session_state.get(table_state_key)
    table_options = tables if tables else ["(none)"]

    if tables:
        default_table_index = table_options.index(prev_table) if prev_table in table_options else 0
    else:
        default_table_index = 0

    table = st.selectbox("Table", table_options, index=default_table_index)
    if table != "(none)":
        st.session_state[table_state_key] = table

    # 削除操作用: DB -> Schema -> Table のカスケード選択
    st.divider()
    st.subheader("削除対象カスケード選択")
    drop_target_db = st.selectbox("削除対象DB", dbs, index=dbs.index(db) if db in dbs else 0, key="drop_target_db")
    insp_drop = Introspector(make_client(profile, password, dbname=drop_target_db))
    try:
        drop_schemas = insp_drop.list_schemas()
    except DbError as e:
        st.error(f"削除対象スキーマ一覧取得に失敗: {e}")
        drop_schemas = []

    drop_target_schema = st.selectbox(
        "削除対象スキーマ",
        drop_schemas if drop_schemas else ["(none)"],
        index=(drop_schemas.index("public") if "public" in drop_schemas else 0) if drop_schemas else 0,
        key="drop_target_schema",
    )

    if drop_schemas and drop_target_schema != "(none)":
        try:
            drop_tables = insp_drop.list_tables(drop_target_schema)
        except DbError as e:
            st.error(f"削除対象テーブル一覧取得に失敗: {e}")
            drop_tables = []
    else:
        drop_tables = []

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
            drop_db = st.selectbox("削除DB名", ["(select)"] + dbs, key="drop_db_name")
            force = st.checkbox("WITH (FORCE)（対応バージョンのみ）", key="drop_db_force")
            if st.button("SQL生成（DROP DATABASE）"):
                try:
                    if drop_db == "(select)":
                        raise ValueError("削除DB名を選択してください。")
                    sql = ops_db.sql_drop_database(drop_db, force=bool(force))
                    st.session_state["pending_sql"] = sql
                    st.session_state["pending_target"] = drop_db
                    st.session_state["pending_action"] = "drop_database"
                    st.session_state["pending_exec_db"] = None
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
                    st.session_state["pending_exec_db"] = db
                    st.success("SQL生成OK → 右の Apply タブで実行")
                except Exception as e:
                    st.error(str(e))
        with c2:
            st.markdown("#### DROP SCHEMA")
            drop_schema = st.selectbox(
                "削除スキーマ名",
                ["(select)"] + drop_schemas if drop_schemas else ["(select)"],
                key="drop_schema_name",
            )
            cascade = st.checkbox("CASCADE", key="drop_schema_cascade")
            if st.button("SQL生成（DROP SCHEMA）"):
                try:
                    if drop_schema == "(select)":
                        raise ValueError("削除スキーマ名を選択してください。")
                    sql = ops_obj.sql_drop_schema(drop_schema, cascade=bool(cascade))
                    st.session_state["pending_sql"] = sql
                    st.session_state["pending_target"] = f"{drop_target_db}.{drop_schema}"
                    st.session_state["pending_action"] = "drop_schema"
                    st.session_state["pending_exec_db"] = drop_target_db
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
                    st.session_state["pending_exec_db"] = db
                    st.success("DDLセット → 右の Apply タブで実行")
                else:
                    st.error("DDLが空です。")
        with c2:
            st.markdown("#### DROP TABLE")
            drop_table = st.selectbox("削除テーブル", ["(select)"] + drop_tables, key="drop_table_name")
            cascade = st.checkbox("CASCADE", key="drop_table_cascade")
            if st.button("SQL生成（DROP TABLE）"):
                try:
                    if drop_target_schema == "(none)":
                        raise ValueError("削除対象スキーマを選択してください。")
                    if drop_table == "(select)":
                        raise ValueError("削除テーブルを選択してください。")
                    sql = ops_obj.sql_drop_table(drop_target_schema, drop_table, cascade=bool(cascade))
                    st.session_state["pending_sql"] = sql
                    st.session_state["pending_target"] = f"{drop_target_db}.{drop_target_schema}.{drop_table}"
                    st.session_state["pending_action"] = "drop_table"
                    st.session_state["pending_exec_db"] = drop_target_db
                    st.success("SQL生成OK → 右の Apply タブで実行")
                except Exception as e:
                    st.error(str(e))

with colB:
    tab_over, tab_ddl, tab_apply, tab_export = st.tabs(["Overview", "DDL", "Apply（確認→実行）", "Export"])

    with tab_over:
        def _parse_pg_array(val):
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

        def _parse_pg_float_array(val):
            items = _parse_pg_array(val)
            out = []
            for it in items:
                try:
                    out.append(float(it))
                except Exception:
                    out.append(None)
            return out

        st.subheader("概要")
        if table != "(none)":
            try:
                ov = insp.get_table_overview(schema, table)
                st.markdown(
                    f"""
<div>
  <span class="db-chip">DB: {db}</span>
  <span class="db-chip">Schema: {schema}</span>
  <span class="db-chip">Table: {table}</span>
</div>
""",
                    unsafe_allow_html=True,
                )

                conn_info = {
                    "profile": profile.name,
                    "env": profile.environment_label,
                    "host": profile.host,
                    "port": profile.port,
                    "user": profile.user,
                    "database": db,
                    "schema": schema,
                    "table": table,
                }
                conn_block = "\n".join([f"{k}: {v}" for k, v in conn_info.items()])
                cinfo1, cinfo2 = st.columns([2, 1])
                with cinfo1:
                    st.markdown(
                        f"""
<div class="db-card">
  <h4>Connection info (copy)</h4>
  <pre>{conn_block}</pre>
</div>
""",
                        unsafe_allow_html=True,
                    )
                    st.code(conn_block, language="text")
                with cinfo2:
                    st.markdown("#### Table info")
                    table_info = {
                        "db": db,
                        "schema": schema,
                        "table": table,
                        "fqtn": f"{schema}.{table}",
                    }
                    table_block = "\n".join([f"{k}: {v}" for k, v in table_info.items()])
                    if st.button("テーブル情報をコピー用に表示"):
                        st.session_state["table_info_copy"] = table_block
                    if st.session_state.get("table_info_copy"):
                        st.code(st.session_state["table_info_copy"], language="text")
                        st.caption("上のコードブロックのコピーを使用してください。")

                size = ov.get("size_bytes", {})
                if size:
                    k1, k2, k3 = st.columns(3)
                    k1.markdown(
                        f"""
<div class="db-kpi">
  <div class="label">Total Size</div>
  <div class="value">{human_bytes(size.get("total_bytes", 0))}</div>
</div>
""",
                        unsafe_allow_html=True,
                    )
                    k2.markdown(
                        f"""
<div class="db-kpi">
  <div class="label">Table Size</div>
  <div class="value">{human_bytes(size.get("table_bytes", 0))}</div>
</div>
""",
                        unsafe_allow_html=True,
                    )
                    k3.markdown(
                        f"""
<div class="db-kpi">
  <div class="label">Index Size</div>
  <div class="value">{human_bytes(size.get("index_bytes", 0))}</div>
</div>
""",
                        unsafe_allow_html=True,
                    )

                tabs = st.tabs(["Columns", "Constraints", "Indexes", "Stats", "Sample rows", "df.info"])
                with tabs[0]:
                    cols = ov.get("columns", [])
                    col_stats = {c.get("column_name"): c for c in ov.get("column_stats", [])}
                    stats = ov.get("stats", {})
                    est_rows = stats.get("n_live_tup")
                    enriched = []
                    for c in cols:
                        name = c.get("column_name")
                        st_row = col_stats.get(name, {})
                        null_frac = st_row.get("null_frac")
                        n_distinct = st_row.get("n_distinct")
                        if n_distinct is None:
                            distinct_est = None
                        elif isinstance(n_distinct, (int, float)) and n_distinct < 0 and est_rows:
                            distinct_est = int(abs(n_distinct) * int(est_rows))
                        else:
                            distinct_est = int(n_distinct) if isinstance(n_distinct, (int, float)) else n_distinct
                        enriched.append(
                            {
                                "column_name": name,
                                "data_type": c.get("data_type"),
                                "is_nullable": c.get("is_nullable"),
                                "column_default": c.get("column_default"),
                                "null_%": round(float(null_frac) * 100, 2) if null_frac is not None else None,
                                "distinct_est": distinct_est,
                            }
                        )
                    st.caption(f"Columns: {len(cols)}")
                    st.dataframe(enriched, width="stretch", hide_index=True)

                    st.markdown("#### Unique values (est.)")
                    assist = st.checkbox(
                        "補助モード: 低カーディナリティ時に実データで DISTINCT を取得",
                        value=False,
                        key="distinct_assist",
                    )
                    distinct_limit = st.slider("DISTINCT 取得上限", 5, 200, 50, 5, key="distinct_limit")
                    if not cols:
                        st.info("カラムがありません。")
                    else:
                        for c in cols:
                            name = c.get("column_name")
                            st_row = col_stats.get(name, {})
                            null_frac = st_row.get("null_frac")
                            n_distinct = st_row.get("n_distinct")
                            most_vals = _parse_pg_array(st_row.get("most_common_vals"))
                            most_freqs = _parse_pg_float_array(st_row.get("most_common_freqs"))
                            data_type = str(c.get("data_type") or "").lower()

                            if n_distinct is None:
                                distinct_est = "n/a"
                            elif isinstance(n_distinct, (int, float)) and n_distinct < 0 and est_rows:
                                distinct_est = str(int(abs(n_distinct) * int(est_rows)))
                            else:
                                distinct_est = str(int(n_distinct)) if isinstance(n_distinct, (int, float)) else str(n_distinct)

                            null_pct = f"{round(float(null_frac) * 100, 2)}%" if null_frac is not None else "n/a"

                            with st.expander(f"{name}  ·  distinct_est={distinct_est}  ·  null={null_pct}", expanded=False):
                                if data_type in {"integer", "bigint", "smallint", "numeric", "real", "double precision", "decimal"}:
                                    tag_class = "num"
                                elif "timestamp" in data_type or "date" in data_type or "time" in data_type:
                                    tag_class = "dt"
                                elif data_type in {"boolean", "bool"}:
                                    tag_class = "bool"
                                elif "char" in data_type or "text" in data_type or "uuid" in data_type:
                                    tag_class = "text"
                                else:
                                    tag_class = "other"

                                display_vals = []
                                display_source = ""
                                if most_vals:
                                    chips = []
                                    freq_iter = most_freqs if most_freqs else [None] * len(most_vals)
                                    for v, f in zip(most_vals, freq_iter):
                                        val = str(v)
                                        if len(val) > 60:
                                            val = val[:57] + "..."
                                        freq = f"{round(float(f) * 100, 2)}%" if f is not None else ""
                                        chips.append(
                                            f'<span class="db-tag {tag_class}">{val}<span class="freq">{freq}</span></span>'
                                        )
                                        display_vals.append(str(v))
                                    st.markdown("".join(chips), unsafe_allow_html=True)
                                    st.markdown('<div class="db-muted">Most common values (pg_stats)</div>', unsafe_allow_html=True)
                                    display_source = "pg_stats.most_common_vals"
                                else:
                                    did_assist = False
                                    if assist and distinct_est != "n/a":
                                        try:
                                            if int(distinct_est) <= int(distinct_limit):
                                                rows = insp.get_distinct_values(schema, table, name, limit=int(distinct_limit))
                                                if rows:
                                                    chips = []
                                                    for r in rows:
                                                        val = str(r.get("value"))
                                                        if len(val) > 60:
                                                            val = val[:57] + "..."
                                                        chips.append(
                                                            f'<span class="db-tag {tag_class}">{val}<span class="freq">distinct</span></span>'
                                                        )
                                                        display_vals.append(str(r.get("value")))
                                                    st.markdown("".join(chips), unsafe_allow_html=True)
                                                    st.markdown('<div class="db-muted">Distinct values (live query)</div>', unsafe_allow_html=True)
                                                    did_assist = True
                                                    display_source = "SELECT DISTINCT (live)"
                                        except Exception:
                                            did_assist = False
                                    if not did_assist:
                                        st.info("pg_stats に most_common_vals がありません。ANALYZE で更新してください。")

                                if display_vals:
                                    st.markdown("#### Copy list")
                                    fmt = st.selectbox(
                                        "形式",
                                        ["text", "csv", "json"],
                                        index=0,
                                        key=f"copy_fmt::{schema}::{table}::{name}",
                                    )
                                    if fmt == "json":
                                        payload = json.dumps(display_vals, ensure_ascii=False, indent=2)
                                    elif fmt == "csv":
                                        buf = io.StringIO()
                                        writer = csv.writer(buf)
                                        for v in display_vals:
                                            writer.writerow([v])
                                        payload = buf.getvalue()
                                    else:
                                        payload = "\n".join(display_vals)
                                    st.caption(f"source: {display_source}")
                                    st.code(payload, language="text")
                with tabs[1]:
                    constraints = ov.get("constraints", [])
                    st.caption(f"Constraints: {len(constraints)}")
                    st.dataframe(constraints, width="stretch", hide_index=True)
                with tabs[2]:
                    indexes = ov.get("indexes", [])
                    st.caption(f"Indexes: {len(indexes)}")
                    st.dataframe(indexes, width="stretch", hide_index=True)
                with tabs[3]:
                    stats = ov.get("stats", {})
                    if stats:
                        m1, m2, m3, m4 = st.columns(4)
                        writes = (stats.get("n_tup_ins", 0) or 0) + (stats.get("n_tup_upd", 0) or 0) + (stats.get("n_tup_del", 0) or 0)
                        m1.markdown(
                            f"""
<div class="db-kpi">
  <div class="label">Live Tuples</div>
  <div class="value">{stats.get("n_live_tup", 0)}</div>
</div>
""",
                            unsafe_allow_html=True,
                        )
                        m2.markdown(
                            f"""
<div class="db-kpi">
  <div class="label">Dead Tuples</div>
  <div class="value">{stats.get("n_dead_tup", 0)}</div>
</div>
""",
                            unsafe_allow_html=True,
                        )
                        m3.markdown(
                            f"""
<div class="db-kpi">
  <div class="label">Seq Scans</div>
  <div class="value">{stats.get("seq_scan", 0)}</div>
</div>
""",
                            unsafe_allow_html=True,
                        )
                        m4.markdown(
                            f"""
<div class="db-kpi">
  <div class="label">Index Scans</div>
  <div class="value">{stats.get("idx_scan", 0)}</div>
</div>
""",
                            unsafe_allow_html=True,
                        )
                        st.markdown(
                            f"""
<div class="db-subtle">
Writes (ins+upd+del): {writes} /
Last vacuum: {stats.get("last_vacuum")} /
Last analyze: {stats.get("last_analyze")}
</div>
""",
                            unsafe_allow_html=True,
                        )
                        st.dataframe(
                            [{"key": k, "value": v} for k, v in stats.items()],
                            width="stretch",
                            hide_index=True,
                        )
                    else:
                        st.info("統計情報がありません。")
                with tabs[4]:
                    sample_limit = st.selectbox("表示件数", [10, 50, 100, 200, 500], index=2, key="sample_limit")
                    sample_rows = insp.get_table_sample(schema, table, limit=int(sample_limit))
                    if sample_rows:
                        st.dataframe(sample_rows, width="stretch", hide_index=True)
                    else:
                        st.info("表示できる行がありません。")
                with tabs[5]:
                    cols = ov.get("columns", [])
                    col_stats = {c.get("column_name"): c for c in ov.get("column_stats", [])}
                    stats = ov.get("stats", {})
                    est_rows = stats.get("n_live_tup")
                    info_rows = []
                    for c in cols:
                        name = c.get("column_name")
                        st_row = col_stats.get(name, {})
                        null_frac = st_row.get("null_frac")
                        n_distinct = st_row.get("n_distinct")
                        if n_distinct is None:
                            distinct_est = None
                        elif isinstance(n_distinct, (int, float)) and n_distinct < 0 and est_rows:
                            distinct_est = int(abs(n_distinct) * int(est_rows))
                        else:
                            distinct_est = int(n_distinct) if isinstance(n_distinct, (int, float)) else n_distinct
                        non_null_est = int((1 - float(null_frac)) * int(est_rows)) if null_frac is not None and est_rows is not None else None
                        info_rows.append(
                            {
                                "column": name,
                                "dtype": c.get("data_type"),
                                "non_null_est": non_null_est,
                                "null_%": round(float(null_frac) * 100, 2) if null_frac is not None else None,
                                "distinct_est": distinct_est,
                                "default": c.get("column_default"),
                            }
                        )
                    st.caption("df.info 相当（推定値: pg_stats + pg_stat_user_tables）")
                    st.dataframe(info_rows, width="stretch", hide_index=True)
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
        pending_exec_db = st.session_state.get("pending_exec_db")

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
                        exec_db = str(pending_exec_db) if pending_exec_db else db
                        DbOps(make_client(profile, password, dbname=exec_db), safety=safety).client.execute_ddl(pending_sql)
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
                        meta={"db": db, "schema": schema, "table": table, "exec_db": pending_exec_db},
                    )
                    st.session_state.pop("pending_sql", None)
                    st.session_state.pop("pending_target", None)
                    st.session_state.pop("pending_action", None)
                    st.session_state.pop("pending_exec_db", None)

    with tab_export:
        st.subheader("解析結果エクスポート")
        st.caption("選択したテーブルの解析情報をまとめてファイル出力します。")

        if not tables:
            st.info("このスキーマにテーブルがありません。")
        else:
            OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

            ck_prefix = f"export_ck::{db}::{schema}::"
            ctl1, ctl2 = st.columns([1, 1])
            with ctl1:
                if st.button("全選択", key=f"export_select_all::{db}::{schema}"):
                    for t in tables:
                        st.session_state[f"{ck_prefix}{t}"] = True
            with ctl2:
                if st.button("全解除", key=f"export_unselect_all::{db}::{schema}"):
                    for t in tables:
                        st.session_state[f"{ck_prefix}{t}"] = False

            st.markdown("#### テーブル選択（checkbox）")
            cols = st.columns(3)
            for i, t in enumerate(tables):
                with cols[i % 3]:
                    st.checkbox(t, key=f"{ck_prefix}{t}", value=bool(st.session_state.get(f"{ck_prefix}{t}", False)))

            selected_tables = [t for t in tables if bool(st.session_state.get(f"{ck_prefix}{t}", False))]
            st.caption(f"選択中: {len(selected_tables)} / {len(tables)}")

            fmt = st.selectbox("出力形式", ["json", "md", "html"], index=0, key=f"export_format::{db}::{schema}")
            include_sample = st.checkbox("sample rows を含める", value=True, key=f"export_include_sample::{db}::{schema}")
            sample_limit = st.selectbox("sample rows 件数", [10, 50, 100, 200], index=1, key=f"export_sample_limit::{db}::{schema}")

            if st.button("解析ファイルを生成して保存", type="primary", key=f"export_run::{db}::{schema}"):
                if not selected_tables:
                    st.warning("テーブルを1つ以上選択してください。")
                else:
                    with st.spinner("解析情報を収集中..."):
                        payload = _build_export_payload(
                            profile_name=profile.name,
                            db=db,
                            schema=schema,
                            selected_tables=selected_tables,
                            insp=insp,
                            include_sample=bool(include_sample),
                            sample_limit=int(sample_limit),
                        )

                    if fmt == "json":
                        content = json.dumps(payload, ensure_ascii=False, indent=2, default=_json_default)
                    elif fmt == "md":
                        content = _payload_to_markdown(payload)
                    else:
                        content = _payload_to_html(payload)

                    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                    safe_db = db.replace("/", "_").replace("\\", "_")
                    safe_schema = schema.replace("/", "_").replace("\\", "_")
                    out_name = f"{safe_db}_{safe_schema}_table_analysis_{ts}.{fmt}"
                    out_path = OUTPUT_DIR / out_name
                    out_path.write_text(content, encoding="utf-8")

                    st.session_state["export_last_content"] = content
                    st.session_state["export_last_file"] = str(out_path)
                    st.success(f"出力しました: {out_path}")

            last_content = st.session_state.get("export_last_content")
            last_file = st.session_state.get("export_last_file")
            if last_content and last_file:
                st.download_button(
                    "生成ファイルをダウンロード",
                    data=str(last_content),
                    file_name=Path(str(last_file)).name,
                    mime="text/plain",
                    key=f"export_download::{db}::{schema}",
                )
                st.caption(f"保存先: {last_file}")
