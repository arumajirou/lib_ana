from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

APP_DIR = Path(__file__).resolve().parents[1]  # .../streamlit_app
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from bootstrap import ensure_import_path
ensure_import_path()

from ui.lib_analysis.db.streamlit_app.common import sidebar_profile_selector, make_client, connection_test
from ui.lib_analysis.db.streamlit_app.ui_utils import human_bytes
from ui.lib_analysis.db.streamlit_app.components.mermaid_component import mermaid

from ui.lib_analysis.db.core.client import DbError
from ui.lib_analysis.db.core.introspect import Introspector
from ui.lib_analysis.db.core.graph import GraphBuilder
from ui.lib_analysis.db.core.render_mermaid import render_er_mermaid

st.set_page_config(page_title="DB Visualizer", layout="wide")
st.title("DB Visualizer")
st.caption("ER図（FKベース） + 統計（サイズ/更新）")

profile, password = sidebar_profile_selector()
if st.sidebar.button("接続テスト"):
    connection_test(profile, password)

client_default = make_client(profile, password, dbname=profile.default_db)
try:
    insp_default = Introspector(client_default)
    dbs = insp_default.list_databases()
except DbError as e:
    st.error(f"接続に失敗しました: {e}")
    st.stop()

db = st.sidebar.selectbox("Database", dbs, index=dbs.index(profile.default_db) if profile.default_db in dbs else 0)
client_db = make_client(profile, password, dbname=db)
insp = Introspector(client_db)

try:
    schemas = insp.list_schemas()
except DbError as e:
    st.error(f"スキーマ一覧取得に失敗: {e}")
    st.stop()

schema = st.sidebar.selectbox("Schema", schemas, index=schemas.index("public") if "public" in schemas else 0)

max_edges = st.sidebar.slider("最大エッジ数（巨大スキーマ対策）", 50, 2000, 400, 50)
show_schema = st.sidebar.checkbox("図で schema を表示", value=False)

col1, col2 = st.columns([3, 2], gap="large")
with col1:
    st.subheader("ER図（外部キーFKベース）")
    try:
        fk_rows = insp.get_fk_edges(schema)
        if not fk_rows:
            st.warning("外部キーが見つかりません。テーブル一覧のみのER図を表示します。")
            tables = insp.list_tables(schema)
            if len(tables) > max_edges:
                tables = tables[:max_edges]
                st.warning(f"テーブル数が多いため先頭 {max_edges} 件に制限しました。")
            g = GraphBuilder().build_table_graph(schema, tables)
        else:
            if len(fk_rows) > max_edges:
                fk_rows = fk_rows[:max_edges]
                st.warning(f"エッジ数が多いため先頭 {max_edges} 件に制限しました。")
            g = GraphBuilder().build_er_graph_from_fk_rows(fk_rows, schema_filter=schema)

        code = render_er_mermaid(g, show_schema=show_schema)
        mermaid(code, height=720)
        st.download_button("Mermaid（.mmd）をダウンロード", data=code, file_name=f"{db}_{schema}_er.mmd")
    except DbError as e:
        st.error(f"ER図生成に失敗: {e}")

with col2:
    st.subheader("統計ダッシュボード")
    st.caption("行数などは推定値・統計値です。")
    try:
        top_size = insp.top_tables_by_size(schema, limit=20)
        if top_size:
            for r in top_size:
                r["total"] = human_bytes(r["total_bytes"])
            st.markdown("#### サイズ TOP 20")
            st.dataframe(top_size, width="stretch")

        top_writes = insp.top_tables_by_updates(schema, limit=20)
        if top_writes:
            st.markdown("#### 更新（write）TOP 20")
            st.dataframe(top_writes, width="stretch")
    except DbError as e:
        st.error(f"統計取得に失敗: {e}")
