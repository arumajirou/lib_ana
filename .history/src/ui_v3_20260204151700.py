# ファイルパス: C:\lib_ana\src\ui_v3.py
import ipywidgets as widgets
from IPython.display import display, Markdown, HTML, clear_output
import plotly.express as px
import pandas as pd
import html
import sys

# ロジック層のインポート
try:
    from analyzer_v3 import DeepLibraryAnalyzer
except ImportError:
    from src.analyzer_v3 import DeepLibraryAnalyzer


class CognitiveLibraryUI_v3:
    def __init__(self):
        self.analyzer = None
        self.df = pd.DataFrame()
        self.lib_name = ""
        self.installed_libs = DeepLibraryAnalyzer.get_installed_libraries()

        # --- UI Header & Controls ---

        # Library Selector (Combobox for searchability)
        self.combo_lib = widgets.Combobox(
            options=self.installed_libs,
            value="chronos" if "chronos" in self.installed_libs else "",
            placeholder="Type or select library...",
            description="📚 Lib:",
            ensure_option=False,
            layout=widgets.Layout(width="300px"),
        )

        self.btn_load = widgets.Button(
            description="Analyze", button_style="primary", icon="rocket"
        )
        self.btn_load.on_click(self._on_load)

        # Filters & Sorters
        self.chk_public = widgets.Checkbox(
            value=True,
            description="Public Only",
            indent=False,
            layout=widgets.Layout(width="auto"),
        )
        self.chk_modules = widgets.Checkbox(
            value=True,
            description="Modules",
            indent=False,
            layout=widgets.Layout(width="auto"),
        )
        self.drop_sort = widgets.Dropdown(
            options=["Name (A-Z)", "Arg Count (Desc)", "Category"],
            value="Name (A-Z)",
            description="Sort:",
            layout=widgets.Layout(width="180px"),
        )

        # Event handler for filters (updates lists without re-analysis)
        self.chk_public.observe(self._update_navigators, names="value")
        self.drop_sort.observe(self._update_navigators, names="value")

        self.controls = widgets.HBox(
            [
                self.combo_lib,
                self.btn_load,
                widgets.Label(" | "),
                self.chk_public,
                self.drop_sort,
            ],
            layout=widgets.Layout(
                align_items="center",
                padding="10px",
                background_color="#f0f0f0",
                border="1px solid #ccc",
            ),
        )

        # --- Navigators (Miller Columns) ---
        common_layout = widgets.Layout(width="33%", height="350px")
        self.sel_level1 = widgets.Select(description="1. Scope", layout=common_layout)
        self.sel_level2 = widgets.Select(description="2. Group", layout=common_layout)
        self.sel_level3 = widgets.Select(description="3. Item", layout=common_layout)

        self.sel_level1.observe(self._on_level1_select, names="value")
        self.sel_level2.observe(self._on_level2_select, names="value")
        self.sel_level3.observe(self._on_level3_select, names="value")

        self.navigator = widgets.HBox(
            [self.sel_level1, self.sel_level2, self.sel_level3]
        )

        # --- Tabs ---
        self.out_dash = widgets.Output(layout=widgets.Layout(padding="10px"))
        self.out_inspect = widgets.Output(
            layout=widgets.Layout(
                padding="10px",
                border="1px solid #ddd",
                height="500px",
                overflow="scroll",
            )
        )
        self.out_reverse = widgets.Output(layout=widgets.Layout(padding="10px"))
        self.out_viz = widgets.Output(layout=widgets.Layout(padding="10px"))
        self.out_mmd = widgets.Output(layout=widgets.Layout(padding="10px"))

        self.tabs = widgets.Tab(
            children=[
                self.out_dash,
                self.out_inspect,
                self.out_reverse,
                self.out_viz,
                self.out_mmd,
            ]
        )
        self.tabs.set_title(0, "📊 Dashboard")
        self.tabs.set_title(1, "🔍 Inspector")
        self.tabs.set_title(2, "↩️ Reverse Search")
        self.tabs.set_title(3, "🕸️ Structure Map")
        self.tabs.set_title(4, "🧜‍♀️ Mermaid Graph")

        # --- Layout ---
        self.app = widgets.VBox(
            [
                self.controls,
                widgets.HTML("<b>Navigator:</b>"),
                self.navigator,
                widgets.HTML("<hr>"),
                self.tabs,
            ]
        )

    def display(self):
        display(self.app)

    def _on_load(self, b):
        self.lib_name = self.combo_lib.value
        if not self.lib_name:
            return

        self.out_dash.clear_output()
        self.out_inspect.clear_output()
        self.out_reverse.clear_output()
        self.out_viz.clear_output()

        with self.out_dash:
            print(f"Analyzing {self.lib_name}...")

        try:
            self.analyzer = DeepLibraryAnalyzer(self.lib_name)
            summary, self.df = self.analyzer.get_library_summary()

            if self.df.empty:
                with self.out_dash:
                    print("No data found.")
                return

            # Dashboard
            with self.out_dash:
                self.out_dash.clear_output()
                self._render_dashboard(summary)

            # Init Navigator
            self._update_navigators()

            # Visualization
            with self.out_viz:
                self._render_sunburst()

            # Reverse Search Setup
            with self.out_reverse:
                self._render_reverse_search()

            # Mermaid
            with self.out_mmd:
                self._render_mermaid()

            self.tabs.selected_index = 0

        except Exception as e:
            with self.out_dash:
                print(f"Error: {e}")

    def _filter_df(self):
        """現在のフィルター設定に基づいてDFをフィルタリング"""
        if self.df.empty:
            return self.df
        df_filtered = self.df.copy()
        if self.chk_public.value:
            df_filtered = df_filtered[df_filtered["IsPublic"] == True]
        return df_filtered

    def _sort_df(self, df):
        """設定に基づいてソート"""
        sort_mode = self.drop_sort.value
        if sort_mode == "Name (A-Z)":
            return df.sort_values("Name")
        elif sort_mode == "Arg Count (Desc)":
            return df.sort_values("ArgCount", ascending=False)
        elif sort_mode == "Category":
            return df.sort_values("Category")
        return df

    def _update_navigators(self, change=None):
        """ナビゲーター（左端）の更新"""
        if self.df.empty:
            return

        df_sub = self._filter_df()
        # Level 1: Modules (ROOT) or Categories if we implemented categorization grouping
        # ここでは基本としてモジュール階層を表示
        # Root直下のモジュールまたはクラス
        root_items = df_sub[df_sub["ParentPath"] == self.lib_name]
        if root_items.empty:
            root_items = df_sub[df_sub["Type"] == "module"]  # Fallback

        root_items = self._sort_df(root_items)

        # Option format: (Label, Value) -> (Name [Cat], Path)
        options = []
        for row in root_items.itertuples():
            label = f"{row.Name}  ({row.Category})"
            options.append((label, row.Path))

        self.sel_level1.options = options
        self.sel_level2.options = []
        self.sel_level3.options = []

    def _on_level1_select(self, change):
        if not change["new"]:
            return
        path = change["new"]
        self._update_level2(path)
        self._show_details(path)

    def _update_level2(self, parent_path):
        df_sub = self._filter_df()
        items = df_sub[df_sub["ParentPath"] == parent_path]
        items = self._sort_df(items)

        options = []
        for row in items.itertuples():
            label = f"{row.Name}  [{row.Type}]"
            options.append((label, row.Path))
        self.sel_level2.options = options
        self.sel_level3.options = []

    def _on_level2_select(self, change):
        if not change["new"]:
            return
        path = change["new"]
        self._update_level3(path)
        self._show_details(path)

    def _update_level3(self, parent_path):
        df_sub = self._filter_df()
        items = df_sub[df_sub["ParentPath"] == parent_path]
        items = self._sort_df(items)

        options = []
        for row in items.itertuples():
            # Show Arg count in label
            label = f"{row.Name} (args:{row.ArgCount})"
            options.append((label, row.Path))
        self.sel_level3.options = options

    def _on_level3_select(self, change):
        if not change["new"]:
            return
        path = change["new"]
        self._show_details(path)

    def _show_details(self, path):
        self.tabs.selected_index = 1
        self.out_inspect.clear_output()

        row = self.df[self.df["Path"] == path].iloc[0]

        with self.out_inspect:
            display(Markdown(f"# {row['Name']}"))
            display(
                Markdown(
                    f"**Type:** `{row['Type']}` | **Category:** `{row['Category']}`"
                )
            )
            display(Markdown(f"**Args Count:** {row['ArgCount']}"))

            if row["Signature"]:
                display(
                    Markdown(
                        f"### Signature\n```python\n{row['Name']}{row['Signature']}\n```"
                    )
                )

            if row["Return"]:
                display(Markdown(f"**Return Type:** `{row['Return']}`"))

            display(Markdown(f"### Docstring\n> {row['DocSummary']}"))

            # Simple Code Gen
            display(Markdown("### 🛠 Sample Code"))
            code = f"from {'.'.join(row['Path'].split('.')[:-1])} import {row['Name']}\n\n# Usage\nobj = {row['Name']}(...)"
            display(Markdown(f"```python\n{code}\n```"))

    def _render_reverse_search(self):
        """引数名からの逆引き検索UI"""
        txt_arg = widgets.Text(
            placeholder="e.g. prediction_length, input_ids", description="Arg Name:"
        )
        btn_search = widgets.Button(description="Search", icon="search")
        out_res = widgets.Output()

        def run_search(b):
            out_res.clear_output()
            q = txt_arg.value
            if not q:
                return

            # 引数文字列にクエリが含まれる行を検索
            res = self.df[self.df["Args"].str.contains(q, na=False, case=False)]

            with out_res:
                if res.empty:
                    print("No matches found.")
                else:
                    display(Markdown(f"**Found {len(res)} functions using `{q}`:**"))
                    # 必要な列だけ表示
                    display(res[["Name", "Category", "Path", "Args"]])

        btn_search.on_click(run_search)
        txt_arg.on_submit(run_search)

        display(widgets.VBox([widgets.HBox([txt_arg, btn_search]), out_res]))

    def _render_dashboard(self, summary):
        html_code = f"""
        <div style="background:#eef; padding:15px; border-radius:5px;">
            <h2>📘 {summary['Name']} <small>v{summary['Version']}</small></h2>
            <div style="display:flex; justify-content:space-around; margin-top:10px;">
                <div style="text-align:center"><b>Modules</b><h1>{summary['Modules']}</h1></div>
                <div style="text-align:center"><b>Classes</b><h1>{summary['Classes']}</h1></div>
                <div style="text-align:center"><b>Functions</b><h1>{summary['Functions']}</h1></div>
                <div style="text-align:center"><b>Total Args</b><h1>{summary['Total_Args']}</h1></div>
            </div>
        </div>
        """
        display(HTML(html_code))

    def _render_sunburst(self):
        df_viz = self._filter_df()
        fig = px.sunburst(
            df_viz,
            path=["Type", "Category", "Name"],
            title=f"{self.lib_name} Structure by Category",
            height=600,
        )
        fig.show()

    def _render_mermaid(self):
        """Mermaidコード生成と表示"""
        display(Markdown("### Mermaid Class/Flow Diagram"))
        # 簡易的な生成: モジュールごとのクラス図
        # 全体は大きすぎるため、主要なクラスのみ、あるいはカテゴリ別に生成するアイデアもあるが
        # ここでは上位のクラスを抽出

        # Generate Code
        classes = self.df[self.df["Type"] == "class"].head(20)  # Limit for display

        mmd = ["classDiagram"]
        for _, row in classes.iterrows():
            mmd.append(f"    class {row['Name']}")
            # もし継承情報があればここに追加

        mmd_code = "\n".join(mmd)

        # Display Text
        display(Markdown(f"```mermaid\n{mmd_code}\n```"))

        # Copy Button
        display(
            HTML(
                f"""
        <textarea style="width:100%; height:100px;">{mmd_code}</textarea>
        <p>Copy above code to Mermaid Live Editor</p>
        """
            )
        )
