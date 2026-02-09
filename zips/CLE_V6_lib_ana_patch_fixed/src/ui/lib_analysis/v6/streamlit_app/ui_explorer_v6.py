# ファイルパス: C:\lib_ana\src\v6\streamlit_app\ui_explorer_v6.py
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

import plotly.express as px
import plotly.graph_objects as go

from v6.core.hierarchy_v6 import build_options, auto_depth
from v6.core.param_map_v6 import build_param_reverse_index
from v6.core.link_resolver_v6 import (
    lookup_pypi_urls,
    extract_github_urls,
    guess_github_search_url,
    guess_huggingface_search_url,
)
from v6.core.inspect_params_v6 import inspect_params_from_path
from v6.core.codegen_v6 import generate_call_stub
from v6.core.mermaid_v6 import mermaid_flowchart, mermaid_sequence
from v6.core.viz_v6 import (
    build_sunburst_frame,
    extract_unique_param_names,
    extract_unique_return_types,
    filter_errors,
    build_scoped_graph,
)


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
        t = str(row.get("Type", "")).lower()
        bg = TYPE_COLOR.get(t, "")
        return [f"background-color: {bg}" if bg else "" for _ in row]

    return df.style.apply(_row_style, axis=1)


def _render_df(df: pd.DataFrame, *, color_tables: bool, height: int = 360) -> None:
    if df is None or df.empty:
        st.info("データがありません。")
        return
    if color_tables and "Type" in df.columns:
        st.dataframe(_style_by_type(df), use_container_width=True, height=height)
    else:
        st.dataframe(df, use_container_width=True, height=height)


def _filter_nodes_by_prefix(nodes: pd.DataFrame, prefix: str) -> pd.DataFrame:
    if nodes is None or nodes.empty or not prefix:
        return nodes
    p = str(prefix)
    if "Module" in nodes.columns:
        m = nodes["Module"].astype(str).str.startswith(p)
        # module行は Module が空のことがあるので Path も見る
        if "Path" in nodes.columns:
            m = m | nodes["Path"].astype(str).str.startswith(p)
        return nodes[m].copy()
    if "Path" in nodes.columns:
        m = nodes["Path"].astype(str).str.startswith(p)
        return nodes[m].copy()
    return nodes


def _params_obj_to_names(params_obj: Any) -> List[str]:
    """Params列やinspect_paramsの返り値から、引数名のリストを抽出する。"""
    names: List[str] = []
    if params_obj is None:
        return names
    if isinstance(params_obj, list):
        for it in params_obj:
            if isinstance(it, dict) and it.get("name"):
                names.append(str(it["name"]))
            elif isinstance(it, str):
                names.append(it)
    elif isinstance(params_obj, dict):
        for k in params_obj.keys():
            names.append(str(k))
    else:
        return names

    out: List[str] = []
    seen = set()
    for n in names:
        n = str(n).strip()
        if not n or n in seen:
            continue
        seen.add(n)
        out.append(n)
    return out


def _row_for_id(nodes: pd.DataFrame, node_id: str) -> Optional[pd.Series]:
    if nodes is None or nodes.empty:
        return None
    if "ID" not in nodes.columns:
        return None
    m = nodes["ID"].astype(str) == str(node_id)
    r = nodes[m].head(1)
    if r.empty:
        return None
    return r.iloc[0]


def _params_for_id(nodes: pd.DataFrame, node_id: str) -> List[str]:
    """指定IDのParamsを返す。なければinspectで補完する（失敗したら空）。"""
    row = _row_for_id(nodes, node_id)
    if row is None:
        return []
    if "Params" in row and row.get("Params") not in (None, "", [], {}):
        got = _params_obj_to_names(row.get("Params"))
        if got:
            return got
    path = str(row.get("Path") or "")
    if not path:
        return []
    fallback = inspect_params_from_path(path)
    return _params_obj_to_names(fallback)


