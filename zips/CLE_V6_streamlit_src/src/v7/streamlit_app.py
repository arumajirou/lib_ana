# ファイルパス: C:\lib_ana\src\v6\streamlit_app.py
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd
import streamlit as st

# --- import 解決（v6 は src\v6 配下、解析器は src 直下にある想定） ---
SRC_ROOT = Path(__file__).resolve().parents[1]  # ...\src
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

# 既存資産
from package_catalog_v4 import build_package_catalog  # type: ignore

from v6.analysis_service import analyze_library, split_tables, default_config
from v6.state_store import load_state, save_state, push_history, PersistedState
from v6.name_tools import group_key, extract_features, nearest_names
from v6.table_tools import style_by_type, build_param_reverse_index, metric_summary_table
from v6.link_resolver import resolve_pypi, resolve_github_from_pypi, search_github, search_huggingface
from v6.report_exporter import ReportBundle, export_single_html
from v6.code_executor import compile_only, run_code

# v5 のコード生成があれば利用（無い場合でも落ちない）
try:
    from v5.codegen_v5 import generate_sample_code  # type: ignore
except Exception:
    generate_sample_code = None  # type: ignore

try:
    from v5.mermaid_export_v5 import make_mermaid_and_html  # type: ignore
except Exception:
    make_mermaid_and_html = None  # type: ignore

