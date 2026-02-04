import inspect
import pkgutil
import importlib
import pandas as pd
import plotly.express as px
import ipywidgets as widgets
from IPython.display import display, Markdown, HTML, clear_output
import json
import base64
import html


class LibraryAnalyzer:
    """ライブラリの構造解析、データ生成、検索ロジックを担当するクラス"""

    def __init__(self, lib_name):
        self.lib_name = lib_name
        self.module = None
        self.df_structure = pd.DataFrame()
        self.inheritance_pairs = []  # (parent, child)

    def scan_library(self, max_depth=3):
        """ライブラリを走査してDataFrame化する"""
        try:
            self.module = importlib.import_module(self.lib_name)
        except ImportError as e:
            raise ImportError(
                f"Library '{self.lib_name}' could not be imported. Detail: {e}"
            )

        data = []
        self.inheritance_pairs = []

        # スタック: (module_obj, depth, parent_path_list)
        stack = [(self.module, 0, [self.lib_name])]
        visited = set()

        while stack:
            mod, depth, path = stack.pop()
            mod_name = path[-1]

            if mod in visited or depth > max_depth:
                continue
            visited.add(mod)

            try:
                members = inspect.getmembers(mod)
            except:
                continue

            for name, obj in members:
                # Private/Internalメンバーの除外
                if name.startswith("_"):
                    continue

                full_path = path + [name]
                path_str = ".".join(full_path)

                kind = "unknown"
                signature = ""
                args_list = []
                doc = inspect.getdoc(obj) or ""

                if inspect.ismodule(obj):
                    if hasattr(obj, "__name__") and obj.__name__.startswith(
                        self.lib_name
                    ):
                        stack.append((obj, depth + 1, full_path))
                    kind = "module"

                elif inspect.isclass(obj):
                    kind = "class"
                    for base in obj.__bases__:
                        if base.__module__.startswith(self.lib_name):
                            self.inheritance_pairs.append((base.__name__, name))

                    try:
                        for m_name, m_obj in inspect.getmembers(obj):
                            if not m_name.startswith("_") and (
                                inspect.isfunction(m_obj) or inspect.ismethod(m_obj)
                            ):
                                m_sig = self._get_sig(m_obj)
                                m_args = self._get_args(m_obj)
                                data.append(
                                    {
                                        "Path": ".".join(full_path + [m_name]),
                                        "Module": mod.__name__,
                                        "Name": m_name,
                                        "Type": "method",
                                        "Signature": str(m_sig),
                                        "Arguments": json.dumps(m_args),
                                        "Docstring": (inspect.getdoc(m_obj) or "")[
                                            :100
                                        ],
                                        "Parent": name,
                                    }
                                )
                    except:
                        pass

                elif inspect.isfunction(obj):
                    kind = "function"
                    signature = self._get_sig(obj)
                    args_list = self._get_args(obj)

                if kind != "module":
                    data.append(
                        {
                            "Path": path_str,
                            "Module": mod.__name__,
                            "Name": name,
                            "Type": kind,
                            "Signature": str(signature),
                            "Arguments": json.dumps(args_list),
                            "Docstring": doc[:100],
                            "Parent": path[-2] if len(path) > 1 else "",
                        }
                    )

        self.df_structure = pd.DataFrame(data)
        return self.df_structure

    def _get_sig(self, obj):
        try:
            return inspect.signature(obj)
        except:
            return ""

    def _get_args(self, obj):
        try:
            sig = inspect.signature(obj)
            return list(sig.parameters.keys())
        except:
            return []

    def get_mermaid_class_diagram(self):
        if not self.inheritance_pairs:
            return "No inheritance relationships found in scanned scope."

        mmd = ["classDiagram"]
        pairs = list(set(self.inheritance_pairs))
        for parent, child in pairs:
            mmd.append(f"    {parent} <|-- {child}")
        return "\n".join(mmd)

    def search_arguments(self, query):
        if self.df_structure.empty:
            return pd.DataFrame()
        return self.df_structure[
            self.df_structure["Arguments"].str.contains(query, na=False)
        ]