def _render_param_overlap_table(
    nodes: pd.DataFrame,
    *,
    scope_prefix: str,
    selected_ids: List[str],
    selected_target_id: str,
    max_items: int,
) -> None:
    """選択ターゲットの引数が、同スコープ内の他APIと比べて共通/独自かを可視化する。"""
    st.markdown("##### 引数の共通/独自（選択API vs 同スコープ他API）")

    scoped = _filter_nodes_by_prefix(nodes, scope_prefix)
    if scoped is None or scoped.empty or "Type" not in scoped.columns:
        st.info("データがありません。")
        return

    call_types = {"function", "method", "class", "external", "property"}
    scoped_calls = scoped[scoped["Type"].astype(str).isin(call_types)].copy()
    if scoped_calls.empty:
        st.info("データがありません。")
        return

    selected_params = set(_params_for_id(nodes, selected_target_id))

    others = scoped_calls[~scoped_calls["ID"].astype(str).isin([str(x) for x in selected_ids])].copy()
    others_params_df = extract_unique_param_names(others)
    scope_params_df = extract_unique_param_names(scoped_calls)

    others_params = set(others_params_df["ParamName"].astype(str).tolist()) if not others_params_df.empty else set()
    scope_counts = {str(r["ParamName"]): int(r["Count"]) for _, r in scope_params_df.iterrows()} if not scope_params_df.empty else {}
    others_counts = {str(r["ParamName"]): int(r["Count"]) for _, r in others_params_df.iterrows()} if not others_params_df.empty else {}

    universe = sorted(set(scope_counts.keys()) | set(selected_params) | set(others_counts.keys()))

    rows = []
    for p in universe:
        in_sel = p in selected_params
        in_oth = p in others_params
        if in_sel and in_oth:
            cat = "common"
        elif in_sel and not in_oth:
            cat = "unique_selected"
        elif (not in_sel) and in_oth:
            cat = "unique_others"
        else:
            continue
        rows.append(
            {
                "ParamName": p,
                "Category": cat,
                "InSelected": in_sel,
                "InOthers": in_oth,
                "CountInScope": scope_counts.get(p, 0),
                "CountInOthers": others_counts.get(p, 0),
            }
        )

    if not rows:
        st.info("データがありません。")
        return

    df = pd.DataFrame(rows)
    cat_order = {"common": 0, "unique_selected": 1, "unique_others": 2}
    df["_ord"] = df["Category"].map(cat_order).fillna(9).astype(int)
    df = df.sort_values(["_ord", "CountInScope", "ParamName"], ascending=[True, False, True]).drop(columns=["_ord"])

    if len(df) > max_items:
        df = df.head(max_items)

    _render_df(df, color_tables=False, height=320)

def _render_mermaid(code: str, *, height: int = 620) -> None:
    """Mermaid を Streamlit 内でレンダリングする（外部CDN使用）。"""
    code = (code or "").replace("</script>", "</scr" + "ipt>")
    html = f"""
    <div class="mermaid">{code}</div>
    <script type="module">
      import mermaid from 'https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.esm.min.mjs';
      mermaid.initialize({{ startOnLoad: true, theme: 'default' }});
    </script>
    """
    components.html(html, height=height, scrolling=True)


def _make_network_figure(g, id_to_label: Dict[str, str]) -> Optional[go.Figure]:
    if g is None:
        return None
    try:
        import networkx as nx  # type: ignore
    except Exception:
        return None

    if g.number_of_nodes() == 0:
        return None

    # 座標
    pos = nx.spring_layout(g, seed=42)

    edge_x: List[float] = []
    edge_y: List[float] = []
    for a, b in g.edges():
        x0, y0 = pos[a]
        x1, y1 = pos[b]
        edge_x += [x0, x1, None]
        edge_y += [y0, y1, None]

    node_x: List[float] = []
    node_y: List[float] = []
    texts: List[str] = []
    hover: List[str] = []
    for n in g.nodes():
        x, y = pos[n]
        node_x.append(x)
        node_y.append(y)
        lab = id_to_label.get(str(n), str(n))
        hover.append(lab)
        # text は短め
        texts.append(lab.split(": ")[-1][:30])

    fig = go.Figure()
    fig.add_trace(go.Scatter(x=edge_x, y=edge_y, mode="lines", hoverinfo="none"))
    fig.add_trace(
        go.Scatter(
            x=node_x,
            y=node_y,
            mode="markers+text",
            text=texts,
            hovertext=hover,
            hoverinfo="text",
        )
    )
    fig.update_layout(
        margin=dict(l=10, r=10, t=10, b=10),
        showlegend=False,
        xaxis=dict(visible=False),
        yaxis=dict(visible=False),
    )
    return fig


