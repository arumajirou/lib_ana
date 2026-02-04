# ファイルパス: C:\lib_ana\src\ui_v2.py
import ipywidgets as widgets
from IPython.display import display, Markdown, HTML, clear_output
import plotly.express as px
import pandas as pd
import html

# --- 修正箇所: 相対インポート(.)を削除 ---
from analyzer_v2 import DeepLibraryAnalyzer


class CognitiveLibraryUI:
    """
    認知負荷を低減し、直感的な探索を可能にするライブラリエクスプローラーUI
    """

    def __init__(self):
        self.analyzer = None
        self.df = pd.DataFrame()
        self.lib_name = ""

        # --- UI Components ---

        # Header
        self.txt_input = widgets.Text(
            value="chronos",
            placeholder="Library Name (e.g. chronos, pandas)",
            description="Library:",
            layout=widgets.Layout(width="300px"),
        )
        self.btn_load = widgets.Button(
            description="Analyze",
            button_style="primary",
            icon="rocket",
            tooltip="Start Analysis",
        )
        self.btn_load.on_click(self._on_load)

        self.header = widgets.HBox(
            [self.txt_input, self.btn_load],
            layout=widgets.Layout(padding="10px", border_bottom="1px solid #ddd"),
        )

        # Navigator (Miller Columns)
        # モジュール -> クラス -> メソッド の3層構造
        list_layout = widgets.Layout(width="33%", height="250px")
        self.sel_modules = widgets.Select(
            options=[], description="1. Modules", layout=list_layout
        )
        self.sel_classes = widgets.Select(
            options=[], description="2. Classes", layout=list_layout
        )
        self.sel_members = widgets.Select(
            options=[], description="3. Functions", layout=list_layout
        )

        self.sel_modules.observe(self._on_module_select, names="value")
        self.sel_classes.observe(self._on_class_select, names="value")
        self.sel_members.observe(self._on_member_select, names="value")

        self.navigator = widgets.HBox(
            [self.sel_modules, self.sel_classes, self.sel_members],
            layout=widgets.Layout(padding="10px", background_color="#f4f6f9"),
        )

        # Content Tabs
        self.out_dashboard = widgets.Output(layout=widgets.Layout(padding="15px"))
        self.out_viz = widgets.Output(layout=widgets.Layout(padding="10px"))
        self.out_details = widgets.Output(
            layout=widgets.Layout(padding="15px", border="1px solid #eee")
        )

        self.tabs = widgets.Tab(
            children=[self.out_dashboard, self.out_viz, self.out_details]
        )
        self.tabs.set_title(0, "📊 Dashboard (Summary)")
        self.tabs.set_title(1, "🕸️ Structure Map")
        self.tabs.set_title(2, "🔍 Inspector (Details)")

        # Main Container
        self.app_layout = widgets.VBox(
            [
                self.header,
                widgets.HTML(
                    "<b>🗂️ Cascade Navigator:</b> Select items from left to right to drill down."
                ),
                self.navigator,
                widgets.HTML("<hr style='margin:0;'>"),
                self.tabs,
            ]
        )

    def display(self):
        display(self.app_layout)

    def _on_load(self, b):
        self.lib_name = self.txt_input.value
        self.out_dashboard.clear_output()
        self.out_viz.clear_output()
        self.out_details.clear_output()

        # Reset Selectors
        self.sel_modules.options = []
        self.sel_classes.options = []
        self.sel_members.options = []

        with self.out_dashboard:
            print(f"🔄 Scanning library '{self.lib_name}'... This may take a moment.")

        try:
            self.analyzer = DeepLibraryAnalyzer(self.lib_name)
            summary, self.df = self.analyzer.get_library_summary()

            if self.df.empty:
                with self.out_dashboard:
                    print(
                        f"❌ Could not analyze '{self.lib_name}'. Check if it is installed."
                    )
                return

            # 1. Update Dashboard
            self.out_dashboard.clear_output()
            with self.out_dashboard:
                self._render_dashboard(summary)

            # 2. Update Navigator (Level 1)
            modules = sorted(
                self.df[self.df["Type"] == "module"]["Name"].unique().tolist()
            )
            self.sel_modules.options = modules
            if modules:
                self.sel_modules.value = None

            # 3. Update Visualization
            with self.out_viz:
                self._render_sunburst()

            # Default tab
            self.tabs.selected_index = 0

        except Exception as e:
            with self.out_dashboard:
                print(f"❌ Error: {e}")
                import traceback

                traceback.print_exc()

    def _render_dashboard(self, summary):
        """統計情報のダッシュボード表示"""
        style_card = "flex:1; padding:15px; margin:5px; border-radius:8px; background:#fff; box-shadow:0 2px 5px rgba(0,0,0,0.1); text-align:center;"
        style_num = "font-size:24px; font-weight:bold; margin:5px 0;"
        style_label = "color:#666; font-size:12px; text-transform:uppercase;"

        html_content = f"""
        <div style="font-family:sans-serif; background:#fafafa; padding:20px;">
            <h2 style="margin-top:0;">📘 Analysis Report: {summary.get('Name')}</h2>
            <p><b>Version:</b> {summary.get('Version')} | <b>File:</b> {summary.get('File')}</p>
            <p style="background:#e3f2fd; padding:10px; border-radius:4px;">{html.escape(summary.get('Doc', ''))}</p>
            
            <div style="display:flex; flex-direction:row; margin-top:20px;">
                <div style="{style_card} border-left:4px solid #2196F3;">
                    <div style="{style_label}">Modules</div>
                    <div style="{style_num} color:#2196F3;">{summary.get('Modules')}</div>
                </div>
                <div style="{style_card} border-left:4px solid #4CAF50;">
                    <div style="{style_label}">Classes</div>
                    <div style="{style_num} color:#4CAF50;">{summary.get('Classes')}</div>
                </div>
                <div style="{style_card} border-left:4px solid #FF9800;">
                    <div style="{style_label}">Functions/Methods</div>
                    <div style="{style_num} color:#FF9800;">{summary.get('Functions')}</div>
                </div>
            </div>
        </div>
        """
        display(HTML(html_content))

    def _render_sunburst(self):
        if self.df.empty:
            return

        display(Markdown("### 🔭 Library Structure Map"))
        display(Markdown("Click center to zoom out, click sectors to zoom in."))

        # NULL処理とパスの調整
        df_viz = self.df.copy()
        df_viz["Parent"] = df_viz["Parent"].replace("", self.lib_name)

        fig = px.sunburst(
            df_viz,
            path=["Type", "Name"],
            title=f"Hierarchical Structure of {self.lib_name}",
            height=600,
            color="Type",
            color_discrete_map={
                "module": "#636EFA",
                "class": "#EF553B",
                "function": "#00CC96",
                "method": "#AB63FA",
            },
        )
        fig.show()

    # --- Navigation Logic ---
    def _on_module_select(self, change):
        if not change["new"]:
            return
        mod_name = change["new"]

        # Module選択 -> そのModuleに含まれるClassを表示
        # Pathが mod_name を含むものを抽出
        subset = self.df[
            (self.df["Path"].str.contains(mod_name)) & (self.df["Type"] == "class")
        ]
        self.sel_classes.options = sorted(subset["Name"].unique().tolist())
        self.sel_members.options = []  # Reset level 3

        # 詳細表示
        self._show_details(mod_name)

    def _on_class_select(self, change):
        if not change["new"]:
            return
        cls_name = change["new"]

        # Class選択 -> そのClassのMethodを表示
        subset = self.df[
            (self.df["Parent"] == cls_name) & (self.df["Type"] == "method")
        ]
        self.sel_members.options = sorted(subset["Name"].unique().tolist())

        # 詳細表示
        self._show_details(cls_name)

    def _on_member_select(self, change):
        if not change["new"]:
            return
        name = change["new"]
        self._show_details(name)

    def _show_details(self, name):
        """詳細タブ(Inspector)に情報を表示"""
        self.tabs.selected_index = 2
        self.out_details.clear_output()

        # 完全一致で検索（同名がある場合はTypeで優先度をつけるなどのロジックが必要だが簡易化）
        row = (
            self.df[self.df["Name"] == name].iloc[0]
            if not self.df[self.df["Name"] == name].empty
            else None
        )

        with self.out_details:
            if row is None:
                display(Markdown(f"**Info:** No details found for `{name}`"))
                return

            type_icon = {
                "module": "📦",
                "class": "💎",
                "function": "ƒ",
                "method": "ƒ",
            }.get(row["Type"], "🔹")

            display(Markdown(f"# {type_icon} {name}"))
            display(Markdown(f"**Type:** `{row['Type']}` | **Path:** `{row['Path']}`"))

            if row["Signature"]:
                display(
                    Markdown(
                        f"**Signature:**\n```python\n{name}{row['Signature']}\n```"
                    )
                )

            display(Markdown(f"### Description"))
            display(Markdown(f"> {row['DocSummary']}"))

            # クラスの場合、Mermaid図を表示
            if row["Type"] == "class":
                self._render_class_diagram(name)

    def _render_class_diagram(self, class_name):
        display(Markdown("### 🧬 Class Diagram (Mermaid)"))
        # 簡易的な図示
        mmd = f"""
        classDiagram
            class {class_name} {{
                +Methods...
            }}
        """
        display(Markdown(f"```mermaid\n{mmd}\n```"))
        display(
            Markdown(
                "*(Mermaid diagram rendering requires compatible environment extension)*"
            )
        )
