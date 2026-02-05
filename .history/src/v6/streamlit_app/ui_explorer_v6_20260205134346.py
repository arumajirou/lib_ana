# C:\lib_ana\src\v6\streamlit_app\ui_explorer_v6.py
from __future__ import annotations

import streamlit as st
import pandas as pd

from v6.core.link_resolver_v6 import (
    lookup_pypi_urls,
    extract_github_urls,
    guess_github_search_url,
    guess_huggingface_search_url,
)


def _styled_or_plain(df: pd.DataFrame, color: bool) -> object:
    if not color or df is None or df.empty:
        return df
    # Type/Roleなどカテゴリ列があれば軽く色付け
    cat_cols = [c for c in ["Type", "Role", "TopGroup"] if c in df.columns]
    if not cat_cols:
        return df

    # “見やすさ”優先：カテゴリ列だけ背景を薄く
    def hi(s: pd.Series):
        return ["background-color: rgba(16,185,129,0.12)" for _ in s]

    sty = df.style
    for c in cat_cols:
        sty = sty.apply(hi, subset=[c])
    return sty


def render_explorer(analysis: dict) -> None:
    summary = analysis["summary"]
    df_nodes = analysis["nodes"]
    tables = analysis["tables"]
    param_tables = analysis["param_tables"]
    lib = analysis["library"]

    # --- Summaryカード（クリックで表切替） ---
    st.subheader("Summary")
    c1, c2, c3, c4, c5 = st.columns(5)

    def btn(label: str, key: str, col):
        with col:
            if st.button(f"{label}: {summary.get(label, '-')}"):
                st.session_state.active_table = key

    btn("Modules", "Modules", c1)
    btn("Classes", "Classes", c2)
    btn("Functions", "Functions", c3)
    btn("Methods/Props", "Methods", c4)
    btn("External", "External", c5)

    st.divider()

    # --- メイン：表 + Inspector ---
    left, right = st.columns([1.35, 1.0], gap="large")

    with left:
        st.subheader(f"Table: {st.session_state.active_table}")
        df = tables.get(st.session_state.active_table, pd.DataFrame())
        if df is None or df.empty:
            st.warning("No rows.")
        else:
            # 行選択（公式）:contentReference[oaicite:7]{index=7}
            event = st.dataframe(
                _styled_or_plain(df, st.session_state.color_tables),
                use_container_width=True,
                hide_index=True,
                on_select="rerun",
                selection_mode="single-row",
                key=f"tbl_{st.session_state.active_table}",
            )
            sel_rows = event.selection.rows if hasattr(event, "selection") else []
            if sel_rows:
                st.session_state.last_selected["row_index"] = int(sel_rows[0])
                st.session_state.last_selected["table"] = st.session_state.active_table

        # 分類テーブル（追加で欲しいやつ）
        with st.expander(
            "分類（Role/Event/近似クラスタ）を含む Nodes（上位200）", expanded=False
        ):
            view_cols = [
                c
                for c in [
                    "Type",
                    "Name",
                    "Path",
                    "Module",
                    "Role",
                    "EventLike",
                    "TopGroup",
                    "NameCluster",
                ]
                if c in df_nodes.columns
            ]
            st.dataframe(
                _styled_or_plain(
                    df_nodes[view_cols].head(200), st.session_state.color_tables
                ),
                use_container_width=True,
                hide_index=True,
            )

        with st.expander("引数対応表（ParamOverview / ParamMap）", expanded=False):
            po = param_tables.get("ParamOverview", pd.DataFrame())
            pm = param_tables.get("ParamMap", pd.DataFrame())
            st.markdown("### ParamOverview（引数名→頻度/型/対象）")
            st.dataframe(po, use_container_width=True, hide_index=True)
            st.markdown("### ParamMap（引数名→API一覧）")
            st.dataframe(pm.head(500), use_container_width=True, hide_index=True)

    with right:
        st.subheader("Inspector")

        # 選択行があれば詳細表示
        table_name = st.session_state.last_selected.get("table")
        row_index = st.session_state.last_selected.get("row_index")

        if table_name and row_index is not None:
            cur_df = tables.get(table_name, pd.DataFrame())
            if cur_df is not None and not cur_df.empty and 0 <= row_index < len(cur_df):
                row = cur_df.iloc[row_index].to_dict()
                st.json(row, expanded=False)

                # 外部リンク探索
                st.markdown("### Links")
                if st.session_state.enable_online_lookup:
                    try:
                        urls = lookup_pypi_urls(lib)
                    except Exception as e:
                        urls = {}
                        st.warning(f"PyPI lookup failed: {repr(e)}")
                else:
                    urls = {}

                if not urls:
                    # フォールバック：検索URLだけ出す
                    urls = {
                        "PyPI": f"https://pypi.org/project/{lib}/",
                        "GitHub search": guess_github_search_url(lib),
                        "HuggingFace search": guess_huggingface_search_url(lib),
                    }

                # 新規タブフラグ：
                # - StreamlitのMarkdownリンクは新規タブになりやすい（コミュニティ知見）:contentReference[oaicite:8]{index=8}
                # - HTML anchorで target を指定して挙動切替（ただし st.html は target が落ちるケースあり）:contentReference[oaicite:9]{index=9}
                open_new = st.session_state.open_new_tab
                for k, v in urls.items():
                    if open_new:
                        st.markdown(f"- [{k}]({v})")
                    else:
                        st.markdown(
                            f'- <a href="{v}" target="_self">{k}</a>',
                            unsafe_allow_html=True,
                        )

        else:
            st.info("左の表で行を選択すると、ここに詳細が出ます。")
