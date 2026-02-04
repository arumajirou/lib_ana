# src/ui_v2.py
import ipywidgets as widgets
from IPython.display import display, Markdown, HTML, clear_output
import plotly.express as px
import pandas as pd
from .analyzer_v2 import DeepLibraryAnalyzer


class CognitiveLibraryUI:
    def __init__(self):
        self.analyzer = None
        self.df = pd.DataFrame()
        self.lib_name = ""

        # --- UI Components Definition ---

        # 1. Header Area
        self.txt_input = widgets.Text(
            placeholder="Input Library Name (e.g. chronos)",
            layout=widgets.Layout(width="300px"),
        )
        self.btn_load = widgets.Button(
            description="🚀 Launch Explorer", button_style="primary"
        )
        self.btn_load.on_click(self._on_load)
        self.header = widgets.HBox(
            [self.txt_input, self.btn_load],
            layout=widgets.Layout(padding="10px", border="1px solid #ddd"),
        )

        # 2. Miller Columns (The Cascade Navigation)
        # Level 1: Modules, Level 2: Classes, Level 3: Methods/Functions
        common_layout = widgets.Layout(width="30%", height="300px")
        self.sel_modules = widgets.Select(
            options=[], description="📦 Modules", layout=common_layout
        )
        self.sel_classes = widgets.Select(
            options=[], description="💎 Classes", layout=common_layout
        )
        self.sel_members = widgets.Select(
            options=[], description="ƒ Functions", layout=common_layout
        )

        self.sel_modules.observe(self._on_module_select, names="value")
        self.sel_classes.observe(self._on_class_select, names="value")
        self.sel_members.observe(self._on_member_select, names="value")

        self.columns_ui = widgets.HBox(
            [self.sel_modules, self.sel_classes, self.sel_members]
        )

        # 3. Content Area (Tabs)
        self.out_dashboard = widgets.Output(layout=widgets.Layout(padding="10px"))
        self.out_details = widgets.Output(
            layout=widgets.Layout(padding="10px", border="1px solid #eee")
        )
        self.out_viz = widgets.Output(layout=widgets.Layout(padding="10px"))

        self.tabs = widgets.Tab(
            children=[self.out_dashboard, self.out_viz, self.out_details]
        )
        self.tabs.set_title(0, "📊 Dashboard")
        self.tabs.set_title(1, "🕸️ Structure Map")
        self.tabs.set_title(2, "🔍 Inspector")

        # Main Layout
        self.app_layout = widgets.VBox(
            [
                self.header,
                widgets.HTML("<hr>"),
                widgets.Label(
                    "📁 Navigator (Select to drill down):",
                    style={"font_weight": "bold"},
                ),
                self.columns_ui,
                widgets.HTML("<hr>"),
                self.tabs,
            ]
        )

    def display(self):
        display(self.app_layout)

    def _on_load(self, b):
        self.lib_name = self.txt_input.value
        self.out_dashboard.clear_output()
        self.out_viz.clear_output()

        with self.out_dashboard:
            print(f"Scanning {self.lib_name}...")

        try:
            self.analyzer = DeepLibraryAnalyzer(self.lib_name)
            summary, self.df = self.analyzer.get_library_summary()

            # Update Dashboard
            with self.out_dashboard:
                self.out_dashboard.clear_output()
                self._render_dashboard(summary)

            # Update Navigator (Level 1)
            modules = sorted(
                self.df[self.df["Type"] == "module"]["Name"].unique().tolist()
            )
            self.sel_modules.options = modules

            # Update Visualization
            with self.out_viz:
                self._render_sunburst()

            # Switch to Dashboard tab
            self.tabs.selected_index = 0

        except Exception as e:
            with self.out_dashboard:
                print(f"Error: {e}")

    def _render_dashboard(self, summary):
        """統計カードと基本情報の表示"""
        # HTML/CSS for Cards
        card_style = "border:1px solid #ddd; border-radius:8px; padding:15px; margin:10px; flex:1; text-align:center; box-shadow: 2px 2px 5px rgba(0,0,0,0.1);"

        html = f"""
        <div style="display:flex; flex-direction:row;">
            <div style="{card_style}">
                <h3 style="margin:0; color:#666;">Modules</h3>
                <h1 style="margin:0; color:#2196F3;">{summary.get('Modules', 0)}</h1>
            </div>
            <div style="{card_style}">
                <h3 style="margin:0; color:#666;">Classes</h3>
                <h1 style="margin:0; color:#4CAF50;">{summary.get('Classes', 0)}</h1>
            </div>
            <div style="{card_style}">
                <h3 style="margin:0; color:#666;">Functions</h3>
                <h1 style="margin:0; color:#FF9800;">{summary.get('Functions', 0)}</h1>
            </div>
        </div>
        <div style="padding:15px;">
            <h3>📘 {summary.get('Name')} <span style="font-size:0.6em; color:#888;">v{summary.get('Version')}</span></h3>
            <p><b>File:</b> {summary.get('File')}</p>
            <p><b>Description:</b> {summary.get('Doc')}</p>
        </div>
        """
        display(HTML(html))

    def _render_sunburst(self):
        if self.df.empty:
            return

        # Plotly Sunburst
        fig = px.sunburst(
            self.df,
            path=["Type", "Name"],
            title=f"Composition of {self.lib_name}",
            height=500,
        )
        fig.show()

    # --- Navigation Logic ---
    def _on_module_select(self, change):
        if not change["new"]:
            return
        mod_name = change["new"]

        # Filter Classes belonging to this module
        # Pathが "module.sub.Class" のような形式を想定
        subset = self.df[
            (self.df["Path"].str.contains(mod_name)) & (self.df["Type"] == "class")
        ]
        self.sel_classes.options = sorted(subset["Name"].tolist())
        self.sel_members.options = []  # Clear next level

        # Show module details
        self._show_details(mod_name, "module")

    def _on_class_select(self, change):
        if not change["new"]:
            return
        cls_name = change["new"]

        # Filter Methods belonging to this class
        subset = self.df[
            (self.df["Parent"] == cls_name) & (self.df["Type"] == "method")
        ]
        self.sel_members.options = sorted(subset["Name"].tolist())

        # Show class details
        self._show_details(cls_name, "class")

    def _on_member_select(self, change):
        if not change["new"]:
            return
        mem_name = change["new"]
        self._show_details(mem_name, "method")

    def _show_details(self, name, type_):
        self.tabs.selected_index = 2  # Switch to Inspector tab
        self.out_details.clear_output()

        row = (
            self.df[self.df["Name"] == name].iloc[0]
            if not self.df[self.df["Name"] == name].empty
            else None
        )

        with self.out_details:
            display(Markdown(f"## {name} `({type_})`"))
            if row is not None:
                display(Markdown(f"**Path:** `{row['Path']}`"))
                display(Markdown(f"**Description:**\n> {row['DocSummary']}"))
                if type_ == "class":
                    display(Markdown("### 🧬 Inheritance"))
                    # ここにMermaidを表示可能
                    mmd = f"classDiagram\n class {name}"
                    display(Markdown(f"```mermaid\n{mmd}\n```"))
            else:
                display(Markdown("*No detailed info found.*"))
