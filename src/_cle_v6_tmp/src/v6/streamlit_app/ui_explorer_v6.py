# ファイルパス: C:\lib_ana\src\v6\streamlit_app\ui_explorer_v6.py
from __future__ import annotations
from typing import Any, Dict, List
import pandas as pd
import streamlit as st

from v6.core.hierarchy_v6 import build_options, auto_depth
from v6.core.param_map_v6 import build_param_reverse_index
from v6.core.link_resolver_v6 import lookup_pypi_urls, extract_github_urls, guess_github_search_url, guess_huggingface_search_url

TYPE_COLOR = {
    "module": "#eef2ff",
    "class": "#ecfeff",
    "function": "#f0fdf4",
    "method": "#fff7ed",
    "property": "#fefce8",
    "external": "#fdf2f8",
}

def _style_by_type(df: pd.DataFrame) -> "pd.io.formats.style.Styler":
    if df is None or df.empty or "Type" not in df.columns:
        return df.style
    def _row_style(row):
        t = str(row.get("Type","")).lower()
        bg = TYPE_COLOR.get(t, "")
        return [f"background-color: {bg}" if bg else "" for _ in row]
    return df.style.apply(_row_style, axis=1)

def _render_df(df: pd.DataFrame, color_tables: bool, key: str, height: int = 360) -> None:
    if df is None or df.empty:
        st.info("データがありません。")
        return
    if color_tables and "Type" in df.columns:
        st.dataframe(_style_by_type(df), use_container_width=True, height=height)
    else:
        st.dataframe(df, use_container_width=True, height=height)

