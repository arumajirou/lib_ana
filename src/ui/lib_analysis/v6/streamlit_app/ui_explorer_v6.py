# ファイルパス: C:\lib_ana\src\v6\streamlit_app\ui_explorer_v6.py
from __future__ import annotations

import json
import html
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple
from pathlib import Path

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

import plotly.express as px
import plotly.graph_objects as go

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

def _load_library_filter(path_text: str) -> list[str]:
    p = Path(path_text)
    if not p.exists():
        return []
    try:
        payload = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return []
    libs = payload.get("libraries", []) if isinstance(payload, dict) else []
    if not isinstance(libs, list):
        return []
    out: List[str] = []
    seen = set()
    for x in libs:
        s = str(x).strip()
        if not s or s in seen:
            continue
        seen.add(s)
        out.append(s)
    return out


def _style_by_type(df: pd.DataFrame) -> "pd.io.formats.style.Styler":
    if df is None or df.empty or "Type" not in df.columns:
        return df.style

    def _row_style(row):
        t = str(row.get("Type", "")).lower()
        bg = TYPE_COLOR.get(t, "")
        return [f"background-color: {bg}" if bg else "" for _ in row]

    return df.style.apply(_row_style, axis=1)


def _render_df(
    df: pd.DataFrame,
    *,
    color_tables: bool,
    height: int = 360,
    context_label: str = "",
    scope_prefix: str = "",
    key_tag: str = "",
) -> None:
    if df is None or df.empty:
        st.info("データがありません。")
        return
    if color_tables and "Type" in df.columns:
        st.dataframe(_style_by_type(df), width="stretch", height=height)
    else:
        st.dataframe(df, width="stretch", height=height)

    # Copy / Download
    lib = str(st.session_state.get("current_lib") or "library")
    nav_prefix = str(st.session_state.get("nav_prefix") or "")
    effective_prefix = scope_prefix or nav_prefix or "all"
    prefix = effective_prefix.replace(".", "_")
    label = context_label.replace(" ", "_") if context_label else "table"
    safe = lambda s: s.replace("/", "_").replace("\\", "_").replace(":", "_")
    file_base = f"{safe(lib)}_{safe(prefix)}_{safe(label)}"
    key_base = f"{file_base}::{safe(key_tag or scope_prefix or label)}"
    widget_key = f"{key_base}::{id(df)}"

    with st.expander("Copy / Download", expanded=False):
        fmt = st.selectbox(
            "形式",
            ["text", "csv", "json"],
            index=1,
            key=f"copy_fmt::{widget_key}",
        )
        if fmt == "json":
            payload = df.to_json(orient="records", force_ascii=False, indent=2)
        elif fmt == "csv":
            payload = df.to_csv(index=False)
        else:
            payload = df.to_string(index=False)
        st.code(payload, language="text")
        st.download_button(
            "Download table (.csv)",
            data=df.to_csv(index=False),
            file_name=f"{file_base}.csv",
            mime="text/csv",
            key=f"dl::{widget_key}",
        )


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

    _render_df(df, color_tables=False, height=320, context_label="ParamOverlap", scope_prefix=scope_prefix, key_tag="ParamOverlap")

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
    scope_label: str = "",
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
            _render_df(
                dfk,
                color_tables=color_tables,
                height=260,
                context_label=k,
                scope_prefix=prefix,
                key_tag=f"{scope_label}::{k}",
            )