class LibraryExplorerApp:
    def __init__(self):
        self.analyzer = None

        # --- UI Components ---
        self.txt_lib = widgets.Text(
            value="chronos", description="Library:", placeholder="Enter library name"
        )
        self.btn_analyze = widgets.Button(
            description="Analyze Library", button_style="success", icon="search"
        )
        self.btn_analyze.on_click(self._run_analysis)
        self.status_label = widgets.Label(value="Ready to analyze.")

        self.out_explore = widgets.Output()
        self.out_visualize = widgets.Output()
        self.out_relation = widgets.Output()
        self.out_search = widgets.Output()

        self.tabs = widgets.Tab(
            children=[
                self.out_explore,
                self.out_visualize,
                self.out_relation,
                self.out_search,
            ]
        )
        self.tabs.set_title(0, "📋 Explorer & Export")
        self.tabs.set_title(1, "📊 Visualization (Plotly)")
        self.tabs.set_title(2, "🔗 Relationships (Mermaid)")
        self.tabs.set_title(3, "🔍 Reverse Search (Args)")

        self.container = widgets.VBox(
            [
                widgets.HBox([self.txt_lib, self.btn_analyze, self.status_label]),
                self.tabs,
            ]
        )

    def display(self):
        display(self.container)

    def _run_analysis(self, b):
        self.status_label.value = "Scanning library... please wait."
        self.out_explore.clear_output()
        self.out_visualize.clear_output()
        self.out_relation.clear_output()
        self.out_search.clear_output()

        lib_name = self.txt_lib.value
        try:
            self.analyzer = LibraryAnalyzer(lib_name)
            df = self.analyzer.scan_library(max_depth=2)
            self.status_label.value = f"Analysis complete. Found {len(df)} items."

            self._render_explorer(df)
            self._render_visualization(df, lib_name)
            self._render_relations()
            self._render_search()

        except Exception as e:
            self.status_label.value = "Error occurred."
            with self.out_explore:
                print(f"Error detail: {e}")

    def _render_explorer(self, df):
        with self.out_explore:
            display(Markdown("### Function/Class Explorer"))

            csv_data = df.to_csv(index=False)
            json_data = df.to_json(orient="records")
            b64_csv = base64.b64encode(csv_data.encode()).decode()
            b64_json = base64.b64encode(json_data.encode()).decode()

            # --- SyntaxError修正箇所 ---
            # f-string内でバックスラッシュを使わず、事前にエスケープ処理を行う
            safe_csv = html.escape(csv_data).replace("'", r"\'").replace("\n", r"\n")

            html_buttons = f"""
            <div style="margin-bottom: 10px;">
                <a download="{self.analyzer.lib_name}_analysis.csv" href="data:text/csv;base64,{b64_csv}" style="background-color:#4CAF50;color:white;padding:5px 10px;text-decoration:none;border-radius:4px;">Download CSV</a>
                <a download="{self.analyzer.lib_name}_analysis.json" href="data:application/json;base64,{b64_json}" style="background-color:#2196F3;color:white;padding:5px 10px;text-decoration:none;border-radius:4px;margin-left:10px;">Download JSON</a>
                <button onclick="navigator.clipboard.writeText('{safe_csv}').then(() => alert('CSV Copied to clipboard!'))" style="background-color:#ff9800;color:white;padding:5px 10px;border:none;border-radius:4px;margin-left:10px;cursor:pointer;">Copy Table to Clipboard</button>
            </div>
            """
            display(HTML(html_buttons))

            pd.set_option("display.max_colwidth", 100)
            display(df[["Type", "Name", "Path", "Signature", "Docstring"]])

    def _render_visualization(self, df, lib_name):
        with self.out_visualize:
            if df.empty:
                print("No data to visualize.")
                return

            display(Markdown("### Library Structure Sunburst Chart"))

            df_viz = df.copy()
            df_viz["Parent"] = df_viz["Parent"].replace("", lib_name)

            try:
                fig = px.sunburst(
                    df_viz,
                    path=["Module", "Type", "Name"],
                    title=f"Structure of {lib_name}",
                    height=700,
                )
                fig.show()
            except Exception as e:
                print(f"Visualization Error: {e}")

    def _render_relations(self):
        with self.out_relation:
            display(Markdown("### Class Inheritance Diagram (Mermaid)"))
            mmd_code = self.analyzer.get_mermaid_class_diagram()

            # Mermaidコードのエスケープ処理
            mmd_escaped = html.escape(mmd_code).replace("'", r"\'").replace("\n", r"\n")

            display(
                HTML(
                    f"""
            <div style="border:1px solid #ddd; padding:10px; background:#f9f9f9;">
                <button onclick="navigator.clipboard.writeText('{mmd_escaped}').then(() => alert('Mermaid code copied!'))" style="float:right; cursor:pointer;">Copy MMD</button>
                <pre>{mmd_code}</pre>
            </div>
            """
                )
            )

            try:
                b64_mmd = base64.b64encode(mmd_code.encode("utf8")).decode("ascii")
                url = f"https://mermaid.ink/img/{b64_mmd}"
                display(Markdown(f"![Mermaid Diagram]({url})"))
            except:
                pass

    def _render_search(self):
        with self.out_search:
            display(Markdown("### Reverse Argument Search"))

            txt_search = widgets.Text(placeholder="e.g. prediction_length")
            btn_search = widgets.Button(description="Search", icon="search")
            out_result = widgets.Output()

            def on_search(b):
                out_result.clear_output()
                query = txt_search.value
                if not query:
                    return

                res = self.analyzer.search_arguments(query)
                with out_result:
                    if res.empty:
                        print("No matches found.")
                    else:
                        display(
                            Markdown(f"**Found {len(res)} matches for `{query}`:**")
                        )
                        display(res[["Type", "Path", "Signature"]])

            btn_search.on_click(on_search)
            txt_search.on_submit(on_search)

            display(widgets.HBox([txt_search, btn_search]))
            display(out_result)