def render_explorer(analysis: Dict[str, Any]) -> None:
    lib = analysis.get("library","")
    summary = analysis.get("summary", {}) or {}
    nodes: pd.DataFrame = analysis.get("nodes", pd.DataFrame())
    errors: pd.DataFrame = analysis.get("errors", pd.DataFrame())
    tables: Dict[str, pd.DataFrame] = analysis.get("tables", {}) or {}
    param_tables: Dict[str, pd.DataFrame] = analysis.get("param_tables", {}) or {}

    color_tables = bool(st.session_state.get("color_tables", False))
    open_new_tab = bool(st.session_state.get("open_new_tab", True))
    enable_online_lookup = bool(st.session_state.get("enable_online_lookup", True))
    max_items = int(st.session_state.get("max_list_items", 500))

    tab_nav, tab_sum, tab_param, tab_tables, tab_links = st.tabs(
        ["🧭 Navigator", "📊 Summary", "🧬 Param Reverse", "📚 Tables", "🔗 Links"]
    )

    with tab_sum:
        st.subheader(f"📊 Summary — {lib}")
        preferred = ["Modules","Classes","Functions","Methods/Props","External","UniqueParamNames","UniqueReturnTypes","Errors"]
        rows = [{"Metric": k, "Value": summary.get(k, 0)} for k in preferred]
        st.dataframe(pd.DataFrame(rows), use_container_width=True, height=260)

        metric = st.radio("表を表示（クリック相当）", ["Modules","Classes","Functions","Methods","External","Errors"], horizontal=True)
        if metric == "Errors":
            _render_df(errors, color_tables, "errors")
        else:
            _render_df(tables.get(metric, pd.DataFrame()), color_tables, metric)

    with tab_tables:
        st.subheader("📚 一覧表（分類フィルタ付き）")
        choice = st.selectbox("表示する表", ["Modules","Classes","Functions","Methods","External"], index=0)
        df = tables.get(choice, pd.DataFrame()).copy()
        _render_df(df, color_tables, "tbl")

        if nodes is not None and not nodes.empty and "Role" in nodes.columns:
            st.markdown("#### 分類フィルタ")
            roles = sorted({str(x) for x in nodes["Role"].dropna().unique()})
            role = st.selectbox("Role(機能分類)", options=["(all)"] + roles, index=0)
            ev = st.selectbox("EventLike(イベント系)", options=["(all)","True","False"], index=0)
            df2 = df.copy()
            if not df2.empty and role != "(all)" and "Role" in df2.columns:
                df2 = df2[df2["Role"] == role]
            if not df2.empty and ev != "(all)" and "EventLike" in df2.columns:
                df2 = df2[df2["EventLike"].astype(bool) == (ev == "True")]
            _render_df(df2, color_tables, "filtered")

    with tab_param:
        st.subheader("🧬 引数の逆引き（ParamName → API一覧）")
        df_map = param_tables.get("ParamMap", pd.DataFrame())
        df_over = param_tables.get("ParamOverview", pd.DataFrame())

        if df_over is None or df_over.empty:
            st.warning("引数情報がありません。Deep param inspect をONにして再解析すると増える場合があります。")
        else:
            st.caption("一意引数一覧（頻度順）")
            st.dataframe(df_over.head(300), use_container_width=True, height=320)

            df_idx, rev = build_param_reverse_index(df_map)
            q = st.text_input("引数名で検索（部分一致）", value="", placeholder="例: alpha / seed / X / lr …")
            candidates = sorted([k for k in rev.keys() if q.lower() in k.lower()])[:200] if q else sorted(list(rev.keys()))[:200]
            chosen = st.selectbox("ParamName", options=candidates) if candidates else None
            if chosen:
                st.markdown(f"#### 使用箇所 — `{chosen}`")
                st.dataframe(pd.DataFrame({"API": rev.get(chosen, [])}), use_container_width=True, height=360)

            st.divider()
            st.markdown("#### 引数対応表（ParamMap）")
            st.dataframe(df_map.head(800), use_container_width=True, height=360)

    with tab_links:
        st.subheader("🔗 PyPI / GitHub / HuggingFace へのリンク")
        pkg = st.text_input("Package name（PyPI名）", value=lib)
        if not enable_online_lookup:
            st.info("オンライン探索がOFFです。")
        else:
            if st.button("Search URLs"):
                urls = lookup_pypi_urls(pkg)
                st.write(urls if urls else {"warning": "PyPIから取得できません（名前違い/制限/ネットワーク）"})

                gh = extract_github_urls(urls) if urls else []
                st.write({
                    "PyPI": f"https://pypi.org/project/{pkg}/",
                    "GitHub search": guess_github_search_url(pkg),
                    "HuggingFace search": guess_huggingface_search_url(pkg),
                    "GitHub urls": gh,
                })

                def link_html(url: str, label: str) -> str:
                    if open_new_tab:
                        return f"<a href='{url}' target='_blank' rel='noreferrer'>{label}</a>"
                    return f"<a href='{url}'>{label}</a>"

                st.markdown("#### リンク", unsafe_allow_html=True)
                base = [
                    ("PyPI", f"https://pypi.org/project/{pkg}/"),
                    ("GitHub search", guess_github_search_url(pkg)),
                    ("HuggingFace search", guess_huggingface_search_url(pkg)),
                ]
                for title, url in base:
                    st.markdown(link_html(url, f"[{title}] {url}"), unsafe_allow_html=True)
                for url in gh:
                    st.markdown(link_html(url, f"[GitHub] {url}"), unsafe_allow_html=True)

    with tab_nav:
        st.subheader("🧭 Navigator（動的階層 → 5列）")
        if nodes is None or nodes.empty or "Type" not in nodes.columns:
            st.info("解析結果がありません。")
            return

        df_mod = nodes[nodes["Type"] == "module"].copy()
        if df_mod.empty:
            st.warning("Modules がありません。")
            return

        df_mod = df_mod.sort_values("Path")
        module_paths = df_mod["Path"].astype(str).tolist()

        col1, col2 = st.columns([1,2])
        with col1:
            auto = st.checkbox("Auto depth", value=True)
        with col2:
            max_depth = st.slider("Max depth", 1, 10, 8)

        depth = auto_depth(module_paths, max_depth=max_depth) if auto else max_depth
        st.caption(f"動的階層（深さ={depth}）例: neuralforecast → common → _base_auto → BaseAuto …")

        selected_levels: List[str] = []
        for lvl in range(depth):
            opts, _ = build_options(module_paths, selected_levels)
            if not opts:
                break
            pick = st.selectbox(f"Level {lvl+1}", options=["(all)"] + opts, index=0)
            if pick == "(all)":
                break
            selected_levels.append(pick)

        prefix = ".".join(selected_levels)
        filtered_mods = [m for m in module_paths if m.startswith(prefix)] if prefix else module_paths
        q = st.text_input("Modules filter（部分一致/手入力）", value="", placeholder="例: common._base_auto / plotting / util ...")
        if q.strip():
            qq = q.strip().lower()
            filtered_mods = [m for m in filtered_mods if qq in m.lower()]
        if len(filtered_mods) > max_items:
            st.warning(f"候補が多いので先頭 {max_items} 件に制限しました（Settingsで変更可）")
            filtered_mods = filtered_mods[:max_items]

        module_sel = st.selectbox("1. Modules", options=filtered_mods, index=0)

        mod_row = df_mod[df_mod["Path"].astype(str) == str(module_sel)].head(1)
        if mod_row.empty:
            st.warning("モジュールが見つかりません。")
            return
        mod_id = str(mod_row.iloc[0].get("ID", ""))

        df_items = nodes[(nodes["Parent"].astype(str) == mod_id) & (nodes["Type"].isin(["class","function","external"]))].copy()
        if df_items.empty:
            st.info("このモジュール配下に Items がありません。")
            return
        df_items["Label"] = df_items["Type"].astype(str) + ": " + df_items["Name"].astype(str)
        df_items = df_items.sort_values(["Type","Name"])

        item_q = st.text_input("Items filter（部分一致/手入力）", value="", placeholder="例: BaseAuto / heatmap / sobol ...")
        labels = df_items["Label"].tolist()
        if item_q.strip():
            qq = item_q.strip().lower()
            labels = [x for x in labels if qq in x.lower()]
        labels = labels[:max_items] if len(labels) > max_items else labels

        item_sel = st.selectbox("2. Items（class/function 分離）", options=labels, index=0)
        item_row = df_items[df_items["Label"] == item_sel].head(1)
        node_id = str(item_row.iloc[0].get("ID", ""))
        node_type = str(item_row.iloc[0].get("Type", ""))

        member_id = None
        if node_type in {"class","external"}:
            df_mem = nodes[(nodes["Parent"].astype(str) == node_id) & (nodes["Type"].isin(["method","property"]))].copy()
            if not df_mem.empty:
                df_mem["Label"] = df_mem["Type"].astype(str) + ": " + df_mem["Name"].astype(str)
                df_mem = df_mem.sort_values(["Type","Name"])
                mem_labels = df_mem["Label"].tolist()
                mem_q = st.text_input("Members filter（部分一致）", value="", placeholder="例: fit / plot / to_ ...")
                if mem_q.strip():
                    qq = mem_q.strip().lower()
                    mem_labels = [x for x in mem_labels if qq in x.lower()]
                mem_labels = mem_labels[:max_items] if len(mem_labels) > max_items else mem_labels
                mem_sel = st.selectbox("3. Members", options=mem_labels, index=0)
                member_row = df_mem[df_mem["Label"] == mem_sel].head(1)
                member_id = str(member_row.iloc[0].get("ID",""))
            else:
                st.caption("Members なし")

        target_id = member_id or node_id
        trow = nodes[nodes["ID"].astype(str) == str(target_id)].head(1)
        tpath = str(trow.iloc[0].get("Path") or trow.iloc[0].get("Name") or "")

        st.markdown("#### Inspector（選択中）")
        cols = ["Type","Name","Path","Module","Role","EventLike","NameCluster","TopGroup"]
        obj = {c: (trow.iloc[0].get(c) if c in trow.columns else None) for c in cols}
        st.write(obj)

        params = trow.iloc[0].get("Params") if ("Params" in trow.columns and not trow.empty) else None
        param_names: List[str] = []
        if isinstance(params, list):
            for it in params:
                if isinstance(it, dict) and it.get("name"):
                    param_names.append(str(it["name"]))
                elif isinstance(it, str):
                    param_names.append(it)
        elif isinstance(params, dict):
            param_names = list(params.keys())

        param_names = sorted({p for p in param_names if p})
        if param_names:
            st.selectbox("4. Params", options=param_names, index=0)
            st.selectbox("5. Values（候補）", options=["None","0","1"], index=0)
        else:
            st.caption("Params なし（Deep param inspect をONにして再解析すると増える場合があります）")