def _render_navigator(
    analysis: Dict[str, Any],
    *,
    color_tables: bool,
    max_items: int,
) -> None:
    nodes: pd.DataFrame = analysis.get("nodes", pd.DataFrame())
    errors: pd.DataFrame = analysis.get("errors", pd.DataFrame())

    st.subheader("🧭 Navigator（Modules → Classes → Functions → Methods/Props → External）")
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

    st.markdown("#### Modules")
    _render_df(
        df_mod.head(max_items),
        color_tables=color_tables,
        height=260,
        context_label="Modules",
        scope_prefix="modules",
        key_tag="Navigator::ModulesTable",
    )
    mod_q = st.text_input("Modules filter（部分一致）", value="", placeholder="例: numpy.linalg", key="mod_q")
    filtered_mods = module_paths
    if mod_q.strip():
        qq = mod_q.strip().lower()
        filtered_mods = [m for m in module_paths if qq in m.lower()]
    if len(filtered_mods) > max_items:
        filtered_mods = filtered_mods[:max_items]
    default_mod_idx = 0
    if st.session_state.get("nav_module") in filtered_mods:
        default_mod_idx = filtered_mods.index(str(st.session_state.get("nav_module")))
    module_sel = st.selectbox("Modules", options=filtered_mods, index=default_mod_idx, key="module_sel")
    st.session_state["nav_module"] = module_sel
    st.session_state["nav_prefix"] = module_sel

    mod_row = df_mod[df_mod["Path"].astype(str) == str(module_sel)].head(1)
    if mod_row.empty:
        st.warning("モジュールが見つかりません。")
        return
    mod_id = str(mod_row.iloc[0].get("ID", ""))

    def _mk_label(df: pd.DataFrame) -> pd.DataFrame:
        if df is None:
            return pd.DataFrame(columns=["LabelBase", "Label"])
        if df.empty:
            out_df = df.copy()
            if "LabelBase" not in out_df.columns:
                out_df["LabelBase"] = pd.Series(dtype="object")
            if "Label" not in out_df.columns:
                out_df["Label"] = pd.Series(dtype="object")
            return out_df
        base_col = "Path" if "Path" in df.columns else "Name"
        out_df = df.copy()
        out_df["LabelBase"] = out_df["Type"].astype(str) + ": " + out_df[base_col].astype(str)
        if dedupe_ui:
            g = out_df.groupby("LabelBase", dropna=False).size().reset_index(name="_dup")
            first = out_df.drop_duplicates(subset=["LabelBase"], keep="first").copy()
            first = first.merge(g, on="LabelBase", how="left")
            first["Label"] = first["LabelBase"] + first["_dup"].apply(lambda n: f" (×{int(n)})" if int(n) > 1 else "")
            return first.drop(columns=["_dup"]).sort_values(["Type", "LabelBase"])
        out_df["Label"] = out_df["LabelBase"]
        return out_df.sort_values(["Type", "LabelBase"])

    scoped = nodes[nodes["Parent"].astype(str) == mod_id].copy()
    df_classes = _mk_label(scoped[scoped["Type"] == "class"].copy())
    df_functions = _mk_label(scoped[scoped["Type"] == "function"].copy())
    df_external = _mk_label(scoped[scoped["Type"] == "external"].copy())

    st.markdown("#### Classes")
    _render_df(
        df_classes.head(max_items),
        color_tables=color_tables,
        height=260,
        context_label="Classes",
        scope_prefix=module_sel,
        key_tag="Navigator::ClassesTable",
    )
    class_labels = ["(skip)"] + df_classes["Label"].tolist()[:max_items]
    class_sel = st.selectbox("Classes", options=class_labels, index=0, key="class_sel")
    class_row = df_classes[df_classes["Label"] == class_sel].head(1) if class_sel != "(skip)" else pd.DataFrame()
    class_id = str(class_row.iloc[0].get("ID", "")) if not class_row.empty else ""

    st.markdown("#### Functions")
    _render_df(
        df_functions.head(max_items),
        color_tables=color_tables,
        height=260,
        context_label="Functions",
        scope_prefix=module_sel,
        key_tag="Navigator::FunctionsTable",
    )
    fn_labels = ["(skip)"] + df_functions["Label"].tolist()[:max_items]
    fn_sel = st.selectbox("Functions", options=fn_labels, index=0, key="function_sel")
    fn_row = df_functions[df_functions["Label"] == fn_sel].head(1) if fn_sel != "(skip)" else pd.DataFrame()
    fn_id = str(fn_row.iloc[0].get("ID", "")) if not fn_row.empty else ""

    st.markdown("#### External")
    _render_df(
        df_external.head(max_items),
        color_tables=color_tables,
        height=260,
        context_label="External",
        scope_prefix=module_sel,
        key_tag="Navigator::ExternalTable",
    )
    ex_labels = ["(skip)"] + df_external["Label"].tolist()[:max_items]
    ex_sel = st.selectbox("External", options=ex_labels, index=0, key="external_sel")
    ex_row = df_external[df_external["Label"] == ex_sel].head(1) if ex_sel != "(skip)" else pd.DataFrame()
    ex_id = str(ex_row.iloc[0].get("ID", "")) if not ex_row.empty else ""

    methods_owner_row = class_row if not class_row.empty else ex_row
    methods_owner_id = class_id or ex_id
    member_id = ""
    if methods_owner_id:
        df_mem = nodes[(nodes["Parent"].astype(str) == methods_owner_id) & (nodes["Type"].isin(["method", "property"]))].copy()
        df_mem = _mk_label(df_mem)
        st.markdown("#### Methods/Props")
        _render_df(
            df_mem.head(max_items),
            color_tables=color_tables,
            height=260,
            context_label="Methods/Props",
            scope_prefix=str(methods_owner_row.iloc[0].get("Path") or module_sel) if not methods_owner_row.empty else module_sel,
            key_tag="Navigator::MethodsPropsTable",
        )
        mem_labels = ["(skip)"] + df_mem["Label"].tolist()[:max_items]
        mem_sel = st.selectbox("Methods/Props", options=mem_labels, index=0, key="mem_sel")
        mem_row = df_mem[df_mem["Label"] == mem_sel].head(1) if mem_sel != "(skip)" else pd.DataFrame()
        member_id = str(mem_row.iloc[0].get("ID", "")) if not mem_row.empty else ""

    target_id = member_id or class_id or fn_id or ex_id or mod_id
    st.session_state["nav_target_id"] = target_id

    trow = nodes[nodes["ID"].astype(str) == str(target_id)].head(1)
    tpath = str(trow.iloc[0].get("Path") or trow.iloc[0].get("Name") or "") if not trow.empty else ""

    st.markdown("#### Inspector（選択中）")
    cols = ["Type", "Name", "Path", "Module", "Role", "EventLike", "NameCluster", "TopGroup"]
    obj = {c: (trow.iloc[0].get(c) if (not trow.empty and c in trow.columns) else None) for c in cols}
    st.write(obj)

    st.divider()
    selected_ids = [x for x in [mod_id, class_id, fn_id, ex_id, member_id] if x]
    _render_param_overlap_table(
        nodes,
        scope_prefix=module_sel,
        selected_ids=selected_ids,
        selected_target_id=target_id,
        max_items=max_items,
    )

    st.divider()
    with st.expander("全体の一覧表（All scope）", expanded=False):
        all_df = nodes.copy()
        if dedupe_ui and not all_df.empty:
            subset = [c for c in ["Type", "Path", "Module", "Name"] if c in all_df.columns]
            if subset:
                all_df = all_df.drop_duplicates(subset=subset, keep="first").copy()
        _render_df(
            all_df.head(max_items),
            color_tables=color_tables,
            height=360,
            context_label="AllNodes",
            scope_prefix="all",
            key_tag="Navigator::AllNodes",
        )

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
        key=f"dl::call_stub::{target_id or 'none'}",
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
    st.download_button("Download Mermaid (.mmd)", data=mmd, file_name="graph.mmd", mime="text/plain", key="dl::mermaid_graph")

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
    st.download_button("Download Sequence (.mmd)", data=seq, file_name="sequence.mmd", mime="text/plain", key="dl::mermaid_seq")

    st.divider()
    st.markdown("### Sunburst（階層の俯瞰）")
    sb = build_sunburst_frame(nodes, prefix=prefix, max_nodes=2500)
    if sb is None or sb.empty:
        st.info("Sunburst用データがありません。")
    else:
        # ids/parents 形式（内部ノードも含む）で描画：path=... の leaf 制約を回避
        fig = px.sunburst(sb, ids="id", names="label", parents="parent", values="count", branchvalues="total")
        st.plotly_chart(fig, width="stretch")

    st.divider()
    st.markdown("### Network（依存/呼び出しグラフ）")
    g, id_to_label, _ = build_scoped_graph(nodes, edges, prefix=prefix, max_nodes=max_nodes, max_edges=max_edges)
    fig2 = _make_network_figure(g, id_to_label)
    if fig2 is None:
        st.info("Networkの生成に失敗しました（networkx未インストール、またはデータ不足）。")
    else:
        st.plotly_chart(fig2, width="stretch")

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
            st.plotly_chart(fig3, width="stretch")

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
    _render_df(pd.DataFrame(rows), color_tables=False, height=260, context_label="Summary", key_tag="Summary")

    metric = st.radio("表を表示（クリック相当）", ["Modules", "Classes", "Functions", "Methods/Props", "External", "Errors"], horizontal=True)
    if metric == "Errors":
        _render_df(errors, color_tables=color_tables, context_label="Errors", scope_prefix="summary", key_tag="SummaryErrors")
    else:
        src_df = tables.get(metric, pd.DataFrame())
        if src_df is None or src_df.empty:
            src_df = tables.get("Methods", pd.DataFrame()) if metric == "Methods/Props" else src_df
        _render_df(src_df, color_tables=color_tables, context_label=metric, scope_prefix="summary", key_tag=f"Summary{metric}")


