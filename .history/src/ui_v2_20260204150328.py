# ファイルパス: C:\lib_ana\src\ui_v2.py
import ipywidgets as widgets
from IPython.display import display, Markdown, HTML, clear_output
import plotly.express as px
import pandas as pd
import html
import sys

# 相対インポート対策
try:
    from analyzer_v2 import DeepLibraryAnalyzer
except ImportError:
    # srcがパスに入っていない場合のフォールバック
    from src.analyzer_v2 import DeepLibraryAnalyzer


class CognitiveLibraryUI:
    def __init__(self):
        self.analyzer = None
        self.df = pd.DataFrame()
        self.lib_name = ""

        # --- UI Header ---
        self.txt_input = widgets.Text(
            value="chronos",
            placeholder="Library Name",
            description="Library:",
            layout=widgets.Layout(width="250px"),
        )
        self.btn_load = widgets.Button(
            description="Analyze", button_style="primary", icon="search"
        )
        self.btn_load.on_click(self._on_load)

        # --- Cascade Navigators (Miller Columns) ---
        # 3つのリストボックスを配置
        layout_list = widgets.Layout(width="33%", height="300px")

        self.sel_modules = widgets.Select(
            options=[], description="1. Modules", layout=layout_list
        )
        self.sel_classes = widgets.Select(
            options=[], description="2. Classes", layout=layout_list
        )
        self.sel_members = widgets.Select(
            options=[], description="3. Funcs", layout=layout_list
        )

        # イベントハンドラ設定
        self.sel_modules.observe(self._on_module_select, names="value")
        self.sel_classes.observe(self._on_class_select, names="value")
        self.sel_members.observe(self._on_member_select, names="value")

        self.navigator = widgets.HBox(
            [self.sel_modules, self.sel_classes, self.sel_members],
            layout=widgets.Layout(border="1px solid #ddd", padding="5px"),
        )

        # --- Details Tabs ---
        self.out_dashboard = widgets.Output(layout=widgets.Layout(padding="10px"))
        self.out_viz = widgets.Output(layout=widgets.Layout(padding="10px"))
        self.out_details = widgets.Output(
            layout=widgets.Layout(
                padding="10px",
                border="1px solid #ccc",
                height="400px",
                overflow="scroll",
            )
        )

        self.tabs = widgets.Tab(
            children=[self.out_dashboard, self.out_viz, self.out_details]
        )
        self.tabs.set_title(0, "📊 Dashboard")
        self.tabs.set_title(1, "🕸️ Structure Map")
        self.tabs.set_title(2, "🔍 Inspector")

        # --- Main Layout ---
        self.app_layout = widgets.VBox(
            [
                widgets.HBox([self.txt_input, self.btn_load]),
                widgets.HTML("<b>Navigate:</b> Select from left to right."),
                self.navigator,
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
        self.out_details.clear_output()

        # リセット
        self.sel_modules.options = []
        self.sel_classes.options = []
        self.sel_members.options = []

        with self.out_dashboard:
            print(f"Scanning {self.lib_name}...")

        try:
            self.analyzer = DeepLibraryAnalyzer(self.lib_name)
            summary, self.df = self.analyzer.get_library_summary()

            if self.df.empty:
                with self.out_dashboard:
                    print("No data found.")
                return

            # ダッシュボード更新
            with self.out_dashboard:
                self.out_dashboard.clear_output()
                self._render_dashboard(summary)

            # Moduleリスト更新
            # 表示名: Path (一意にするため), 値: Path
            # modules = self.df[self.df['Type'] == 'module'].sort_values('Path')
            # 修正: ルートを含めるため、ParentPathが空のもの or Type=moduleのもの
            modules = self.df[self.df["Type"] == "module"].sort_values("Path")

            # optionsには (Label, Value) のリストを渡す
            # Label=Path (わかりやすい), Value=Path (検索用ID)
            self.sel_modules.options = [(r.Path, r.Path) for r in modules.itertuples()]

            # Visualization更新
            with self.out_viz:
                self._render_sunburst()

            self.tabs.selected_index = 0

        except Exception as e:
            with self.out_dashboard:
                print(f"Error: {e}")

    def _on_module_select(self, change):
        """モジュール選択 -> 所属するクラスを表示"""
        if not change["new"]:
            return
        selected_mod_path = change["new"]

        # フィルタリング: ParentPath が 選ばれたモジュールのPath と一致するもの
        classes = self.df[
            (self.df["ParentPath"] == selected_mod_path) & (self.df["Type"] == "class")
        ].sort_values("Name")

        # Classリスト更新: Label=Name (短い名前), Value=Path (一意なID)
        self.sel_classes.options = [(r.Name, r.Path) for r in classes.itertuples()]
        self.sel_members.options = []  # 3列目をクリア

        # 詳細表示
        self._show_details(selected_mod_path)

    def _on_class_select(self, change):
        """クラス選択 -> 所属するメソッドを表示"""
        if not change["new"]:
            return
        selected_class_path = change["new"]

        # フィルタリング: ParentPath が 選ばれたクラスのPath と一致するもの
        funcs = self.df[
            (self.df["ParentPath"] == selected_class_path)
            & (self.df["Type"].isin(["method", "function"]))
        ].sort_values("Name")

        self.sel_members.options = [(r.Name, r.Path) for r in funcs.itertuples()]

        # 詳細表示
        self._show_details(selected_class_path)

    def _on_member_select(self, change):
        """メンバー選択 -> 詳細表示"""
        if not change["new"]:
            return
        selected_path = change["new"]
        self._show_details(selected_path)

    def _show_details(self, path):
        """Inspectorタブに詳細を表示"""
        self.tabs.selected_index = 2
        self.out_details.clear_output()

        row = self.df[self.df["Path"] == path].iloc[0]

        with self.out_details:
            display(Markdown(f"# {row['Name']}"))
            display(Markdown(f"**Full Path:** `{row['Path']}`"))
            display(Markdown(f"**Type:** `{row['Type']}`"))

            if row["Signature"]:
                display(
                    Markdown(
                        f"### Signature\n```python\n{row['Name']}{row['Signature']}\n```"
                    )
                )

            display(Markdown("### Description"))
            display(Markdown(f"> {row['DocSummary']}"))

            # クラスならMermaid図
            if row["Type"] == "class":
                display(Markdown("### Inheritance Diagram"))
                mmd = f"classDiagram\n class {row['Name']}"
                display(Markdown(f"```mermaid\n{mmd}\n```"))

    def _render_dashboard(self, summary):
        html_code = f"""
        <div style="background:#f0f8ff; padding:15px; border-radius:5px;">
            <h2>📘 {summary['Name']} <span style="font-size:0.6em">v{summary['Version']}</span></h2>
            <p>{summary['Doc']}</p>
            <div style="display:flex; gap:20px; margin-top:10px;">
                <div style="background:white; padding:10px; border-radius:5px; flex:1; text-align:center;">
                    <b>Modules</b><br><span style="font-size:1.5em; color:blue">{summary['Modules']}</span>
                </div>
                <div style="background:white; padding:10px; border-radius:5px; flex:1; text-align:center;">
                    <b>Classes</b><br><span style="font-size:1.5em; color:green">{summary['Classes']}</span>
                </div>
                <div style="background:white; padding:10px; border-radius:5px; flex:1; text-align:center;">
                    <b>Functions</b><br><span style="font-size:1.5em; color:orange">{summary['Functions']}</span>
                </div>
            </div>
        </div>
        """
        display(HTML(html_code))

    def _render_sunburst(self):
        if self.df.empty:
            return
        fig = px.sunburst(
            self.df,
            path=["Type", "Name"],
            title=f"Structure of {self.lib_name}",
            height=500,
        )
        fig.show()