def _render_scope_tables(
    nodes: pd.DataFrame,
    errors: pd.DataFrame,
    *,
    prefix: str,
    color_tables: bool,
    max_items: int,
) -> None:
    """prefixでスコープを切って、Modules/Classes/Functions/... を“必ず”縦に展開表示する。
    - データがあるものは expanded=True
    - 空のものだけ「データがありません。」を表示（expanded=False）
    """
    scoped = _filter_nodes_by_prefix(nodes, prefix)
    dedupe_ui = bool(st.session_state.get("dedupe_ui", True))
    if dedupe_ui and scoped is not None and not scoped.empty:
        subset = [c for c in ["Type", "Path", "Module", "Name"] if c in scoped.columns]
        if subset:
            scoped = scoped.drop_duplicates(subset=subset, keep="first").copy()

    def cap(df: pd.DataFrame) -> pd.DataFrame:
        return df.head(max_items) if (df is not None and len(df) > max_items) else (df if df is not None else pd.DataFrame())

    if scoped is None or scoped.empty or "Type" not in scoped.columns:
        scoped = pd.DataFrame(columns=list(nodes.columns) if nodes is not None else [])

    tbl: Dict[str, pd.DataFrame] = {
        "Modules": cap(scoped[scoped["Type"] == "module"].copy()) if "Type" in scoped.columns else pd.DataFrame(),
        "Classes": cap(scoped[scoped["Type"] == "class"].copy()) if "Type" in scoped.columns else pd.DataFrame(),
        "Functions": cap(scoped[scoped["Type"] == "function"].copy()) if "Type" in scoped.columns else pd.DataFrame(),
        "Methods/Props": cap(scoped[scoped["Type"].isin(["method", "property"])].copy()) if "Type" in scoped.columns else pd.DataFrame(),
        "External": cap(scoped[scoped["Type"] == "external"].copy()) if "Type" in scoped.columns else pd.DataFrame(),
        "UniqueParamNames": extract_unique_param_names(scoped).head(min(300, max_items)),
        "UniqueReturnTypes": extract_unique_return_types(scoped).head(min(300, max_items)),
        "Errors": cap(filter_errors(errors, prefix=prefix)) if (errors is not None and not errors.empty) else pd.DataFrame(),
    }

    for k in [
        "Modules",
        "Classes",
        "Functions",
        "Methods/Props",
        "External",
        "UniqueParamNames",
        "UniqueReturnTypes",
        "Errors",
    ]:
        dfk = tbl.get(k, pd.DataFrame())
        expanded = (dfk is not None and not dfk.empty)
        with st.expander(k, expanded=expanded):
            _render_df(dfk, color_tables=color_tables, height=260)

