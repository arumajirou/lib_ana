# ファイルパス: C:\lib_ana\src\ui_v3.py
# （このノートブック環境では /mnt/data/ui_v3.py に置いています）
from __future__ import annotations

import json
import base64
import html
from typing import Dict, Any, List, Tuple

import ipywidgets as widgets
from IPython.display import display, Markdown, HTML, clear_output
import plotly.express as px
import pandas as pd

from analyzer_v3 import LibraryAnalyzerV3
from models import AnalysisConfig


class CognitiveLibraryUIV3:
    """
    V3の設計思想:
      - ID（完全修飾名）で探索する。Nameだけで検索しない（同名衝突を根絶）
      - module → class/function → method/property の“本当の親子関係”で絞り込む（str.contains禁止）
      - 外部再エクスポート/継承メンバー/プライベート をスイッチで制御
    """

    def __init__(self):
        self.df = pd.DataFrame()
        self.summary: Dict[str, Any] = {}
        self.lib_name = ""

        # ---- controls ----
        self.txt_lib = widgets.Text(
            value="chronos",
            placeholder="Library name (e.g. chronos, pandas)",
            description="Library:",
            layout=widgets.Layout(width="320px"),
        )

        self.chk_private = widgets.Checkbox(value=False, description="include private (_*)")
        self.chk_external = widgets.Checkbox(value=False, description="include external re-exports")
        self.chk_inherited = widgets.Checkbox(value=False, description="include inherited members")

        self.btn_analyze = widgets.Button(description="Analyze", button_style="primary", icon="search")
        self.btn_analyze.on_click(self._on_analyze)

        self.search_box = widgets.Text(
            value="",
            placeholder="search by substring (FQN/Doc)",
            description="Search:",
            layout=widgets.Layout(width="500px"),
        )
        self.btn_search = widgets.Button(description="Find", icon="filter")
        self.btn_search.on_click(self._on_search)

        # ---- navigator ----
        list_layout = widgets.Layout(width="33%", height="260px")
        self.sel_modules = widgets.Select(options=[], description="1. Modules", layout=list_layout)
        self.sel_classes_funcs = widgets.Select(options=[], description="2. Classes/Functions", layout=list_layout)
        self.sel_members = widgets.Select(options=[], description="3. Members", layout=list_layout)

        self.sel_modules.observe(self._on_module_select, names="value")
        self.sel_classes_funcs.observe(self._on_level2_select, names="value")
        self.sel_members.observe(self._on_member_select, names="value")

        # ---- tabs ----
        self.out_dashboard = widgets.Output(layout=widgets.Layout(padding="10px"))
        self.out_viz = widgets.Output(layout=widgets.Layout(padding="10px"))
        self.out_details = widgets.Output(layout=widgets.Layout(padding="10px", border="1px solid #eee"))

        self.tabs = widgets.Tab(children=[self.out_dashboard, self.out_viz, self.out_details])
        self.tabs.set_title(0, "📊 Dashboard")
        self.tabs.set_title(1, "🕸️ Structure Map")
        self.tabs.set_title(2, "🔍 Inspector")

        self.header = widgets.VBox(
            [
                widgets.HBox([self.txt_lib, self.btn_analyze]),
                widgets.HBox([self.chk_private, self.chk_external, self.chk_inherited]),
                widgets.HBox([self.search_box, self.btn_search]),
            ],
            layout=widgets.Layout(padding="10px", border_bottom="1px solid #ddd"),
        )
        self.navigator = widgets.HBox(
            [self.sel_modules, self.sel_classes_funcs, self.sel_members],
            layout=widgets.Layout(padding="10px", background_color="#f4f6f9"),
        )
        self.app = widgets.VBox(
            [
                self.header,
                widgets.HTML("<b>🗂️ Cascade Navigator:</b> module → class/function → member"),
                self.navigator,
                widgets.HTML("<hr style='margin:0;'>"),
                self.tabs,
            ]
        )

    def display(self):
        display(self.app)

    # ---------- analysis ----------

    def _on_analyze(self, _):
        self.lib_name = self.txt_lib.value.strip()
        self._clear_all()

        with self.out_dashboard:
            print(f"🔄 Analyzing '{self.lib_name}' ...")

        cfg = AnalysisConfig(
            include_private=self.chk_private.value,
            include_external_reexports=self.chk_external.value,
            include_inherited_members=self.chk_inherited.value,
        )

        analyzer = LibraryAnalyzerV3(self.lib_name, cfg)
        summary, df, _ = analyzer.analyze()

        if df.empty:
            with self.out_dashboard:
                print("❌ No data. (library not installed / import failed)")
            return

        self.summary = summary
        self.df = df

        # dashboard
        self.out_dashboard.clear_output()
        with self.out_dashboard:
            self._render_dashboard()

        # navigator level1
        self._refresh_modules()

        # viz
        self.out_viz.clear_output()
        with self.out_viz:
            self._render_sunburst()

        self.tabs.selected_index = 0

    def _clear_all(self):
        self.out_dashboard.clear_output()
        self.out_viz.clear_output()
        self.out_details.clear_output()
        self.sel_modules.options = []
        self.sel_classes_funcs.options = []
        self.sel_members.options = []

    # ---------- dashboard ----------

    def _render_dashboard(self):
        s = self.summary
        style_card = "flex:1; padding:12px; margin:6px; border-radius:10px; background:#fff; box-shadow:0 2px 6px rgba(0,0,0,0.08); text-align:center;"
        style_num = "font-size:22px; font-weight:700; margin:2px 0;"
        style_label = "color:#666; font-size:12px; text-transform:uppercase;"
        html_content = f"""
        <div style="font-family:sans-serif; background:#fafafa; padding:12px;">
            <h2 style="margin:0 0 8px 0;">📘 Analysis Report: {html.escape(s.get('Name',''))}</h2>
            <div style="display:flex; flex-direction:row; flex-wrap:wrap;">
                <div style="{style_card}"><div style="{style_label}">Modules</div><div style="{style_num}">{s.get('Modules')}</div></div>
                <div style="{style_card}"><div style="{style_label}">Classes</div><div style="{style_num}">{s.get('Classes')}</div></div>
                <div style="{style_card}"><div style="{style_label}">Functions</div><div style="{style_num}">{s.get('Functions')}</div></div>
                <div style="{style_card}"><div style="{style_label}">Methods/Props</div><div style="{style_num}">{s.get('Methods/Properties')}</div></div>
                <div style="{style_card}"><div style="{style_label}">External</div><div style="{style_num}">{s.get('ExternalReexports')}</div></div>
                <div style="{style_card}"><div style="{style_label}">Errors</div><div style="{style_num}">{s.get('Errors')}</div></div>
            </div>
            <p style="margin-top:8px; color:#555;">
                ※ “External” は外部再エクスポートを含めたときだけ増えます。通常はノイズなのでOFF推奨。
            </p>
        </div>
        """
        display(HTML(html_content))

        # export buttons
        csv_data = self.df.to_csv(index=False)
        json_data = self.df.to_json(orient="records", force_ascii=False)

        b64_csv = base64.b64encode(csv_data.encode("utf-8")).decode("ascii")
        b64_json = base64.b64encode(json_data.encode("utf-8")).decode("ascii")

        safe_csv = html.escape(csv_data[:8000]).replace("\n", r"\n").replace("'", r"\'")

        html_buttons = f"""
            <div style="margin-top: 8px;">
                <a download="{self.lib_name}_analysis.csv" href="data:text/csv;base64,{b64_csv}"
                   style="background-color:#4CAF50;color:white;padding:6px 10px;text-decoration:none;border-radius:6px;">Download CSV</a>
                <a download="{self.lib_name}_analysis.json" href="data:application/json;base64,{b64_json}"
                   style="background-color:#2196F3;color:white;padding:6px 10px;text-decoration:none;border-radius:6px;margin-left:8px;">Download JSON</a>
                <button onclick="navigator.clipboard.writeText('{safe_csv}').then(() => alert('CSV Copied!'))"
                   style="background-color:#ff9800;color:white;padding:6px 10px;border:none;border-radius:6px;margin-left:8px;cursor:pointer;">Copy CSV</button>
            </div>
        """
        display(HTML(html_buttons))

    # ---------- navigator ----------

    def _refresh_modules(self):
        mods = self.df[self.df["Type"] == "module"].copy()
        # option: (label, value=ID)
        options = [(row["Path"], row["ID"]) for _, row in mods.sort_values("Path").iterrows()]
        self.sel_modules.options = options
        self.sel_modules.value = None
        self.sel_classes_funcs.options = []
        self.sel_members.options = []

    def _on_module_select(self, change):
        mod_id = change["new"]
        if not mod_id:
            return

        # module直下の class/function/external を表示
        subset = self.df[(self.df["Parent"] == mod_id) & (self.df["Type"].isin(["class", "function", "external"]))]
        options = [(f"{r['Type']}: {r['Name']}", r["ID"]) for _, r in subset.sort_values(["Type", "Name"]).iterrows()]
        self.sel_classes_funcs.options = options
        self.sel_classes_funcs.value = None
        self.sel_members.options = []

        self._show_details(mod_id)

    def _on_level2_select(self, change):
        node_id = change["new"]
        if not node_id:
            return

        # classならメンバー、functionなら（今はメンバーなし）
        row = self.df[self.df["ID"] == node_id]
        if row.empty:
            return
        kind = row.iloc[0]["Type"]

        if kind in ["class", "external"]:
            subset = self.df[(self.df["Parent"] == node_id) & (self.df["Type"].isin(["method", "property"]))]
            options = [(f"{r['Type']}: {r['Name']}", r["ID"]) for _, r in subset.sort_values(["Type", "Name"]).iterrows()]
            self.sel_members.options = options
            self.sel_members.value = None
        else:
            self.sel_members.options = []

        self._show_details(node_id)

    def _on_member_select(self, change):
        node_id = change["new"]
        if not node_id:
            return
        self._show_details(node_id)

    # ---------- search ----------

    def _on_search(self, _):
        q = self.search_box.value.strip()
        if not q or self.df.empty:
            return

        self.out_details.clear_output()
        self.tabs.selected_index = 2

        # FQN/DocSummary を対象に簡易検索
        mask = self.df["Path"].str.contains(q, na=False) | self.df["DocSummary"].str.contains(q, na=False)
        hits = self.df[mask].sort_values(["Type", "Path"]).head(200)

        with self.out_details:
            display(Markdown(f"## 🔎 Search results: `{q}` ({len(hits)} hits, showing up to 200)"))
            if hits.empty:
                display(Markdown("No matches."))
                return
            display(hits[["Type", "Path", "OriginModule", "OriginFile", "Signature"]])

    # ---------- inspector ----------

    def _show_details(self, node_id: str):
        self.out_details.clear_output()
        self.tabs.selected_index = 2

        row = self.df[self.df["ID"] == node_id]
        if row.empty:
            with self.out_details:
                display(Markdown(f"**Info:** No details for `{node_id}`"))
            return
        r = row.iloc[0]

        icon = {"module": "📦", "class": "💎", "function": "ƒ", "method": "ƒ", "property": "🔑", "external": "🔗"}.get(r["Type"], "🔹")

        with self.out_details:
            display(Markdown(f"# {icon} `{r['Path']}`"))
            display(Markdown(f"**Type:** `{r['Type']}`  \n**Parent:** `{r['Parent']}`"))
            display(Markdown(f"**Origin:** `{r['OriginModule']}`  \n**File:** `{r['OriginFile']}`  \n**LOC:** `{r['LOC']}`"))
            if r["Signature"]:
                display(Markdown(f"**Signature:**\n```python\n{r['Name']}{r['Signature']}\n```"))
            if r["DocSummary"]:
                display(Markdown("### Description"))
                display(Markdown(f"> {r['DocSummary']}"))

    # ---------- visualization ----------

    def _render_sunburst(self):
        if self.df.empty:
            return

        display(Markdown("### 🔭 Structure Map (Sunburst)"))
        display(Markdown("中心=ライブラリ → モジュール → クラス/関数 → メンバー"))

        # 4階層に正規化（欠けは空に）
        dfv = self.df.copy()

        def level1(row):
            # module名（フル）
            if row["Type"] == "module":
                return row["Path"]
            return row["Module"] or ""

        def level2(row):
            if row["Type"] in ["class", "function", "external"]:
                return row["Name"]
            if row["Type"] in ["method", "property"]:
                # 親がクラスFQNなので、クラス名だけ
                parent = row["Parent"].split(".")[-1] if row["Parent"] else ""
                return parent
            return ""

        def level3(row):
            if row["Type"] in ["method", "property"]:
                return row["Name"]
            return ""

        dfv["L0"] = self.lib_name
        dfv["L1"] = dfv.apply(level1, axis=1)
        dfv["L2"] = dfv.apply(level2, axis=1)
        dfv["L3"] = dfv.apply(level3, axis=1)

        # “module行”は可視化を歪めるので落とす（L1として使っているため）
        df_plot = dfv[dfv["Type"] != "module"].copy()
        df_plot = df_plot[df_plot["L1"] != ""]

        fig = px.sunburst(
            df_plot,
            path=["L0", "L1", "L2", "L3"],
            color="Type",
            height=650,
        )
        fig.show()