def _render_param_reverse(analysis: Dict[str, Any]) -> None:
    st.subheader("🧬 引数の逆引き（ParamName → API一覧）")
    param_tables: Dict[str, pd.DataFrame] = analysis.get("param_tables", {}) or {}
    df_map = param_tables.get("ParamMap", pd.DataFrame())
    df_over = param_tables.get("ParamOverview", pd.DataFrame())

    if df_over is None or df_over.empty:
        st.warning("引数情報がありません。Deep param inspect をONにして再解析すると増える場合があります。")
        return

    st.caption("一意引数一覧（頻度順）")
    _render_df(df_over.head(300), color_tables=False, height=320, context_label="ParamOverview", scope_prefix="params", key_tag="ParamOverview")

    df_idx, rev = build_param_reverse_index(df_map)
    q = st.text_input("引数名で検索（部分一致）", value="", placeholder="例: alpha / seed / X / lr …")
    candidates = sorted([k for k in rev.keys() if q.lower() in k.lower()])[:200] if q else sorted(list(rev.keys()))[:200]
    chosen = st.selectbox("ParamName", options=candidates) if candidates else None
    if chosen:
        st.markdown(f"#### 使用箇所 — `{chosen}`")
        _render_df(pd.DataFrame({"API": rev.get(chosen, [])}), color_tables=False, height=360, context_label=f"Param-{chosen}", scope_prefix="params", key_tag=f"Param-{chosen}")

    st.divider()
    st.markdown("#### 引数対応表（ParamMap）")
    _render_df(df_map.head(800), color_tables=False, height=360, context_label="ParamMap", scope_prefix="params", key_tag="ParamMap")


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
    _render_df(df[show_cols].head(min(200, len(df))), color_tables=color_tables, height=320, context_label="SearchResults", scope_prefix=scope_prefix, key_tag="SearchResults")

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
    _render_scope_tables(nodes, errors, prefix=pick, color_tables=color_tables, max_items=max_items, scope_label="SearchPick")

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
    _render_df(neigh.head(200), color_tables=False, height=260, context_label="CallGraphNeighbors", scope_prefix=pick, key_tag="CallGraphNeighbors")