def _render_navigator(
    analysis: Dict[str, Any],
    *,
    color_tables: bool,
    max_items: int,
) -> None:
    nodes: pd.DataFrame = analysis.get("nodes", pd.DataFrame())
    errors: pd.DataFrame = analysis.get("errors", pd.DataFrame())

    st.subheader("🧭 Navigator（段階的カスケード＋Inspector＋一覧表）")
    if nodes is None or nodes.empty or "Type" not in nodes.columns:
        st.info("解析結果がありません。")
        return

    dedupe_ui = bool(st.session_state.get("dedupe_ui", True))
    df_mod = nodes[nodes["Type"] == "module"].copy()
    if df_mod.empty:
        st.warning("Modules がありません。")
        return

    df_mod = df_mod.sort_values("Path")
    if dedupe_ui and "Path" in df_mod.columns:
        df_mod = df_mod.drop_duplicates(subset=["Path"], keep="first").copy()
    module_paths = df_mod["Path"].astype(str).tolist()

    inline_tables = st.checkbox("選択の直下に一覧表を自動表示（重い場合はOFF）", value=True, key="inline_tables")

    col1, col2, col3 = st.columns([1, 1, 2])
    with col1:
        auto = st.checkbox("Auto depth", value=True)
    with col2:
        min_depth = st.slider("Min depth", 1, 10, 2)
    with col3:
        max_depth = st.slider("Max depth", 1, 15, 8)

    depth = auto_depth(module_paths, max_depth=max_depth, min_depth=min_depth) if auto else max_depth
    st.caption(f"例: timesfm → flax → dense ...（depth={depth}）")

    selected_levels: List[str] = []
    for lvl in range(depth):
        opts, _ = build_options(module_paths, selected_levels)
        if not opts:
            break

        csel, cnum = st.columns([8, 2])
        with csel:
            pick = st.selectbox(
                f"Level {lvl+1}",
                options=["(stop)"] + opts,
                index=0,
                key=f"lvl_{lvl}",
            )
        with cnum:
            st.markdown(f"**{len(opts)}件**")

        if pick == "(stop)":
            break
        selected_levels.append(pick)

        if inline_tables:
            st.markdown(f"###### Scope（Level {lvl+1}: `{'.'.join(selected_levels)}`）")
            _render_scope_tables(nodes, errors, prefix=".".join(selected_levels), color_tables=color_tables, max_items=max_items)

    prefix = ".".join(selected_levels)
    st.session_state["nav_prefix"] = prefix

    filtered_mods = [m for m in module_paths if m.startswith(prefix)] if prefix else module_paths
    q = st.text_input(
        "Modules filter（部分一致/手入力）",
        value="",
        placeholder="例: common._base_auto / plotting / util ...",
        key="mod_q",
    )
    if q.strip():
        qq = q.strip().lower()
        filtered_mods = [m for m in filtered_mods if qq in m.lower()]
    if len(filtered_mods) > max_items:
        st.warning(f"候補が多いので先頭 {max_items} 件に制限しました（Settingsで変更可）")
        filtered_mods = filtered_mods[:max_items]

    default_idx = 0
    if prefix and prefix in filtered_mods:
        default_idx = filtered_mods.index(prefix)

    cm, cn = st.columns([8, 2])
    with cm:
        module_sel = st.selectbox("Modules", options=filtered_mods, index=default_idx, key="module_sel")
    with cn:
        st.markdown(f"**{len(filtered_mods)}件**")

    st.session_state["nav_module"] = module_sel

    if inline_tables:
        st.markdown(f"###### Scope（Module: `{module_sel}`）")
        _render_scope_tables(nodes, errors, prefix=module_sel, color_tables=color_tables, max_items=max_items)

    mod_row = df_mod[df_mod["Path"].astype(str) == str(module_sel)].head(1)
    if mod_row.empty:
        st.warning("モジュールが見つかりません。")
        return
    mod_id = str(mod_row.iloc[0].get("ID", ""))

    df_items = nodes[(nodes["Parent"].astype(str) == mod_id) & (nodes["Type"].isin(["class", "function", "external"]))].copy()
    if df_items.empty:
        st.caption("Items なし")
        return

    # UIは Path を優先して表示（同名が多いので可読性↑）
    base_col = "Path" if "Path" in df_items.columns else "Name"
    df_items["LabelBase"] = df_items["Type"].astype(str) + ": " + df_items[base_col].astype(str)
    if dedupe_ui:
        g = df_items.groupby("LabelBase", dropna=False).size().reset_index(name="_dup")
        first = df_items.drop_duplicates(subset=["LabelBase"], keep="first").copy()
        first = first.merge(g, on="LabelBase", how="left")
        first["Label"] = first["LabelBase"] + first["_dup"].apply(lambda n: f" (×{int(n)})" if int(n) > 1 else "")
        df_items = first.drop(columns=["_dup"])
    else:
        df_items["Label"] = df_items["LabelBase"]
    df_items = df_items.sort_values(["Type", "LabelBase"])

    item_q = st.text_input("Items filter（部分一致/手入力）", value="", placeholder="例: BaseAuto / heatmap / sobol ...", key="item_q")
    labels = df_items["Label"].tolist()
    if item_q.strip():
        qq = item_q.strip().lower()
        labels = [x for x in labels if qq in x.lower()]
    if len(labels) > max_items:
        labels = labels[:max_items]

    ci, cin = st.columns([8, 2])
    with ci:
        item_sel = st.selectbox("Items（class/function/external）", options=labels, index=0, key="item_sel")
    with cin:
        st.markdown(f"**{len(labels)}件**")

    item_row = df_items[df_items["Label"] == item_sel].head(1)
    node_id = str(item_row.iloc[0].get("ID", "")) if not item_row.empty else ""
    node_type = str(item_row.iloc[0].get("Type", "")) if not item_row.empty else ""

    if inline_tables:
        item_path = str(item_row.iloc[0].get("Path") or "") if not item_row.empty else ""
        if item_path:
            st.markdown(f"###### Scope（Item: `{item_path}`）")
            _render_scope_tables(nodes, errors, prefix=item_path, color_tables=color_tables, max_items=max_items)

    member_id = None
    if node_type in {"class", "external"}:
        df_mem = nodes[(nodes["Parent"].astype(str) == node_id) & (nodes["Type"].isin(["method", "property"]))].copy()
        if not df_mem.empty:
            base_col_m = "Path" if "Path" in df_mem.columns else "Name"
            df_mem["LabelBase"] = df_mem["Type"].astype(str) + ": " + df_mem[base_col_m].astype(str)
            if dedupe_ui:
                g2 = df_mem.groupby("LabelBase", dropna=False).size().reset_index(name="_dup")
                first2 = df_mem.drop_duplicates(subset=["LabelBase"], keep="first").copy()
                first2 = first2.merge(g2, on="LabelBase", how="left")
                first2["Label"] = first2["LabelBase"] + first2["_dup"].apply(lambda n: f" (×{int(n)})" if int(n) > 1 else "")
                df_mem = first2.drop(columns=["_dup"])
            else:
                df_mem["Label"] = df_mem["LabelBase"]
            df_mem = df_mem.sort_values(["Type", "LabelBase"])
            mem_labels = df_mem["Label"].tolist()

            mem_q = st.text_input("Members filter（部分一致）", value="", placeholder="例: fit / plot / to_ ...", key="mem_q")
            if mem_q.strip():
                qq = mem_q.strip().lower()
                mem_labels = [x for x in mem_labels if qq in x.lower()]
            if len(mem_labels) > max_items:
                mem_labels = mem_labels[:max_items]

            cmem, cmemn = st.columns([8, 2])
            with cmem:
                mem_sel = st.selectbox("Members（method/property）", options=mem_labels, index=0, key="mem_sel")
            with cmemn:
                st.markdown(f"**{len(mem_labels)}件**")

            member_row = df_mem[df_mem["Label"] == mem_sel].head(1)
            member_id = str(member_row.iloc[0].get("ID", "")) if not member_row.empty else ""

            if inline_tables:
                mem_path = str(member_row.iloc[0].get("Path") or "") if not member_row.empty else ""
                if mem_path:
                    st.markdown(f"###### Scope（Member: `{mem_path}`）")
                    _render_scope_tables(nodes, errors, prefix=mem_path, color_tables=color_tables, max_items=max_items)

    target_id = member_id or node_id
    st.session_state["nav_target_id"] = target_id

    trow = nodes[nodes["ID"].astype(str) == str(target_id)].head(1)
    tpath = str(trow.iloc[0].get("Path") or trow.iloc[0].get("Name") or "") if not trow.empty else ""

    st.markdown("#### Inspector（選択中）")
    cols = ["Type", "Name", "Path", "Module", "Role", "EventLike", "NameCluster", "TopGroup"]
    obj = {c: (trow.iloc[0].get(c) if (not trow.empty and c in trow.columns) else None) for c in cols}
    st.write(obj)

    st.divider()
    selected_ids = [x for x in [mod_id, node_id, member_id] if x]
    _render_param_overlap_table(
        nodes,
        scope_prefix=module_sel,
        selected_ids=selected_ids,
        selected_target_id=target_id,
        max_items=max_items,
    )

    st.divider()
    st.markdown("### 選択スコープの一覧表（Moduleスコープ）")
    _render_scope_tables(nodes, errors, prefix=module_sel, color_tables=color_tables, max_items=max_items)

    st.divider()
    st.markdown("### 🧾 Codegen（選択APIを“引数全部入り”でコード化）")
    fallback = inspect_params_from_path(tpath) if tpath else None
    code = generate_call_stub(nodes, target_id=target_id, fallback_params=fallback)
    st.code(code, language="python")
    st.download_button(
        "Download call stub (.py)",
        data=code,
        file_name=f"{(tpath or 'call').replace('.', '_')}_call_stub.py",
        mime="text/x-python",
    )

