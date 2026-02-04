# ファイルパス: C:\lib_ana\src\ui_v2.py
import ipywidgets as widgets
from IPython.display import display, Markdown, HTML, clear_output
import plotly.express as px
import pandas as pd
import html
import re
import sys

# 相対インポート対策
try:
    from analyzer_v2 import DeepLibraryAnalyzer
except ImportError:
    from src.analyzer_v2 import DeepLibraryAnalyzer


class CognitiveLibraryUI:
    """
    コピー機能、サンプルコード生成機能、カスケードナビゲーションを備えた
    統合ライブラリエクスプローラーUI
    """

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
            description="Analyze",
            button_style="primary",
            icon="rocket",
            tooltip="Run Analysis",
        )
        self.btn_load.on_click(self._on_load)

        self.header = widgets.HBox(
            [self.txt_input, self.btn_load],
            layout=widgets.Layout(padding="10px", border_bottom="1px solid #ddd"),
        )

        # --- Cascade Navigators (Miller Columns) ---
        layout_list = widgets.Layout(width="33%", height="300px")

        self.sel_modules = widgets.Select(
            options=[], description="1. Modules", layout=layout_list
        )
        self.sel_classes = widgets.Select(
            options=[], description="2. Classes", layout=layout_list
        )
        self.sel_members = widgets.Select(
            options=[], description="3. Functions", layout=layout_list
        )

        self.sel_modules.observe(self._on_module_select, names="value")
        self.sel_classes.observe(self._on_class_select, names="value")
        self.sel_members.observe(self._on_member_select, names="value")

        self.navigator = widgets.HBox(
            [self.sel_modules, self.sel_classes, self.sel_members],
            layout=widgets.Layout(
                border="1px solid #ddd", padding="5px", background_color="#f8f9fa"
            ),
        )

        # --- Content Tabs ---
        self.out_dashboard = widgets.Output(layout=widgets.Layout(padding="15px"))
        self.out_viz = widgets.Output(layout=widgets.Layout(padding="10px"))
        self.out_details = widgets.Output(
            layout=widgets.Layout(
                padding="15px",
                border="1px solid #eee",
                height="500px",
                overflow="scroll",
            )
        )
        self.out_table = widgets.Output(layout=widgets.Layout(padding="10px"))

        self.tabs = widgets.Tab(
            children=[
                self.out_dashboard,
                self.out_viz,
                self.out_details,
                self.out_table,
            ]
        )
        self.tabs.set_title(0, "📊 Dashboard")
        self.tabs.set_title(1, "🕸️ Structure Map")
        self.tabs.set_title(2, "🔍 Inspector & Code")
        self.tabs.set_title(3, "📑 Data Table")

        # --- Main Layout ---
        self.app_layout = widgets.VBox(
            [
                self.header,
                widgets.HTML(
                    "<b>🗂️ Cascade Navigator:</b> Drill down to generate sample code."
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
        self._clear_outputs()

        with self.out_dashboard:
            print(f"🔄 Scanning library '{self.lib_name}'... Please wait.")

        try:
            self.analyzer = DeepLibraryAnalyzer(self.lib_name)
            summary, self.df = self.analyzer.get_library_summary()

            if self.df.empty:
                with self.out_dashboard:
                    print("❌ No data found. Is the library installed?")
                return

            # 1. Update Dashboard
            self.out_dashboard.clear_output()
            with self.out_dashboard:
                self._render_dashboard(summary)

            # 2. Update Navigator (Modules)
            modules = self.df[self.df["Type"] == "module"].sort_values("Path")
            self.sel_modules.options = [(r.Path, r.Path) for r in modules.itertuples()]

            # 3. Update Visualization
            with self.out_viz:
                self._render_sunburst()

            # 4. Update Data Table
            with self.out_table:
                self._render_datatable()

            self.tabs.selected_index = 0

        except Exception as e:
            with self.out_dashboard:
                print(f"❌ Error: {e}")
            import traceback

            traceback.print_exc()

    def _clear_outputs(self):
        self.out_dashboard.clear_output()
        self.out_viz.clear_output()
        self.out_details.clear_output()
        self.out_table.clear_output()
        self.sel_modules.options = []
        self.sel_classes.options = []
        self.sel_members.options = []

    # --- Navigation Events ---
    def _on_module_select(self, change):
        if not change["new"]:
            return
        path = change["new"]
        # Filter Classes
        classes = self.df[
            (self.df["ParentPath"] == path) & (self.df["Type"] == "class")
        ].sort_values("Name")
        self.sel_classes.options = [(r.Name, r.Path) for r in classes.itertuples()]
        self.sel_members.options = []
        self._show_details(path)

    def _on_class_select(self, change):
        if not change["new"]:
            return
        path = change["new"]
        # Filter Members
        funcs = self.df[
            (self.df["ParentPath"] == path)
            & (self.df["Type"].isin(["method", "function"]))
        ].sort_values("Name")
        self.sel_members.options = [(r.Name, r.Path) for r in funcs.itertuples()]
        self._show_details(path)

    def _on_member_select(self, change):
        if not change["new"]:
            return
        path = change["new"]
        self._show_details(path)

    # --- Rendering Logic ---

    def _show_details(self, path):
        """Inspectorタブに詳細とサンプルコードを表示"""
        self.tabs.selected_index = 2
        self.out_details.clear_output()

        row = self.df[self.df["Path"] == path].iloc[0]

        with self.out_details:
            # Header
            display(Markdown(f"# {row['Name']}"))
            display(Markdown(f"**Type:** `{row['Type']}` | **Path:** `{row['Path']}`"))

            # Signature
            if row["Signature"]:
                display(Markdown("### 🧬 Signature"))
                display(Markdown(f"```python\n{row['Name']}{row['Signature']}\n```"))

            # Docstring
            display(Markdown("### 📄 Description"))
            display(Markdown(f"> {row['DocSummary']}"))

            # Sample Code Generation
            display(Markdown("### 💻 Sample Code Generator"))
            code = self._generate_sample_code(row)
            self._display_copyable_code(code, "Sample Code")

            # Copy Info Button
            info_text = f"Name: {row['Name']}\nPath: {row['Path']}\nType: {row['Type']}\nSignature: {row['Signature']}\nDoc: {row['DocSummary']}"
            self._display_copy_button(info_text, "📋 Copy Info Text")

            # Class Diagram if applicable
            if row["Type"] == "class":
                display(Markdown("### 🔗 Inheritance"))
                mmd = f"classDiagram\n class {row['Name']}"
                display(Markdown(f"```mermaid\n{mmd}\n```"))

    def _render_dashboard(self, summary):
        # Report Text generation for copying
        report_text = f"""# Library Analysis Report: {summary['Name']}
Version: {summary['Version']}
File: {summary['File']}
Modules: {summary['Modules']}
Classes: {summary['Classes']}
Functions: {summary['Functions']}
Description: {summary['Doc']}
"""
        html_code = f"""
        <div style="background:#f0f8ff; padding:20px; border-radius:8px;">
            <h2 style="margin-top:0;">📘 {summary['Name']} <small style="color:#666">v{summary['Version']}</small></h2>
            <p>{summary['Doc']}</p>
            <div style="display:flex; gap:15px; margin:15px 0;">
                <div style="flex:1; background:white; padding:15px; text-align:center; border-radius:5px; box-shadow:0 2px 4px rgba(0,0,0,0.1);">
                    <div style="font-size:12px; color:#666;">MODULES</div>
                    <div style="font-size:24px; font-weight:bold; color:#2196F3;">{summary['Modules']}</div>
                </div>
                <div style="flex:1; background:white; padding:15px; text-align:center; border-radius:5px; box-shadow:0 2px 4px rgba(0,0,0,0.1);">
                    <div style="font-size:12px; color:#666;">CLASSES</div>
                    <div style="font-size:24px; font-weight:bold; color:#4CAF50;">{summary['Classes']}</div>
                </div>
                <div style="flex:1; background:white; padding:15px; text-align:center; border-radius:5px; box-shadow:0 2px 4px rgba(0,0,0,0.1);">
                    <div style="font-size:12px; color:#666;">FUNCTIONS</div>
                    <div style="font-size:24px; font-weight:bold; color:#FF9800;">{summary['Functions']}</div>
                </div>
            </div>
        </div>
        """
        display(HTML(html_code))
        self._display_copy_button(report_text, "📋 Copy Report to Clipboard")

    def _render_datatable(self):
        """全データをテーブル表示し、CSVコピー機能を提供"""
        display(Markdown("### All Analyzed Items"))

        # CSV Copy Button
        csv_data = self.df.to_csv(index=False)
        self._display_copy_button(csv_data, "📋 Copy All as CSV")

        # Display DataFrame (limited rows)
        pd.set_option("display.max_colwidth", 50)
        display(self.df)

    def _render_sunburst(self):
        if self.df.empty:
            return
        fig = px.sunburst(
            self.df,
            path=["Type", "Name"],
            title=f"Library Structure: {self.lib_name}",
            height=600,
            color="Type",
        )
        fig.show()

    # --- Code Generation Logic ---
    def _generate_sample_code(self, row):
        """Signature情報から実行可能なサンプルコードを生成する"""
        name = row["Name"]
        path = row["Path"]
        sig_str = row["Signature"]
        type_ = row["Type"]

        # Import文の生成
        module_path = ".".join(path.split(".")[:-1])
        code_lines = []
        code_lines.append(f"from {module_path} import {name}")
        code_lines.append("")

        # 引数の解析 (簡易的なRegexパース)
        # (a, b: int = 1, c='test') -> ['a', "b: int = 1", "c='test'"]
        args_content = sig_str.strip("()")

        # 引数リストの生成
        args_code = []
        if args_content:
            # カンマで分割するが、カッコ内のカンマは無視する必要がある（今回は簡易版）
            params = [
                p.strip() for p in args_content.split(",") if p.strip() and p != "self"
            ]

            for p in params:
                # デフォルト値があるか？
                if "=" in p:
                    # キーワード引数
                    k, v = p.split("=", 1)
                    args_code.append(f"    {k.strip()}={v.strip()},")
                elif ":" in p:
                    # 型ヒントあり、デフォルトなし
                    k, t = p.split(":", 1)
                    args_code.append(f"    {k.strip()}=..., # Type: {t.strip()}")
                else:
                    # 引数名のみ
                    args_code.append(f"    {p.strip()}=...,")

        # 呼び出しコードの組み立て
        call_str = ""
        if type_ == "class":
            call_str = f"# Initialize {name}\ninstance = {name}(\n"
        else:
            call_str = f"# Call {name}\nresult = {name}(\n"

        code_lines.append(call_str + "\n".join(args_code) + "\n)")

        return "\n".join(code_lines)

    # --- Helper: Copy Button ---
    def _display_copy_button(self, text, button_label="Copy"):
        """JSを使ったコピーボタンを表示"""
        # エスケープ処理
        safe_text = (
            html.escape(text).replace("'", r"\'").replace("\n", r"\n").replace("\r", "")
        )

        # ユニークID生成
        btn_id = f"copy_btn_{id(text)}"

        html_code = f"""
        <div style="margin: 10px 0;">
            <button id="{btn_id}" style="
                background-color: #f0f0f0; 
                border: 1px solid #ccc; 
                padding: 5px 15px; 
                border-radius: 4px; 
                cursor: pointer; 
                font-family: sans-serif;
                display: inline-flex;
                align-items: center;
                gap: 5px;
            " onclick="copyToClipboard_{btn_id}()">
                <span>📄</span> {button_label}
            </button>
            <span id="msg_{btn_id}" style="margin-left:10px; color:green; display:none;">Copied!</span>
        </div>
        <script>
        function copyToClipboard_{btn_id}() {{
            const text = '{safe_text}';
            navigator.clipboard.writeText(text).then(function() {{
                const msg = document.getElementById('msg_{btn_id}');
                msg.style.display = 'inline';
                setTimeout(function() {{ msg.style.display = 'none'; }}, 2000);
            }}, function(err) {{
                alert('Copy failed: ' + err);
            }});
        }}
        </script>
        """
        display(HTML(html_code))

    def _display_copyable_code(self, code, title="Code"):
        """コードブロックとコピーボタンを表示"""
        display(Markdown(f"```python\n{code}\n```"))
        self._display_copy_button(code, f"Copy {title}")