def _render_tables(analysis: Dict[str, Any], *, color_tables: bool) -> None:
    st.subheader("📚 一覧表（分類フィルタ付き）")
    nodes: pd.DataFrame = analysis.get("nodes", pd.DataFrame())
    tables: Dict[str, pd.DataFrame] = analysis.get("tables", {}) or {}

    choice = st.selectbox("表示する表", ["Modules", "Classes", "Functions", "Methods/Props", "External"], index=0)
    df = tables.get(choice, pd.DataFrame()).copy()
    if (df is None or df.empty) and choice == "Methods/Props":
        df = tables.get("Methods", pd.DataFrame()).copy()
    _render_df(df, color_tables=color_tables, height=380, context_label=choice, scope_prefix="tables", key_tag=f"Tables-{choice}")

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
        _render_df(df2, color_tables=color_tables, height=380, context_label=f"{choice}_filtered", scope_prefix="tables", key_tag=f"Tables-{choice}-filtered")


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

    all_libs = list_installed_libraries(limit=2000)
    mode = str(st.session_state.get("library_scope_mode", "全選択"))
    cfg_path = str(st.session_state.get("library_filter_config_path", "configs/library_filter.json"))
    cfg_libs = _load_library_filter(cfg_path)
    libs = all_libs
    if mode == "configのみ":
        cfg_set = set(cfg_libs)
        libs = [x for x in all_libs if x in cfg_set]
        if not libs:
            st.warning("configモードですが表示可能なライブラリがありません。configファイルを確認してください。")

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
        _render_df(dfm, color_tables=False, height=320, context_label="AtlasMetrics", scope_prefix="atlas", key_tag="AtlasMetrics")
        st.markdown("### 共有されやすい引数（Top）")
        if param_rows:
            dfp = pd.DataFrame(param_rows)
            fig = px.bar(dfp, x="ParamName", y="Count", color="Library")
            st.plotly_chart(fig, width="stretch")

    st.divider()
    st.markdown("### semantic cluster（作業仮説：共通機能の塊）")
    st.caption("TF-IDF(文字n-gram) + MiniBatchKMeans による軽量クラスタリング。大規模ライブラリは重いので対象を絞ってください。")
    do_cluster = st.checkbox("クラスタリングを実行する", value=False)
    if do_cluster:
        from v6.core.atlas_features_v6 import build_atlas_table, cluster_nodes_semantic

        # 代表として current_lib だけ表示（複数は重くなりがち）
        name = current_lib
        if not name:
            st.info("現在のLibraryが未選択です。")
            return
        a = _analyze_one(name, deep)
        df_nodes = a.get("nodes", pd.DataFrame())
        atlas_df = build_atlas_table(df_nodes)
        cdf, top_terms = cluster_nodes_semantic(atlas_df, n_clusters=10)
        show = [c for c in ["Cluster", "Type", "Path", "ParamCount", "NameCluster", "Role"] if c in cdf.columns]
        _render_df(cdf[show].head(300), color_tables=False, height=360, context_label="ClusterNodes", scope_prefix="atlas", key_tag="ClusterNodes")
        if top_terms:
            st.markdown("#### クラスタ別：代表n-gram（雰囲気）")
            rows = [{"Cluster": k, "TopTerms": ", ".join(v)} for k, v in sorted(top_terms.items())]
            _render_df(pd.DataFrame(rows), color_tables=False, height=260, context_label="ClusterTopTerms", scope_prefix="atlas", key_tag="ClusterTopTerms")