def _render_visualize(analysis: Dict[str, Any]) -> None:
    st.subheader("🧠 Visualize（Mermaid / Sunburst / Network / Sequence）")

    nodes: pd.DataFrame = analysis.get("nodes", pd.DataFrame())
    edges: pd.DataFrame = analysis.get("edges", pd.DataFrame())
    call_edges: pd.DataFrame = analysis.get("call_edges", pd.DataFrame())

    prefix = st.session_state.get("nav_module") or st.session_state.get("nav_prefix") or ""
    prefix = st.text_input("Scope prefix（空=全体）", value=str(prefix), help="例: timesfm.flax")

    colA, colB, colC = st.columns([1, 1, 2])
    with colA:
        max_nodes = st.slider("max nodes", 20, 300, 80, step=10)
    with colB:
        max_edges = st.slider("max edges", 50, 800, 200, step=50)
    with colC:
        direction = st.selectbox("Mermaid direction", ["TD", "LR"], index=0)

    st.divider()
    st.markdown("### Mermaid（flowchart）")
    mmd = mermaid_flowchart(nodes, edges, prefix=prefix, direction=direction, max_nodes=max_nodes, max_edges=max_edges)
    st.code(mmd, language="text")
    _render_mermaid(mmd, height=620)
    st.download_button("Download Mermaid (.mmd)", data=mmd, file_name="graph.mmd", mime="text/plain")

    st.divider()
    st.markdown("### Mermaid（sequenceDiagram）")
    start_id = str(st.session_state.get("nav_target_id") or "")
    if not start_id and nodes is not None and not nodes.empty:
        cand = nodes[nodes["Type"].isin(["function", "method"])].head(200)
        cand = cand.assign(_label=cand["Type"].astype(str) + ": " + cand["Path"].astype(str))
        opt = cand["_label"].tolist()
        pick = st.selectbox("Start", options=opt, index=0)
        start_id = str(cand[cand["_label"] == pick].iloc[0]["ID"]) if opt else ""
    depth = st.slider("sequence depth", 1, 6, 2)
    seq = mermaid_sequence(nodes, edges, start_id=start_id, depth=depth, max_steps=50)
    st.code(seq, language="text")
    _render_mermaid(seq, height=520)
    st.download_button("Download Sequence (.mmd)", data=seq, file_name="sequence.mmd", mime="text/plain")

    st.divider()
    st.markdown("### Sunburst（階層の俯瞰）")
    sb = build_sunburst_frame(nodes, prefix=prefix, max_nodes=2500)
    if sb is None or sb.empty:
        st.info("Sunburst用データがありません。")
    else:
        # ids/parents 形式（内部ノードも含む）で描画：path=... の leaf 制約を回避
        fig = px.sunburst(sb, ids="id", names="label", parents="parent", values="count", branchvalues="total")
        st.plotly_chart(fig, use_container_width=True)

    st.divider()
    st.markdown("### Network（依存/呼び出しグラフ）")
    g, id_to_label, _ = build_scoped_graph(nodes, edges, prefix=prefix, max_nodes=max_nodes, max_edges=max_edges)
    fig2 = _make_network_figure(g, id_to_label)
    if fig2 is None:
        st.info("Networkの生成に失敗しました（networkx未インストール、またはデータ不足）。")
    else:
        st.plotly_chart(fig2, use_container_width=True)

    st.divider()
    st.markdown("### Call Graph（AST / 推定）")
    if call_edges is None or call_edges.empty:
        st.info("Call Graph がありません（Analyze時にAST Call GraphをONにしてください）。")
    else:
        g3, id_to_label3, _ = build_scoped_graph(nodes, call_edges, prefix=prefix, max_nodes=max_nodes, max_edges=max_edges)
        fig3 = _make_network_figure(g3, id_to_label3)
        if fig3 is None:
            st.info("Call Graphの生成に失敗しました（networkx未インストール、またはデータ不足）。")
        else:
            st.plotly_chart(fig3, use_container_width=True)

