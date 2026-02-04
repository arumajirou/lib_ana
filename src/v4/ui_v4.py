# ファイルパス: C:\lib_ana\src\ui_v4.py
# （この実行環境では /mnt/data/ui_v4.py に生成しています）
from __future__ import annotations

import base64
import html
from typing import Any, Dict

import ipywidgets as widgets
from IPython.display import display, Markdown, HTML
import pandas as pd
import plotly.express as px

from analyzer_v4 import LibraryAnalyzerV4
from models_v4 import AnalysisConfig
from package_catalog_v4 import build_package_catalog
from mermaid_export_v4 import to_mermaid_flowchart

try:
    from pyvis.network import Network
    _HAS_PYVIS = True
except Exception:
    _HAS_PYVIS = False


class CognitiveLibraryUIV4:
    def __init__(self):
        self.df_nodes = pd.DataFrame()
        self.df_edges = pd.DataFrame()
        self.summary: Dict[str, Any] = {}
        self.lib_name = ""

        # package catalog
        self.catalog = build_package_catalog()
        options = [(f"{it.import_name}   ({it.dist_name} {it.version})", it.import_name) for it in self.catalog]
        options = sorted(options, key=lambda x: x[1].lower())

        self.dd_lib = widgets.Dropdown(
            options=options[:600],
            value="chronos" if any(v == "chronos" for _, v in options) else (options[0][1] if options else ""),
            description="Library:",
            layout=widgets.Layout(width="700px"),
        )
        self.txt_filter = widgets.Text(
            value="",
            placeholder="filter packages (e.g. chrono, pandas, torch)",
            description="Filter:",
            layout=widgets.Layout(width="700px"),
        )
        self.btn_filter = widgets.Button(description="Apply Filter", icon="filter")
        self.btn_filter.on_click(self._on_filter_packages)

        self.sel_multi_libs = widgets.SelectMultiple(
            options=options[:600],
            description="Batch:",
            layout=widgets.Layout(width="700px", height="140px"),
        )

        # analysis controls
        self.dd_api_surface = widgets.Dropdown(
            options=[("module_public (__all__/public)", "module_public"), ("top_level (root only)", "top_level")],
            value="module_public",
            description="API:",
            layout=widgets.Layout(width="360px"),
        )
        self.chk_private = widgets.Checkbox(value=False, description="include private (_*)")
        self.chk_external = widgets.Checkbox(value=False, description="include external re-exports")
        self.chk_inherited = widgets.Checkbox(value=False, description="include inherited members")
        self.chk_related = widgets.Checkbox(value=True, description="add related edges")

        self.btn_analyze = widgets.Button(description="Analyze", button_style="primary", icon="search")
        self.btn_analyze.on_click(self._on_analyze)
        self.btn_batch = widgets.Button(description="Batch Summary", icon="list")
        self.btn_batch.on_click(self._on_batch_summary)

        # reverse lookup
        self.txt_param = widgets.Text(value="", placeholder="param name (e.g. path, df)", description="Arg:")
        self.txt_return = widgets.Text(value="", placeholder="return type (e.g. DataFrame)", description="Ret:")
        self.dd_event = widgets.Dropdown(
            options=[("any", ""), ("load", "load"), ("save", "save"), ("train", "train"), ("predict", "predict"), ("eval", "eval"),
                     ("transform", "transform"), ("plot", "plot"), ("config", "config"), ("build", "build"), ("io", "io"), ("util", "util"), ("other", "other")],
            value="",
            description="Event:"
        )
        self.btn_reverse = widgets.Button(description="Reverse Lookup", icon="search")
        self.btn_reverse.on_click(self._on_reverse_lookup)

        # sorting/grouping
        self.dd_sort = widgets.Dropdown(
            options=[("Name", "Name"), ("LOC", "LOC"), ("ParamCount", "ParamCount")],
            value="Name",
            description="Sort:",
            layout=widgets.Layout(width="260px"),
        )
        self.dd_group = widgets.Dropdown(
            options=[("None", ""), ("Event", "Event"), ("ReturnType", "ReturnType"), ("Module", "Module")],
            value="",
            description="Group:",
            layout=widgets.Layout(width="260px"),
        )
        self.btn_apply_view = widgets.Button(description="Apply View", icon="cog")
        self.btn_apply_view.on_click(self._on_apply_view)

        # navigator
        list_layout = widgets.Layout(width="33%", height="280px")
        self.sel_modules = widgets.Select(options=[], description="1. Modules", layout=list_layout)
        self.sel_level2 = widgets.Select(options=[], description="2. Items", layout=list_layout)
        self.sel_level3 = widgets.Select(options=[], description="3. Members", layout=list_layout)

        self.sel_modules.observe(self._on_module_select, names="value")
        self.sel_level2.observe(self._on_level2_select, names="value")
        self.sel_level3.observe(self._on_level3_select, names="value")

        # outputs
        self.out_dashboard = widgets.Output(layout=widgets.Layout(padding="10px"))
        self.out_viz = widgets.Output(layout=widgets.Layout(padding="10px"))
        self.out_details = widgets.Output(layout=widgets.Layout(padding="10px", border="1px solid #eee"))
        self.out_mermaid = widgets.Output(layout=widgets.Layout(padding="10px"))
        self.tabs = widgets.Tab(children=[self.out_dashboard, self.out_viz, self.out_details, self.out_mermaid])
        self.tabs.set_title(0, "📊 Dashboard")
        self.tabs.set_title(1, "🕸️ Structure Map")
        self.tabs.set_title(2, "🔍 Inspector")
        self.tabs.set_title(3, "🧩 Mermaid(MMD)")

        self.header = widgets.VBox(
            [
                widgets.HTML("<b>🔧 Library Explorer V4</b>"),
                widgets.HBox([self.dd_lib]),
                widgets.HBox([self.txt_filter, self.btn_filter]),
                widgets.HBox([self.sel_multi_libs]),
                widgets.HBox([self.dd_api_surface, self.btn_analyze, self.btn_batch]),
                widgets.HBox([self.chk_private, self.chk_external, self.chk_inherited, self.chk_related]),
                widgets.HBox([self.txt_param, self.txt_return, self.dd_event, self.btn_reverse]),
                widgets.HBox([self.dd_sort, self.dd_group, self.btn_apply_view]),
            ],
            layout=widgets.Layout(padding="10px", border_bottom="1px solid #ddd"),
        )

        self.navigator = widgets.HBox([self.sel_modules, self.sel_level2, self.sel_level3],
                                      layout=widgets.Layout(padding="10px", background_color="#f4f6f9"))
        self.app = widgets.VBox([self.header, self.navigator, widgets.HTML("<hr style='margin:0;'>"), self.tabs])

    def display(self):
        display(self.app)

    def _make_cfg(self) -> AnalysisConfig:
        return AnalysisConfig(
            api_surface=self.dd_api_surface.value,
            include_private=self.chk_private.value,
            include_external_reexports=self.chk_external.value,
            include_inherited_members=self.chk_inherited.value,
            add_related_edges=self.chk_related.value,
        )

    # ---- package filter ----
    def _on_filter_packages(self, _):
        q = (self.txt_filter.value or "").strip().lower()
        items = self.catalog
        if q:
            items = [it for it in items if (q in it.import_name.lower()) or (q in it.dist_name.lower())]
        options = [(f"{it.import_name}   ({it.dist_name} {it.version})", it.import_name) for it in items]
        options = sorted(options, key=lambda x: x[1].lower())
        self.dd_lib.options = options[:1500]
        self.sel_multi_libs.options = options[:1500]

    # ---- analysis ----
    def _on_analyze(self, _):
        self.lib_name = self.dd_lib.value
        self._clear_outputs()

        with self.out_dashboard:
            print(f"🔄 Analyzing '{self.lib_name}' ...")

        analyzer = LibraryAnalyzerV4(self.lib_name, self._make_cfg())
        summary, df_nodes, df_edges, _ = analyzer.analyze()

        self.summary = summary
        self.df_nodes = df_nodes
        self.df_edges = df_edges

        self.out_dashboard.clear_output()
        with self.out_dashboard:
            self._render_dashboard()

        self._refresh_modules()
        self.out_viz.clear_output()
        with self.out_viz:
            self._render_visuals()

        self.out_mermaid.clear_output()
        with self.out_mermaid:
            self._render_mermaid()

        self.tabs.selected_index = 0

    def _on_batch_summary(self, _):
        libs = list(self.sel_multi_libs.value)
        self._clear_outputs()
        with self.out_dashboard:
            if not libs:
                print("No libraries selected in Batch.")
                return
            rows = []
            cfg = self._make_cfg()
            for ln in libs[:30]:
                a = LibraryAnalyzerV4(ln, cfg)
                s, _, _, _ = a.analyze()
                rows.append(s)
            df = pd.DataFrame(rows).sort_values(["Errors", "Modules"], ascending=[True, False])
            display(Markdown("## 📚 Batch Summary (first 30)"))
            display(df)

    def _clear_outputs(self):
        self.out_dashboard.clear_output()
        self.out_viz.clear_output()
        self.out_details.clear_output()
        self.out_mermaid.clear_output()
        self.sel_modules.options = []
        self.sel_level2.options = []
        self.sel_level3.options = []

    # ---- dashboard ----
    def _render_dashboard(self):
        s = self.summary
        card = "flex:1; padding:12px; margin:6px; border-radius:10px; background:#fff; box-shadow:0 2px 6px rgba(0,0,0,0.08); text-align:center;"
        num = "font-size:22px; font-weight:700; margin:2px 0;"
        lab = "color:#666; font-size:12px; text-transform:uppercase;"
        html_content = f"""
        <div style="font-family:sans-serif; background:#fafafa; padding:12px;">
          <h2 style="margin:0 0 8px 0;">📘 {html.escape(s.get('Name',''))} / API={html.escape(s.get('ApiSurface',''))}</h2>
          <div style="display:flex; flex-wrap:wrap;">
            <div style="{card}"><div style="{lab}">Modules</div><div style="{num}">{s.get('Modules')}</div></div>
            <div style="{card}"><div style="{lab}">Classes</div><div style="{num}">{s.get('Classes')}</div></div>
            <div style="{card}"><div style="{lab}">Functions</div><div style="{num}">{s.get('Functions')}</div></div>
            <div style="{card}"><div style="{lab}">Methods/Props</div><div style="{num}">{s.get('Methods/Props')}</div></div>
            <div style="{card}"><div style="{lab}">Unique Arg Names</div><div style="{num}">{s.get('UniqueParamNames')}</div></div>
            <div style="{card}"><div style="{lab}">Unique Return Types</div><div style="{num}">{s.get('UniqueReturnTypes')}</div></div>
            <div style="{card}"><div style="{lab}">External</div><div style="{num}">{s.get('External')}</div></div>
            <div style="{card}"><div style="{lab}">Errors</div><div style="{num}">{s.get('Errors')}</div></div>
          </div>
        </div>
        """
        display(HTML(html_content))

        csv_data = self.df_nodes.to_csv(index=False)
        json_data = self.df_nodes.to_json(orient="records", force_ascii=False)
        edges_json = self.df_edges.to_json(orient="records", force_ascii=False)

        b64_csv = base64.b64encode(csv_data.encode("utf-8")).decode("ascii")
        b64_json = base64.b64encode(json_data.encode("utf-8")).decode("ascii")
        b64_edges = base64.b64encode(edges_json.encode("utf-8")).decode("ascii")

        btns = f"""
        <div style="margin-top: 8px;">
          <a download="{self.lib_name}_nodes.csv" href="data:text/csv;base64,{b64_csv}"
             style="background:#4CAF50;color:white;padding:6px 10px;text-decoration:none;border-radius:6px;">Nodes CSV</a>
          <a download="{self.lib_name}_nodes.json" href="data:application/json;base64,{b64_json}"
             style="background:#2196F3;color:white;padding:6px 10px;text-decoration:none;border-radius:6px;margin-left:8px;">Nodes JSON</a>
          <a download="{self.lib_name}_edges.json" href="data:application/json;base64,{b64_edges}"
             style="background:#9c27b0;color:white;padding:6px 10px;text-decoration:none;border-radius:6px;margin-left:8px;">Edges JSON</a>
        </div>
        """
        display(HTML(btns))

    # ---- navigator ----
    def _refresh_modules(self):
        if self.df_nodes.empty:
            return
        mods = self.df_nodes[self.df_nodes["Type"] == "module"].copy().sort_values("Path")
        self.sel_modules.options = [(r["Path"], r["ID"]) for _, r in mods.iterrows()]
        self.sel_modules.value = None
        self.sel_level2.options = []
        self.sel_level3.options = []

    def _on_apply_view(self, _):
        # Re-apply selection logic (sort/group affects list presentation)
        self._on_module_select({"new": self.sel_modules.value})

    def _sorted_subset(self, df: pd.DataFrame) -> pd.DataFrame:
        if df.empty:
            return df
        d = df.copy()
        d["ParamCount"] = d["ParamNames"].apply(lambda x: len(x) if isinstance(x, list) else 0)
        key = self.dd_sort.value
        if key == "LOC":
            return d.sort_values(["LOC", "Name"], ascending=[False, True])
        if key == "ParamCount":
            return d.sort_values(["ParamCount", "Name"], ascending=[False, True])
        return d.sort_values(["Name"], ascending=[True])

    def _on_module_select(self, change):
        mod_id = change["new"] if isinstance(change, dict) else self.sel_modules.value
        if not mod_id or self.df_nodes.empty:
            return
        subset = self.df_nodes[(self.df_nodes["Parent"] == mod_id) & (self.df_nodes["Type"].isin(["class", "function", "external"]))].copy()
        subset = self._sorted_subset(subset)
        self.sel_level2.options = [(f"{r['Type']}: {r['Name']}", r["ID"]) for _, r in subset.iterrows()]
        self.sel_level2.value = None
        self.sel_level3.options = []
        self._show_details(mod_id)

    def _on_level2_select(self, change):
        node_id = change["new"]
        if not node_id:
            return
        row = self.df_nodes[self.df_nodes["ID"] == node_id]
        if row.empty:
            return
        kind = row.iloc[0]["Type"]
        if kind in ["class", "external"]:
            subset = self.df_nodes[(self.df_nodes["Parent"] == node_id) & (self.df_nodes["Type"].isin(["method", "property"]))].copy()
            subset = self._sorted_subset(subset)
            self.sel_level3.options = [(f"{r['Type']}: {r['Name']}", r["ID"]) for _, r in subset.iterrows()]
            self.sel_level3.value = None
        else:
            self.sel_level3.options = []
        self._show_details(node_id)

    def _on_level3_select(self, change):
        node_id = change["new"]
        if not node_id:
            return
        self._show_details(node_id)

    # ---- reverse lookup ----
    def _on_reverse_lookup(self, _):
        if self.df_nodes.empty:
            return
        arg = (self.txt_param.value or "").strip()
        ret = (self.txt_return.value or "").strip()
        ev = self.dd_event.value

        df = self.df_nodes[self.df_nodes["Type"].isin(["function", "method", "property"])].copy()
        if arg:
            df = df[df["ParamNames"].apply(lambda xs: isinstance(xs, list) and (arg in xs))]
        if ret:
            df = df[df["ReturnType"].astype(str).str.contains(ret, na=False)]
        if ev:
            df = df[df["Events"].apply(lambda xs: isinstance(xs, list) and (ev in xs))]

        df = self._sorted_subset(df).head(300)

        self.out_details.clear_output()
        self.tabs.selected_index = 2
        with self.out_details:
            display(Markdown("## 🔁 Reverse Lookup results"))
            display(Markdown(f"- Arg: `{arg or '∅'}` / Ret: `{ret or '∅'}` / Event: `{ev or 'any'}`"))
            if df.empty:
                display(Markdown("No matches."))
                return
            display(df[["Type", "Path", "Signature", "ReturnType", "Events", "OriginModule"]])

    # ---- details ----
    def _show_details(self, node_id: str):
        self.out_details.clear_output()
        self.tabs.selected_index = 2
        row = self.df_nodes[self.df_nodes["ID"] == node_id]
        if row.empty:
            with self.out_details:
                display(Markdown(f"**No details for** `{node_id}`"))
            return
        r = row.iloc[0]
        icon = {"module": "📦", "class": "💎", "function": "ƒ", "method": "ƒ", "property": "🔑", "external": "🔗"}.get(r["Type"], "🔹")

        with self.out_details:
            display(Markdown(f"# {icon} `{r['Path']}`"))
            display(Markdown(f"**Type:** `{r['Type']}`  \n**Parent:** `{r['Parent']}`  \n**Origin:** `{r['OriginModule']}`"))
            display(Markdown(f"**File:** `{r['OriginFile']}`  \n**LOC:** `{r['LOC']}`"))
            if r["Signature"]:
                display(Markdown("**Signature:**"))
                display(Markdown(f"```python\n{r['Name']}{r['Signature']}\n```"))
            if isinstance(r["ParamNames"], list):
                display(Markdown(f"**Params ({len(r['ParamNames'])}):** `{', '.join(r['ParamNames'][:40])}`"))
            if isinstance(r["ReturnType"], str) and r["ReturnType"]:
                display(Markdown(f"**Return:** `{r['ReturnType']}`"))
            if isinstance(r["Events"], list):
                display(Markdown(f"**Events:** `{', '.join(r['Events'])}`"))
            if r["DocSummary"]:
                display(Markdown("### Description"))
                display(Markdown(f"> {r['DocSummary']}"))

            if self.dd_group.value:
                self._render_group_summary()

    def _render_group_summary(self):
        key = self.dd_group.value
        if not key:
            return
        df = self.df_nodes.copy()
        if key == "Event":
            d = df[df["Type"].isin(["function", "method", "property"])].explode("Events")
            g = d.groupby("Events").size().sort_values(ascending=False).head(30)
            display(Markdown("### 📌 Group: Event (top 30)"))
            display(g)
        elif key == "ReturnType":
            d = df[df["Type"].isin(["function", "method", "property"])]
            g = d.groupby("ReturnType").size().sort_values(ascending=False).head(30)
            display(Markdown("### 📌 Group: ReturnType (top 30)"))
            display(g)
        elif key == "Module":
            g = df.groupby("Module").size().sort_values(ascending=False).head(30)
            display(Markdown("### 📌 Group: Module (top 30)"))
            display(g)

    # ---- visuals ----
    def _render_visuals(self):
        if self.df_nodes.empty:
            return
        display(Markdown("### 🕸️ Structure Map"))
        dfv = self.df_nodes.copy()

        def l1(r):
            return r["Module"] or (r["Path"] if r["Type"] == "module" else "")

        def l2(r):
            if r["Type"] in ["class", "function", "external"]:
                return r["Name"]
            if r["Type"] in ["method", "property"]:
                parent = (r["Parent"] or "").split(".")[-1]
                return parent
            return ""

        def l3(r):
            if r["Type"] in ["method", "property"]:
                return r["Name"]
            return ""

        dfv["L0"] = self.lib_name
        dfv["L1"] = dfv.apply(l1, axis=1)
        dfv["L2"] = dfv.apply(l2, axis=1)
        dfv["L3"] = dfv.apply(l3, axis=1)

        df_plot = dfv[dfv["Type"] != "module"].copy()
        df_plot = df_plot[df_plot["L1"] != ""]

        try:
            fig = px.sunburst(df_plot, path=["L0", "L1", "L2", "L3"], color="Type", height=650)
            fig.show()
        except Exception as e:
            display(Markdown(f"Sunburst failed: `{e}`"))

        if _HAS_PYVIS:
            display(Markdown("### 🧠 Graph (PyVis)"))
            self._render_pyvis_graph(max_nodes=260)

    def _render_pyvis_graph(self, max_nodes: int = 260):
        df = self.df_nodes.copy()
        df["ParamCount"] = df["ParamNames"].apply(lambda x: len(x) if isinstance(x, list) else 0)
        df["Score"] = df["LOC"].fillna(0).astype(float) + df["ParamCount"].astype(float) * 3.0
        mods = df[df["Type"] == "module"]
        others = df[df["Type"] != "module"].sort_values("Score", ascending=False)
        keep = pd.concat([mods, others]).head(max_nodes)
        keep_ids = set(keep["ID"].tolist())

        net = Network(height="600px", width="100%", directed=True, notebook=True)
        for _, r in keep.iterrows():
            title = html.escape(str(r["Path"]))
            label = str(r["Name"])
            net.add_node(r["ID"], label=label, title=title)

        for _, e in self.df_edges.iterrows():
            s, d, rel = e["Src"], e["Dst"], e["Rel"]
            if s in keep_ids and d in keep_ids:
                net.add_edge(s, d, title=str(rel))

        html_path = f"/mnt/data/{self.lib_name}_graph.html"
        net.write_html(html_path, open_browser=False)
        display(HTML(f'<iframe src="{html_path}" width="100%" height="650px"></iframe>'))

    # ---- mermaid ----
    def _render_mermaid(self):
        if self.df_nodes.empty:
            return
        mmd = to_mermaid_flowchart(self.df_nodes, self.df_edges, self.lib_name, max_nodes=260)
        display(Markdown("### 🧩 Mermaid(MMD) code"))
        ta = widgets.Textarea(value=mmd, layout=widgets.Layout(width="100%", height="320px"))
        display(ta)
        b64 = base64.b64encode(mmd.encode("utf-8")).decode("ascii")
        btn = f"""
        <div style="margin-top: 6px;">
          <a download="{self.lib_name}.mmd" href="data:text/plain;base64,{b64}"
             style="background:#263238;color:white;padding:6px 10px;text-decoration:none;border-radius:6px;">Download .mmd</a>
        </div>
        """
        display(HTML(btn))
        display(Markdown("※ 描画は環境依存なので、ここではコード出力＋Structure MapタブのPyVisで可視化します。"))