def _safe_filename(s: str) -> str:
    x = str(s or "").strip()
    if not x:
        return "library"
    return "".join(ch if ch.isalnum() or ch in ("-", "_", ".") else "_" for ch in x)


def _df_to_html_table(df: pd.DataFrame, title: str) -> str:
    if df is None:
        df = pd.DataFrame()
    head = f"<h3>{html.escape(title)} ({len(df)} rows)</h3>"
    if df.empty:
        return head + "<p>(empty)</p>"
    table_html = df.to_html(index=False, border=0, escape=True)
    return head + table_html


def _build_full_report_html(analysis: Dict[str, Any], *, scope_prefix: str = "", max_nodes: int = 300, max_edges: int = 600) -> str:
    lib = str(analysis.get("library", "library"))
    summary = analysis.get("summary", {}) or {}
    nodes: pd.DataFrame = analysis.get("nodes", pd.DataFrame())
    edges: pd.DataFrame = analysis.get("edges", pd.DataFrame())
    errors: pd.DataFrame = analysis.get("errors", pd.DataFrame())
    call_edges: pd.DataFrame = analysis.get("call_edges", pd.DataFrame())
    tables: Dict[str, pd.DataFrame] = analysis.get("tables", {}) or {}
    param_tables: Dict[str, pd.DataFrame] = analysis.get("param_tables", {}) or {}

    # Mermaid code（全体 + 現在スコープ）
    mmd_all = mermaid_flowchart(nodes, edges, prefix="", direction="TD", max_nodes=max_nodes, max_edges=max_edges)
    mmd_scope = mermaid_flowchart(nodes, edges, prefix=scope_prefix, direction="TD", max_nodes=max_nodes, max_edges=max_edges) if scope_prefix else mmd_all

    start_id = str(st.session_state.get("nav_target_id") or "")
    if not start_id and nodes is not None and not nodes.empty and "Type" in nodes.columns:
        cand = nodes[nodes["Type"].isin(["function", "method"])].head(1)
        if not cand.empty:
            start_id = str(cand.iloc[0].get("ID", ""))
    mmd_seq = mermaid_sequence(nodes, edges, start_id=start_id, depth=3, max_steps=80) if start_id else "sequenceDiagram\n  %% no start"

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    summary_df = pd.DataFrame([{"Metric": k, "Value": v} for k, v in summary.items()])

    parts: List[str] = []
    parts.append("<h2>Summary</h2>")
    parts.append(_df_to_html_table(summary_df, "Summary"))

    parts.append("<h2>Split Tables</h2>")
    for name in ["Modules", "Classes", "Functions", "Methods", "Methods/Props", "External"]:
        if name in tables:
            parts.append(_df_to_html_table(tables.get(name, pd.DataFrame()), f"tables.{name}"))

    parts.append("<h2>Param Tables</h2>")
    for name in ["ParamOverview", "ParamMap"]:
        if name in param_tables:
            parts.append(_df_to_html_table(param_tables.get(name, pd.DataFrame()), f"param_tables.{name}"))

    parts.append("<h2>All Analyzed DataFrames</h2>")
    parts.append(_df_to_html_table(nodes, "nodes"))
    parts.append(_df_to_html_table(edges, "edges"))
    parts.append(_df_to_html_table(call_edges, "call_edges"))
    parts.append(_df_to_html_table(errors, "errors"))

    parts.append("<h2>Mermaid Codes (.mmd)</h2>")
    parts.append("<h3>Flowchart (all scope)</h3>")
    parts.append(f"<pre>{html.escape(mmd_all)}</pre>")
    parts.append("<h3>Flowchart (current scope)</h3>")
    parts.append(f"<pre>{html.escape(mmd_scope)}</pre>")
    parts.append("<h3>Sequence</h3>")
    parts.append(f"<pre>{html.escape(mmd_seq)}</pre>")

    parts.append("<h2>Mermaid Preview</h2>")
    parts.append('<div class="mermaid">')
    parts.append(html.escape(mmd_scope))
    parts.append("</div>")
    parts.append('<div class="mermaid">')
    parts.append(html.escape(mmd_seq))
    parts.append("</div>")

    body = "\n".join(parts)
    return f"""<!doctype html>
<html lang="ja">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>CLE V6 Full Report - {html.escape(lib)}</title>
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; margin: 24px; line-height: 1.45; }}
    h1, h2, h3 {{ margin: 0.8em 0 0.35em; }}
    table {{ border-collapse: collapse; width: 100%; margin: 8px 0 18px; font-size: 12px; }}
    th, td {{ border: 1px solid #d9d9d9; padding: 6px 8px; vertical-align: top; }}
    th {{ background: #f7f7f7; position: sticky; top: 0; }}
    pre {{ background: #f6f8fa; border: 1px solid #e5e7eb; padding: 10px; overflow-x: auto; white-space: pre-wrap; }}
    .meta {{ color: #444; margin-bottom: 16px; }}
  </style>
  <script type="module">
    import mermaid from 'https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.esm.min.mjs';
    mermaid.initialize({{ startOnLoad: true, theme: 'default' }});
  </script>
</head>
<body>
  <h1>Cognitive Library Explorer V6 - Full Report</h1>
  <div class="meta">
    <div><b>Library:</b> {html.escape(lib)}</div>
    <div><b>Generated:</b> {html.escape(now)}</div>
    <div><b>Scope prefix:</b> {html.escape(scope_prefix or "(all)")}</div>
  </div>
  {body}
</body>
</html>
"""