def _render_summary(analysis: Dict[str, Any], *, color_tables: bool) -> None:
    lib = analysis.get("library", "")
    summary = analysis.get("summary", {}) or {}
    tables: Dict[str, pd.DataFrame] = analysis.get("tables", {}) or {}
    errors: pd.DataFrame = analysis.get("errors", pd.DataFrame())

    st.subheader(f"📊 Summary — {lib}")
    preferred = [
        "Modules",
        "Classes",
        "Functions",
        "Methods/Props",
        "External",
        "UniqueParamNames",
        "UniqueReturnTypes",
        "Errors",
    ]
    rows = [{"Metric": k, "Value": summary.get(k, 0)} for k in preferred]
    st.dataframe(pd.DataFrame(rows), use_container_width=True, height=260)

    metric = st.radio("表を表示（クリック相当）", ["Modules", "Classes", "Functions", "Methods", "External", "Errors"], horizontal=True)
    if metric == "Errors":
        _render_df(errors, color_tables=color_tables)
    else:
        _render_df(tables.get(metric, pd.DataFrame()), color_tables=color_tables)


def _render_param_reverse(analysis: Dict[str, Any]) -> None:
    st.subheader("🧬 引数の逆引き（ParamName → API一覧）")
    param_tables: Dict[str, pd.DataFrame] = analysis.get("param_tables", {}) or {}
    df_map = param_tables.get("ParamMap", pd.DataFrame())
    df_over = param_tables.get("ParamOverview", pd.DataFrame())

    if df_over is None or df_over.empty:
        st.warning("引数情報がありません。Deep param inspect をONにして再解析すると増える場合があります。")
        return

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


def _render_search(analysis: Dict[str, Any], *, color_tables: bool, max_items: int) -> None:
    st.subheader("🔎 Search（文字 / 曖昧 / 意味）")
    st.caption("検索結果から対象APIを選び、Inspector/Codegen/CallGraphまで一気に辿れます。")

    nodes: pd.DataFrame = analysis.get("nodes", pd.DataFrame())
    errors: pd.DataFrame = analysis.get("errors", pd.DataFrame())
    call_edges: pd.DataFrame = analysis.get("call_edges", pd.DataFrame())

    if nodes is None or nodes.empty:
        st.info("解析結果がありません。")
        return

    q = st.text_input("Query", value="", placeholder="例: fit, tokenizer, attention, plot, 正規化 ...")
    mode = st.radio("Mode", ["text", "fuzzy", "semantic"], horizontal=True, index=2)

    prefix = st.session_state.get("nav_module") or st.session_state.get("nav_prefix") or ""
    scope_prefix = st.text_input("Scope prefix（空=全体）", value=str(prefix), help="例: timesfm.flax / sklearn.model_selection")

    scoped = _filter_nodes_by_prefix(nodes, scope_prefix) if scope_prefix else nodes

    if not q.strip():
        st.info("クエリを入力してください。")
        return

    # 検索（重さ対策：上位だけ）
    if mode == "text":
        from v6.core.search_v6 import search_nodes_text
        df = search_nodes_text(scoped, q, limit=min(500, max_items))
    elif mode == "fuzzy":
        from v6.core.search_v6 import search_nodes_fuzzy
        df = search_nodes_fuzzy(scoped, q, limit=min(200, max_items))
    else:
        from v6.core.semantic_index_v6 import build_tfidf_index, query_tfidf_index
        idx = build_tfidf_index(scoped)
        df = query_tfidf_index(idx, q, top_k=min(200, max_items)) if idx is not None else pd.DataFrame()

    if df is None or df.empty:
        st.warning("一致する候補がありません。")
        return

    show_cols = [c for c in ["Score", "Type", "Path", "Name", "Module"] if c in df.columns]
    st.dataframe(df[show_cols].head(min(200, len(df))), use_container_width=True, height=320)

    # 1件選択して深掘り
    if "Path" not in df.columns or df["Path"].dropna().empty:
        st.info("Path列が無いため、選択深掘りは省略します。")
        return

    opts = df["Path"].dropna().astype(str).head(200).tolist()
    pick = st.selectbox("Pick one", options=opts, index=0)

    row = nodes[nodes["Path"].astype(str) == str(pick)].head(1)
    if row.empty:
        st.warning("選択ノードが見つかりません。")
        return

    target_id = str(row.iloc[0].get("ID", ""))
    st.session_state["nav_target_id"] = target_id

    st.divider()
    st.markdown("#### Inspector（検索結果）")
    cols = ["Type", "Name", "Path", "Module", "Role", "EventLike", "NameCluster", "TopGroup"]
    obj = {c: (row.iloc[0].get(c) if c in row.columns else None) for c in cols}
    st.write(obj)

    st.markdown(f"###### Scope（Search pick: `{pick}`）")
    _render_scope_tables(nodes, errors, prefix=pick, color_tables=color_tables, max_items=max_items)

    st.divider()
    st.markdown("### 🧾 Codegen（検索で選んだAPI）")
    fallback = inspect_params_from_path(pick)
    code = generate_call_stub(nodes, target_id=target_id, fallback_params=fallback)
    st.code(code, language="python")

    st.divider()
    st.markdown("### Call Graph（AST / 推定）")
    if call_edges is None or call_edges.empty:
        st.info("Call Graph がありません（Analyze時にAST Call GraphをONにしてください）。")
        return

    # 近傍を抽出
    ce = call_edges.copy()
    # Caller/Callee は ID か Path（解決できない時）なので両方見る
    tid = str(target_id)
    neigh = ce[(ce["Caller"].astype(str) == tid) | (ce["Callee"].astype(str) == tid)].copy()
    if neigh.empty:
        st.info("このAPIの近傍エッジが見つかりません。")
        return
    _render_df(neigh.head(200), color_tables=False, height=260)