st.set_page_config(
    page_title="Cognitive Library Explorer V6",
    page_icon="🔧",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ==========
# UI: Header
# ==========
st.markdown(
    """
    <div style="font-size:22px;font-weight:700;">
      🔧 Cognitive Library Explorer <span style="color:#4F46E5;">V6</span>
    </div>
    <div style="color:#6B7280;font-size:13px;margin-bottom:6px;">
      Modules → Items → Members → Params → Values（＋可変深度の階層）で Python ライブラリを探索（Streamlit UI）
    </div>
    """, unsafe_allow_html=True
)

# ==========
# State (persisted + session)
# ==========
if "persisted" not in st.session_state:
    st.session_state.persisted = load_state()

ps: PersistedState = st.session_state.persisted

# ==========
# Sidebar: global settings
# ==========
with st.sidebar:
    st.subheader("⚙️ Settings")
    ps.module_group_depth = st.slider("階層の深さ（Module group depth）", 1, 6, int(ps.module_group_depth))
    ps.max_list_items = st.slider("リスト最大表示件数（パフォーマンス対策）", 100, 5000, int(ps.max_list_items), step=100)
    ps.open_links_new_tab = st.checkbox("外部リンクを新しいタブで開く", value=bool(ps.open_links_new_tab))
    ps.color_tables = st.checkbox("表を色分けして表示（Type別）", value=bool(ps.color_tables))
    st.caption("※色分けは pandas Styler。大規模テーブルだと重くなるので必要時だけON推奨。")

    st.divider()
    st.subheader("🕘 History")
    if ps.history_labels:
        chosen = st.selectbox("前回の選択へジャンプ", options=["(none)"] + ps.history_labels, index=0)
        if chosen and chosen != "(none)":
            # 選択ラベル→node_id を復元（同順で保持）
            idx = ps.history_labels.index(chosen)
            st.session_state.jump_node_id = ps.history_node_ids[idx]
    else:
        st.caption("まだ履歴はありません。")

    st.divider()
    st.subheader("📤 Export")
    st.caption("レポートは HTML 1 ファイルとして出力できます（タブ情報を統合）。")

# ==========
# Library selector
# ==========
catalog = build_package_catalog(max_items=4000)
lib_opts = [(f"{it.import_name}   ({it.dist_name} {it.version})", it.import_name, it.dist_name, it.version) for it in catalog]
lib_opts.sort(key=lambda x: x[1].lower())

# デフォルトは前回のライブラリ
default_lib = ps.last_library if ps.last_library else (lib_opts[0][1] if lib_opts else "")
lib_names = [o[1] for o in lib_opts]
try:
    default_idx = lib_names.index(default_lib)
except Exception:
    default_idx = 0

colA, colB, colC = st.columns([4,1,1], vertical_alignment="bottom")
with colA:
    lib_name = st.selectbox("Library", options=lib_names, index=default_idx)
with colB:
    analyze_clicked = st.button("Analyze", type="primary", use_container_width=True)
with colC:
    deep_mode = st.toggle("Deep", value=False, help="より詳細な解析（重い処理を増やす想定。現時点ではUI上のフラグ）")

# 保存
ps.last_library = lib_name
save_state(ps)

# ==========
# Analysis (cached)
# ==========
@st.cache_data(show_spinner=False)
def _cached_analyze(lib: str) -> Tuple[dict, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    res = analyze_library(lib, default_config())
    return res.summary, res.nodes, res.edges, res.errors

if analyze_clicked or ("analysis_loaded_for" not in st.session_state) or (st.session_state.analysis_loaded_for != lib_name):
    # Progress UI
    status = st.status(f"解析を開始: {lib_name}", expanded=True)
    p = st.progress(0)

    p.progress(5, text="準備中…")
    status.update(label="解析準備中…", state="running")
    try:
        p.progress(15, text="解析器を実行…（キャッシュがあれば高速）")
        summary, nodes, edges, errors = _cached_analyze(lib_name)
        p.progress(60, text="テーブル整形…")
        tables = split_tables(nodes)
        p.progress(80, text="逆引きインデックス作成…")
        df_param_idx, rev_index = build_param_reverse_index(nodes)
        p.progress(95, text="UI 状態更新…")
        st.session_state.summary = summary
        st.session_state.nodes = nodes
        st.session_state.edges = edges
        st.session_state.errors = errors
        st.session_state.tables = tables
        st.session_state.df_param_idx = df_param_idx
        st.session_state.rev_index = rev_index
        st.session_state.analysis_loaded_for = lib_name
        p.progress(100, text="完了")
        status.update(label=f"解析完了: {lib_name}", state="complete")
    except Exception as e:
        p.progress(100)
        status.update(label="解析でエラー", state="error")
        st.exception(e)

# ==========
# Helpers
# ==========
def _limit_options(opts: List[str], max_items: int) -> List[str]:
    if len(opts) <= max_items:
        return opts
    return opts[:max_items]

def _render_table(df: pd.DataFrame, key: str) -> None:
    if df is None or df.empty:
        st.info("データがありません。")
        return
    if ps.color_tables and "Type" in df.columns:
        st.dataframe(style_by_type(df), use_container_width=True, height=380)
    else:
        st.dataframe(df, use_container_width=True, height=380)

def _link_html(url: str, label: str) -> str:
    if ps.open_links_new_tab:
        return f"<a href='{url}' target='_blank' rel='noreferrer'>{label}</a>"
    return f"<a href='{url}'>{label}</a>"

# ==========
# Tabs
# ==========
tab_nav, tab_summary, tab_params, tab_visual, tab_links, tab_codegen, tab_export = st.tabs(
    ["🧭 Navigator", "📊 Summary", "🧬 Param Index", "📈 Visualize", "🔗 Links", "💡 Code", "📦 Export"]
)

# ==========
# Tab: Summary (クリック相当：Metric選択→テーブル表示)
# ==========
with tab_summary:
    summary: dict = st.session_state.get("summary", {}) or {}
    tables: dict = st.session_state.get("tables", {}) or {}
    st.markdown(f"### 📊 Summary — `{lib_name}`")
    df_sum = metric_summary_table(summary)
    st.dataframe(df_sum, use_container_width=True, height=260)

    metric = st.radio(
        "表を表示（クリック相当）",
        options=["Modules","Classes","Functions","Methods","Properties","External","Errors"],
        horizontal=True,
    )
    if metric == "Errors":
        _render_table(st.session_state.get("errors", pd.DataFrame()), "errors")
    else:
        df = tables.get(metric, pd.DataFrame())
        _render_table(df, metric)

# ==========
# Tab: Navigator (可変階層 + 5列ナビ + 手入力フィルタ + 近似検索)
# ==========
with tab_nav:
    nodes: pd.DataFrame = st.session_state.get("nodes", pd.DataFrame())
    if nodes is None or nodes.empty:
        st.info("Analyze を実行してください。")
    else:
        # --- module list ---
        df_mod = nodes[nodes["Type"] == "module"].copy()
        df_mod = df_mod.sort_values("Path")
        module_paths = df_mod["Path"].astype(str).tolist()

        # 可変深度グループ
        groups = sorted(set(group_key(m, ps.module_group_depth) for m in module_paths))
        default_group = ps.last_group if ps.last_group in groups else (groups[0] if groups else "")
        group_filter = st.selectbox("Group（階層）", options=groups, index=(groups.index(default_group) if default_group in groups else 0))
        ps.last_group = group_filter

        # Modules（手入力フィルタ）
        mod_query = st.text_input("Modules filter（部分一致/手入力）", value="", placeholder="例: SALib.analyze / plotting / util ...")
        filtered_mods = [m for m in module_paths if m.startswith(group_filter)]
        if mod_query.strip():
            q = mod_query.strip().lower()
            filtered_mods = [m for m in filtered_mods if q in m.lower()]

        filtered_mods = _limit_options(filtered_mods, ps.max_list_items)
        if not filtered_mods:
            st.warning("該当するモジュールがありません。")
            st.stop()

        default_module = ps.last_module if ps.last_module in filtered_mods else filtered_mods[0]
        module_sel = st.selectbox("1. Modules", options=filtered_mods, index=filtered_mods.index(default_module))
        ps.last_module = module_sel

        # Module row id
        mod_row = df_mod[df_mod["Path"].astype(str) == str(module_sel)].head(1)
        if mod_row.empty:
            st.warning("モジュールが見つかりません。")
            st.stop()
        mod_id = str(mod_row.iloc[0]["ID"])

        # Items = class / function / external
        df_items = nodes[(nodes["Parent"] == mod_id) & (nodes["Type"].isin(["class","function","external"]))].copy()
        df_items["Label"] = df_items["Type"].astype(str) + ": " + df_items["Name"].astype(str)
        df_items = df_items.sort_values(["Type","Name"])
        item_labels = df_items["Label"].tolist()

        item_query = st.text_input("Items filter（部分一致/手入力）", value="", placeholder="例: heatmap / sobol / sample ...")
        if item_query.strip():
            q = item_query.strip().lower()
            item_labels = [x for x in item_labels if q in x.lower()]
        item_labels = _limit_options(item_labels, ps.max_list_items)
        if not item_labels:
            st.warning("該当する Item がありません。")
            st.stop()

        default_item = ps.last_item if ps.last_item in item_labels else item_labels[0]
        item_sel = st.selectbox("2. Items（class/function を分離）", options=item_labels, index=item_labels.index(default_item))
        ps.last_item = item_sel

        item_row = df_items[df_items["Label"] == item_sel].head(1)
        node_id = str(item_row.iloc[0]["ID"])
        node_type = str(item_row.iloc[0]["Type"])

        # Members (class/external のみ)
        member_id = None
        if node_type in {"class","external"}:
            df_mem = nodes[(nodes["Parent"] == node_id) & (nodes["Type"].isin(["method","property"]))].copy()
            df_mem["Label"] = df_mem["Type"].astype(str) + ": " + df_mem["Name"].astype(str)
            df_mem = df_mem.sort_values(["Type","Name"])
            mem_labels = df_mem["Label"].tolist()
            mem_query = st.text_input("Members filter（部分一致）", value="", placeholder="例: fit / plot / to_ ...")
            if mem_query.strip():
                q = mem_query.strip().lower()
                mem_labels = [x for x in mem_labels if q in x.lower()]
            mem_labels = _limit_options(mem_labels, ps.max_list_items)

            if mem_labels:
                default_mem = ps.last_member if ps.last_member in mem_labels else mem_labels[0]
                mem_sel = st.selectbox("3. Members", options=mem_labels, index=mem_labels.index(default_mem))
                ps.last_member = mem_sel
                member_row = df_mem[df_mem["Label"] == mem_sel].head(1)
                member_id = str(member_row.iloc[0]["ID"])
            else:
                st.caption("Members なし")
                ps.last_member = None

        # Current target
        target_id = member_id or node_id
        target_row = nodes[nodes["ID"].astype(str) == str(target_id)].head(1)
        target_path = str(target_row.iloc[0].get("Path") or target_row.iloc[0].get("Name") or "")

        # 履歴 push
        ps = push_history(ps, label=target_path, node_id=target_id)
        save_state(ps)

        # Params/Values（Nodes に Params が無い場合も落ちない）
        params_raw = target_row.iloc[0].get("Params", None)
        param_names: List[str] = []
        if isinstance(params_raw, dict):
            param_names = list(params_raw.keys())
        elif isinstance(params_raw, list):
            for it in params_raw:
                if isinstance(it, dict) and "name" in it:
                    param_names.append(str(it["name"]))
                elif isinstance(it, str):
                    param_names.append(it)

        param_names = sorted(set([p for p in param_names if p]))
        param_query = st.text_input("4. Params filter（部分一致）", value="", placeholder="例: alpha / seed / X ...")
        if param_query.strip():
            q = param_query.strip().lower()
            param_names = [p for p in param_names if q in p.lower()]

        if param_names:
            default_param = ps.last_param if ps.last_param in param_names else param_names[0]
            param_sel = st.selectbox("4. Params", options=param_names, index=param_names.index(default_param))
            ps.last_param = param_sel
        else:
            param_sel = None
            st.caption("Params 情報がありません（解析器の出力に Params 列が無い可能性）。")

        # Values（候補は v5 の value candidate があれば利用する想定：ここではプレースホルダ）
        values = []
        if param_sel:
            # 最低限の候補（None/0/1）＋型ヒント推定
            values = ["None", "0", "1"]
        if values:
            st.selectbox("5. Values（候補）", options=values, index=0)

        # 近しい名前（類似）
        st.divider()
        st.markdown("#### 🔎 近しい名前（文字列類似）")
        all_paths = nodes["Path"].astype(str).tolist() if "Path" in nodes.columns else nodes["Name"].astype(str).tolist()
        sims = nearest_names(target_path, all_paths, k=10)
        if sims:
            st.write(pd.DataFrame([{"Name": n, "Similarity": round(s,3)} for n,s in sims]))
        else:
            st.caption("（類似候補なし）")

        # 分類（カテゴリ/キーワード）
        st.markdown("#### 🧩 分類（機能/イベント/近しい名前）")
        feat = extract_features(target_path)
        st.write({
            "category(分類)": feat.category,
            "keywords(重要語)": feat.keywords[:12],
            "tokens(トークン)": feat.tokens[:20],
        })

# ==========
# Tab: Param Index（引数逆引き + 対応表）
# ==========
with tab_params:
    df_param_idx: pd.DataFrame = st.session_state.get("df_param_idx", pd.DataFrame())
    rev_index: Dict[str, List[str]] = st.session_state.get("rev_index", {}) or {}

    st.markdown("### 🧬 一意の引数（Param）逆引き & 引数対応表")
    if df_param_idx is None or df_param_idx.empty:
        st.info("Params 情報が無いか、解析器出力に Params 列がありません。")
    else:
        st.dataframe(df_param_idx.head(300), use_container_width=True, height=360)

        p_name = st.text_input("引数名で検索（逆引き）", value="", placeholder="例: alpha / seed / lr ...")
        if p_name.strip():
            p = p_name.strip()
            # 部分一致も許容
            candidates = [x for x in rev_index.keys() if p.lower() in x.lower()]
            candidates = sorted(candidates)[:200]
            chosen = st.selectbox("候補", options=candidates) if candidates else None
            if chosen:
                st.markdown(f"#### 使用箇所 — `{chosen}`")
                st.dataframe(pd.DataFrame({"API": rev_index.get(chosen, [])}), use_container_width=True, height=360)

# ==========
# Tab: Visualize（可視化＋解析強化）
# ==========
with tab_visual:
    nodes: pd.DataFrame = st.session_state.get("nodes", pd.DataFrame())
    summary: dict = st.session_state.get("summary", {}) or {}

    st.markdown("### 📈 可視化（概要→詳細）")
    if nodes is None or nodes.empty:
        st.info("Analyze を実行してください。")
    else:
        # Type別
        if "Type" in nodes.columns:
            by_type = nodes["Type"].value_counts().reset_index()
            by_type.columns = ["Type","Count"]
            st.bar_chart(by_type.set_index("Type"))

        # モジュール別オブジェクト数
        if "Module" in nodes.columns and "Type" in nodes.columns:
            df_mod = nodes[nodes["Type"].isin(["class","function","method","property"])].groupby("Module")["ID"].count().reset_index()
            df_mod = df_mod.rename(columns={"ID":"Objects"}).sort_values("Objects", ascending=False).head(30)
            st.caption("Top modules by objects")
            st.dataframe(df_mod, use_container_width=True, height=280)

        # Mermaid（可能なら）
        st.divider()
        st.markdown("#### 🧩 Mermaid（依存/関係図）")
        if make_mermaid_and_html is None:
            st.caption("v5 の mermaid_export が未検出。Mermaid はスキップ。")
        else:
            edges: pd.DataFrame = st.session_state.get("edges", pd.DataFrame())
            try:
                mmd, html_out = make_mermaid_and_html(nodes, edges, max_nodes=120)
                st.code(mmd, language="mermaid")
                st.components.v1.html(html_out, height=520, scrolling=True)
            except Exception as e:
                st.warning("Mermaid の生成に失敗しました。")
                st.exception(e)

# ==========
# Tab: Links（PyPI/GitHub/HF）
# ==========
with tab_links:
    st.markdown("### 🔗 ライブラリ名から外部サイト探索（PyPI / GitHub / HuggingFace）")
    dist_guess = lib_name  # import_name -> dist_name も可能ならここで補正（今回は簡略）
    q = st.text_input("検索クエリ（必要なら修正）", value=dist_guess)

    if st.button("Search Links", use_container_width=False):
        with st.status("検索中…", expanded=False):
            hits = []
            pypi_hits = resolve_pypi(q)
            hits += resolve_github_from_pypi(pypi_hits)
            hits += search_github(q, max_hits=5)
            hits += search_huggingface(q, max_hits=5)

        if hits:
            rows = [{"site": h.site, "title": h.title, "url": h.url, "confidence": round(h.confidence,2)} for h in hits if h.url]
            df = pd.DataFrame(rows).sort_values(["site","confidence"], ascending=[True, False])
            st.dataframe(df, use_container_width=True, height=320)

            st.markdown("#### リンク（表示）")
            for _, r in df.iterrows():
                url = str(r["url"])
                label = f"[{r['site']}] {r['title']} ({r['confidence']})"
                st.markdown(_link_html(url, label), unsafe_allow_html=True)
        else:
            st.info("ヒットなし（ネットワーク/レート制限/名前違いの可能性）。")

# ==========
# Tab: Code（生成→コンパイル→実行→可視化）
# ==========
with tab_codegen:
    st.markdown("### 💡 Sample Code（生成→コンパイル→実行）")
    st.caption("安全優先: まず compile-only を推奨。実行は safe_mode をON推奨（完全隔離ではありません）。")

    code = st.session_state.get("sample_code", "")
    if generate_sample_code is not None and st.button("Generate Sample Code"):
        try:
            # 生成側が選択状態を必要とする場合があるので最小引数
            code = generate_sample_code(lib_name=lib_name)  # type: ignore
        except Exception:
            code = f"# TODO: generate_sample_code のシグネチャが違う可能性があります\n# lib_name={lib_name}\n"
        st.session_state.sample_code = code

    code = st.text_area("Generated / Editable Code", value=code or "", height=260)

    c1, c2, c3 = st.columns([1,1,1])
    with c1:
        safe_mode = st.checkbox("safe_mode（推奨）", value=True)
    with c2:
        do_run = st.button("Compile & Run", type="primary", use_container_width=True)
    with c3:
        do_compile = st.button("Compile only", use_container_width=True)

    if do_compile:
        ok, msg = compile_only(code)
        st.success("Compile OK") if ok else st.error(msg)

    if do_run:
        res = run_code(code, safe_mode=safe_mode)
        if res.get("ok"):
            st.success("実行成功")
        else:
            st.error("実行失敗（compile または runtime）")
        st.code(res.get("stdout",""), language="text")
        if res.get("stderr"):
            st.code(res.get("stderr",""), language="text")

        # 実行結果の globals から DataFrame を拾って表示（簡易可視化）
        glb = res.get("globals") or {}
        dfs = []
        for k, v in glb.items():
            if isinstance(v, pd.DataFrame):
                dfs.append((k, v))
        if dfs:
            st.markdown("#### 検出された DataFrame（自動表示）")
            for k, df in dfs[:5]:
                st.markdown(f"**{k}**")
                st.dataframe(df, use_container_width=True, height=260)

# ==========
# Tab: Export（タブ統合→1ファイル出力）
# ==========
with tab_export:
    st.markdown("### 📦 Export（タブ情報を 1 ファイルへ統合）")
    summary: dict = st.session_state.get("summary", {}) or {}
    tables: dict = st.session_state.get("tables", {}) or {}
    code = st.session_state.get("sample_code", "")

    notes = st.text_area("Notes（任意メモ）", value="", height=120)

    if st.button("Build HTML Report", type="primary"):
        with st.status("レポート生成中…", expanded=False):
            # mermaid
            mmd = ""
            if make_mermaid_and_html is not None:
                try:
                    nodes = st.session_state.get("nodes", pd.DataFrame())
                    edges = st.session_state.get("edges", pd.DataFrame())
                    mmd, _ = make_mermaid_and_html(nodes, edges, max_nodes=120)
                except Exception:
                    mmd = ""

            bundle = ReportBundle(
                library=lib_name,
                created_at=pd.Timestamp.now().isoformat(),
                summary=summary,
                tables=tables,
                notes=notes,
                mermaid_mmd=mmd,
                sample_code=code,
                links=[],
            )
            out_path = export_single_html(bundle)
        st.success(f"出力: {out_path}")
        # Streamlit download
        try:
            data = Path(out_path).read_bytes()
            st.download_button("Download HTML", data=data, file_name=Path(out_path).name, mime="text/html")
        except Exception:
            st.warning("ファイルの読み込みに失敗しました（パス権限など）。")

# 最後に state 保存
save_state(ps)