def _render_export(analysis: Dict[str, Any]) -> None:
    st.subheader("🗄 Export")
    st.caption("解析済み情報・テーブル・Mermaidコードを1つのHTMLに集約して出力します。")

    prefix = str(st.session_state.get("nav_module") or st.session_state.get("nav_prefix") or "")
    col1, col2 = st.columns(2)
    with col1:
        max_nodes = st.slider("Mermaid max nodes", 50, 500, 300, step=10, key="export_mmd_max_nodes")
    with col2:
        max_edges = st.slider("Mermaid max edges", 100, 2000, 600, step=50, key="export_mmd_max_edges")

    if st.button("Export Full HTML", type="primary", key="export_full_html_btn"):
        report_html = _build_full_report_html(
            analysis,
            scope_prefix=prefix,
            max_nodes=int(max_nodes),
            max_edges=int(max_edges),
        )
        lib = _safe_filename(str(analysis.get("library", "library")))
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        out_dir = Path("outputs/reports_v6")
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / f"cle_v6_full_{lib}_{ts}.html"
        out_path.write_text(report_html, encoding="utf-8")
        st.session_state["export_full_html_content"] = report_html
        st.session_state["export_full_html_path"] = str(out_path)
        st.success(f"保存しました: {out_path}")

    exported = str(st.session_state.get("export_full_html_content") or "")
    exported_path = str(st.session_state.get("export_full_html_path") or "")
    if exported:
        st.download_button(
            "Download Full HTML",
            data=exported,
            file_name=Path(exported_path).name if exported_path else "cle_v6_full_report.html",
            mime="text/html",
            key="export_full_html_download",
        )
        if exported_path:
            st.caption(f"Saved file: {exported_path}")


def render_explorer(analysis: Dict[str, Any]) -> None:
    """CLE V6 のメインUI"""
    lib = analysis.get("library", "")
    color_tables = bool(st.session_state.get("color_tables", False))
    open_new_tab = bool(st.session_state.get("open_new_tab", True))
    enable_online_lookup = bool(st.session_state.get("enable_online_lookup", True))
    max_items = int(st.session_state.get("max_list_items", 500))

    st.session_state["current_lib"] = lib

    tab_nav, tab_search, tab_viz, tab_sum, tab_param, tab_tables, tab_links, tab_atlas, tab_export = st.tabs(
        ["🧭 Navigator", "🔎 Search", "🧠 Visualize", "📊 Summary", "🧬 Param Reverse", "📚 Tables", "🔗 Links", "🌌 Atlas", "🗄 Export"]
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
    with tab_export:
        _render_export(analysis)