def _render_tables(analysis: Dict[str, Any], *, color_tables: bool) -> None:
    st.subheader("📚 一覧表（分類フィルタ付き）")
    nodes: pd.DataFrame = analysis.get("nodes", pd.DataFrame())
    tables: Dict[str, pd.DataFrame] = analysis.get("tables", {}) or {}

    choice = st.selectbox("表示する表", ["Modules", "Classes", "Functions", "Methods", "External"], index=0)
    df = tables.get(choice, pd.DataFrame()).copy()
    _render_df(df, color_tables=color_tables, height=380)

    if nodes is not None and not nodes.empty and "Role" in nodes.columns:
        st.markdown("#### 分類フィルタ")
        roles = sorted({str(x) for x in nodes["Role"].dropna().unique()})
        role = st.selectbox("Role(機能分類)", options=["(all)"] + roles, index=0)
        ev = st.selectbox("EventLike(イベント系)", options=["(all)", "True", "False"], index=0)
        df2 = df.copy()
        if not df2.empty and role != "(all)" and "Role" in df2.columns:
            df2 = df2[df2["Role"] == role]
        if not df2.empty and ev != "(all)" and "EventLike" in df2.columns:
            df2 = df2[df2["EventLike"].astype(bool) == (ev == "True")]
        _render_df(df2, color_tables=color_tables, height=380)


def _render_links(analysis: Dict[str, Any], *, open_new_tab: bool, enable_online_lookup: bool) -> None:
    lib = analysis.get("library", "")
    st.subheader("🔗 PyPI / GitHub / HuggingFace へのリンク")
    pkg = st.text_input("Package name（PyPI名）", value=lib)
    if not enable_online_lookup:
        st.info("オンライン探索がOFFです。")
        return

    if st.button("Search URLs"):
        urls = lookup_pypi_urls(pkg)
        st.write(urls if urls else {"warning": "PyPIから取得できません（名前違い/制限/ネットワーク）"})

        gh = extract_github_urls(urls) if urls else []
        st.write(
            {
                "PyPI": f"https://pypi.org/project/{pkg}/",
                "GitHub search": guess_github_search_url(pkg),
                "HuggingFace search": guess_huggingface_search_url(pkg),
                "GitHub urls": gh,
            }
        )

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


def _render_library_atlas(current_lib: str) -> None:
    """複数ライブラリをまとめて眺める“探索的”タブ（軽量版）。"""
    st.subheader("🌌 Library Atlas（複数ライブラリの特徴比較）")
    st.caption("※ 解析エンジン(v4/v5)がローカルに存在する環境で動く想定です。")

    from v6.core.analyzer_service_v6 import list_installed_libraries, analyze_library_with_progress

    libs = list_installed_libraries(limit=2000)
    default = [current_lib] if current_lib in libs else ([] if not libs else [libs[0]])
    selected = st.multiselect("Libraries", options=libs, default=default)
    deep = st.checkbox("Deep param inspect", value=False)

    @st.cache_data(show_spinner=False)
    def _analyze_one(name: str, deep_param_inspect: bool) -> Dict[str, Any]:
        return analyze_library_with_progress(name, deep_param_inspect=deep_param_inspect)

    if st.button("Batch Analyze") and selected:
        rows: List[Dict[str, Any]] = []
        param_rows: List[Dict[str, Any]] = []

        for n in selected:
            a = _analyze_one(n, deep)
            s = a.get("summary", {}) or {}
            rows.append(
                {
                    "Library": n,
                    "Modules": s.get("Modules", 0),
                    "Classes": s.get("Classes", 0),
                    "Functions": s.get("Functions", 0),
                    "Methods/Props": s.get("Methods/Props", s.get("Methods", 0)),
                    "External": s.get("External", 0),
                    "Errors": s.get("Errors", 0),
                }
            )

            df_nodes = a.get("nodes", pd.DataFrame())
            top = extract_unique_param_names(df_nodes).head(20)
            for _, r in top.iterrows():
                param_rows.append({"Library": n, "ParamName": r["ParamName"], "Count": int(r["Count"])})

        st.markdown("### メトリクス")
        dfm = pd.DataFrame(rows).sort_values("Library")
        st.dataframe(dfm, use_container_width=True, height=320)

st.divider()
st.markdown("### semantic cluster（作業仮説：共通機能の塊）")
st.caption("TF-IDF(文字n-gram) + MiniBatchKMeans による軽量クラスタリング。大規模ライブラリは重いので対象を絞ってください。")
do_cluster = st.checkbox("クラスタリングを実行する", value=False)
if do_cluster:
    from v6.core.atlas_features_v6 import build_atlas_table, cluster_nodes_semantic
    # 代表として current_lib だけ表示（複数は重くなりがち）
    name = current_lib
    a = _analyze_one(name, deep)
    df_nodes = a.get("nodes", pd.DataFrame())
    atlas_df = build_atlas_table(df_nodes)
    cdf, top_terms = cluster_nodes_semantic(atlas_df, n_clusters=10)
    show = [c for c in ["Cluster","Type","Path","ParamCount","NameCluster","Role"] if c in cdf.columns]
    st.dataframe(cdf[show].head(300), use_container_width=True, height=360)
    if top_terms:
        st.markdown("#### クラスタ別：代表n-gram（雰囲気）")
        rows = [{"Cluster": k, "TopTerms": ", ".join(v)} for k, v in sorted(top_terms.items())]
        st.dataframe(pd.DataFrame(rows), use_container_width=True, height=260)

        st.markdown("### 共有されやすい引数（Top）")
        if param_rows:
            dfp = pd.DataFrame(param_rows)
            fig = px.bar(dfp, x="ParamName", y="Count", color="Library")
            st.plotly_chart(fig, use_container_width=True)


def render_explorer(analysis: Dict[str, Any]) -> None:
    """CLE V6 のメインUI"""
    lib = analysis.get("library", "")
    color_tables = bool(st.session_state.get("color_tables", False))
    open_new_tab = bool(st.session_state.get("open_new_tab", True))
    enable_online_lookup = bool(st.session_state.get("enable_online_lookup", True))
    max_items = int(st.session_state.get("max_list_items", 500))

    view = st.radio("表示モード", ["タブ", "シングルページ"], horizontal=True, index=0)

    if view == "シングルページ":
        _render_navigator(analysis, color_tables=color_tables, max_items=max_items)
        st.divider()
        _render_search(analysis, color_tables=color_tables, max_items=max_items)
        st.divider()
        _render_visualize(analysis)
        st.divider()
        _render_summary(analysis, color_tables=color_tables)
        st.divider()
        _render_param_reverse(analysis)
        st.divider()
        _render_tables(analysis, color_tables=color_tables)
        st.divider()
        _render_links(analysis, open_new_tab=open_new_tab, enable_online_lookup=enable_online_lookup)
        st.divider()
        _render_library_atlas(current_lib=lib)
        return

    tab_nav, tab_search, tab_viz, tab_sum, tab_param, tab_tables, tab_links, tab_atlas = st.tabs(
        ["🧭 Navigator", "🔎 Search", "🧠 Visualize", "📊 Summary", "🧬 Param Reverse", "📚 Tables", "🔗 Links", "🌌 Atlas"]
    )

    with tab_nav:
        _render_navigator(analysis, color_tables=color_tables, max_items=max_items)
    with tab_search:
        _render_search(analysis, color_tables=color_tables, max_items=max_items)
    with tab_viz:
        _render_visualize(analysis)
    with tab_sum:
        _render_summary(analysis, color_tables=color_tables)
    with tab_param:
        _render_param_reverse(analysis)
    with tab_tables:
        _render_tables(analysis, color_tables=color_tables)
    with tab_links:
        _render_links(analysis, open_new_tab=open_new_tab, enable_online_lookup=enable_online_lookup)
    with tab_atlas:
        _render_library_atlas(current_lib=lib)
