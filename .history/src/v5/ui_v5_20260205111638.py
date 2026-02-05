from __future__ import annotations

import base64
import html
import importlib
import inspect
from typing import Any, Dict, List, Optional

import ipywidgets as widgets
from IPython.display import HTML, Markdown, display
import pandas as pd
import plotly.express as px

from analyzer_v4 import LibraryAnalyzerV4, _ann_to_str
from models_v4 import AnalysisConfig
from package_catalog_v4 import build_package_catalog

from .mermaid_export_v5 import make_mermaid_and_html
from .sample_data_factory_v5 import ParamInfo, ValueCandidate, suggest_values_for_param
from .codegen_v5 import generate_sample_code


class CognitiveLibraryUIV5:
    """5列ナビゲータ＋値候補＋Mermaid/HTML＋サンプルコード UI."""

    def __init__(self) -> None:
        self.lib_name: Optional[str] = None
        self.df_nodes: pd.DataFrame = pd.DataFrame()
        self.df_edges: pd.DataFrame = pd.DataFrame()
        self.summary: Dict[str, Any] = {}
        self.current_target_id: Optional[str] = None
        self.current_params: List[ParamInfo] = []
        self.value_candidates_by_param: Dict[str, List[ValueCandidate]] = {}
        self.selected_values_by_param: Dict[str, ValueCandidate] = {}

        self.catalog = build_package_catalog(max_items=2000)
        options = [
            (f"{it.import_name}   ({it.dist_name} {it.version})", it.import_name)
            for it in self.catalog
        ]
        options = sorted(options, key=lambda x: x[1].lower())

        self.dd_lib = widgets.Dropdown(
            options=options[:1500],
            description="Library:",
            layout=widgets.Layout(width="600px"),
        )
        self.btn_analyze = widgets.Button(
            description="Analyze",
            button_style="primary",
            icon="search",
            layout=widgets.Layout(width="140px"),
        )
        self.btn_analyze.on_click(self._on_analyze)

        list_layout = widgets.Layout(width="19%", height="260px")
        self.sel_modules = widgets.Select(options=[], description="1. Modules", layout=list_layout)
        self.sel_items = widgets.Select(options=[], description="2. Items", layout=list_layout)
        self.sel_members = widgets.Select(options=[], description="3. Members", layout=list_layout)
        self.sel_params = widgets.Select(options=[], description="4. Params", layout=list_layout)
        self.sel_values = widgets.Select(options=[], description="5. Values", layout=list_layout)

        self.sel_modules.observe(self._on_module_select, names="value")
        self.sel_items.observe(self._on_item_select, names="value")
        self.sel_members.observe(self._on_member_select, names="value")
        self.sel_params.observe(self._on_param_select, names="value")
        self.sel_values.observe(self._on_value_select, names="value")

        self.out_summary = widgets.Output(layout=widgets.Layout(padding="10px"))
        self.out_details = widgets.Output(layout=widgets.Layout(padding="10px"))
        self.out_params = widgets.Output(layout=widgets.Layout(padding="10px"))
        self.out_mermaid = widgets.Output(layout=widgets.Layout(padding="10px"))
        self.out_codegen = widgets.Output(layout=widgets.Layout(padding="10px"))

        self.tabs = widgets.Tab(
            children=[
                self.out_summary,
                self.out_details,
                self.out_params,
                self.out_mermaid,
                self.out_codegen,
            ]
        )
        self.tabs.set_title(0, "📊 Summary")
        self.tabs.set_title(1, "🔎 Inspector")
        self.tabs.set_title(2, "⚙️ Params & Values")
        self.tabs.set_title(3, "🧩 Mermaid & HTML")
        self.tabs.set_title(4, "💡 Sample Code")

        self.btn_generate = widgets.Button(
            description="Generate Sample Code",
            icon="code",
            layout=widgets.Layout(width="220px"),
        )
        self.btn_generate.on_click(self._on_generate_code)

        title_html = """
        <div style="font-size:18px;font-weight:bold;margin-bottom:4px;">
          🔧 Cognitive Library Explorer <span style="color:#4F46E5;">V5</span>
        </div>
        <div style="color:#6B7280;font-size:12px;margin-bottom:4px;">
          Modules → Items → Members → Params → Values の 5 列ナビゲータで Python ライブラリを探索
        </div>
        """
        self.header = widgets.VBox(
            [
                widgets.HTML(title_html),
                widgets.HBox([self.dd_lib, self.btn_analyze]),
                widgets.HTML("<hr style='margin:4px 0;'>"),
            ],
            layout=widgets.Layout(padding="8px", border_bottom="1px solid #e5e7eb"),
        )

        self.navigator = widgets.HBox(
            [
                self.sel_modules,
                self.sel_items,
                self.sel_members,
                self.sel_params,
                self.sel_values,
            ],
            layout=widgets.Layout(padding="8px", background_color="#f9fafb"),
        )

        self.app = widgets.VBox(
            [
                self.header,
                self.navigator,
                widgets.HBox(
                    [widgets.HTML("<div style='flex:1'></div>"), self.btn_generate],
                    layout=widgets.Layout(
                        justify_content="flex-end",
                        padding="0 8px 8px 8px",
                    ),
                ),
                self.tabs,
            ]
        )

    def display(self) -> None:
        display(self.app)

    def _default_config(self) -> AnalysisConfig:
        return AnalysisConfig(
            api_surface="module_public",
            include_private=False,
            include_external_reexports=False,
            include_inherited_members=False,
            add_related_edges=True,
        )

    def _on_analyze(self, _btn: widgets.Button) -> None:
        self.lib_name = self.dd_lib.value
        self._clear_state()

        if not self.lib_name:
            with self.out_summary:
                print("No library selected.")
            return

        with self.out_summary:
            self.out_summary.clear_output()
            print(f"🔄 Analyzing '{self.lib_name}' ...")

        analyzer = LibraryAnalyzerV4(self.lib_name, self._default_config())
        summary, df_nodes, df_edges, _ = analyzer.analyze()

        self.summary = summary
        self.df_nodes = df_nodes
        self.df_edges = df_edges

        self._render_summary()
        self._refresh_modules()
        self._render_mermaid_tab()
        self._refresh_details_from_selection()
        self.tabs.selected_index = 0

    def _clear_state(self) -> None:
        self.df_nodes = pd.DataFrame()
        self.df_edges = pd.DataFrame()
        self.summary = {}
        self.current_target_id = None
        self.current_params = []
        self.value_candidates_by_param = {}
        self.selected_values_by_param = {}
        self.sel_modules.options = []
        self.sel_items.options = []
        self.sel_members.options = []
        self.sel_params.options = []
        self.sel_values.options = []
        for out in [
            self.out_summary,
            self.out_details,
            self.out_params,
            self.out_mermaid,
            self.out_codegen,
        ]:
            out.clear_output()

    def _render_summary(self) -> None:
        self.out_summary.clear_output()
        with self.out_summary:
            if not self.summary:
                print("No data.")
                return
            s = self.summary
            df = pd.DataFrame(
                {
                    "Metric": [
                        "Modules",
                        "Classes",
                        "Functions",
                        "Methods/Props",
                        "External",
                        "UniqueParamNames",
                        "UniqueReturnTypes",
                        "Errors",
                    ],
                    "Value": [
                        s.get("Modules", 0),
                        s.get("Classes", 0),
                        s.get("Functions", 0),
                        s.get("Methods/Props", 0),
                        s.get("External", 0),
                        s.get("UniqueParamNames", 0),
                        s.get("UniqueReturnTypes", 0),
                        s.get("Errors", 0),
                    ],
                }
            )
            display(Markdown(f"### 📊 Summary — `{html.escape(self.lib_name or '')}`"))
            display(df)

            if not self.df_nodes.empty:
                by_type = self.df_nodes["Type"].value_counts().reset_index()
                by_type.columns = ["Type", "Count"]
                fig = px.bar(by_type, x="Type", y="Count", title="Objects by Type")
                fig.update_layout(height=260, margin=dict(l=0, r=0, t=40, b=0))
                display(fig)

    def _refresh_modules(self) -> None:
        if self.df_nodes.empty:
            self.sel_modules.options = []
            return
        df_mod = self.df_nodes[self.df_nodes["Type"] == "module"].copy()
        df_mod = df_mod.sort_values("Path")
        self.sel_modules.options = [(row["Path"], row["ID"]) for _, row in df_mod.iterrows()]
        self.sel_items.options = []
        self.sel_members.options = []
        self.sel_params.options = []
        self.sel_values.options = []
        if self.sel_modules.options:
            first_id = self.sel_modules.options[0][1]
            self.sel_modules.value = first_id

    def _on_module_select(self, change: Dict[str, Any]) -> None:
        mod_id = change["new"]
        if not mod_id or self.df_nodes.empty:
            return
        df_items = self.df_nodes[
            (self.df_nodes["Parent"] == mod_id)
            & (self.df_nodes["Type"].isin(["class", "function", "external"]))
        ].copy()
        df_items = df_items.sort_values("Name")
        self.sel_items.options = [
            (f"{r['Type']}: {r['Name']}", r["ID"]) for _, r in df_items.iterrows()
        ]
        self.sel_members.options = []
        self.sel_params.options = []
        self.sel_values.options = []
        self.current_target_id = None
        self._refresh_details_from_selection()

    def _on_item_select(self, change: Dict[str, Any]) -> None:
        node_id = change["new"]
        if not node_id:
            return
        row = self._get_node_row(node_id)
        if row is None:
            return
        t = str(row.get("Type", "")).lower()
        if t in {"class", "external"}:
            df_members = self.df_nodes[
                (self.df_nodes["Parent"] == node_id)
                & (self.df_nodes["Type"].isin(["method", "property"]))
            ].copy()
            df_members = df_members.sort_values("Name")
            self.sel_members.options = [
                (f"{r['Type']}: {r['Name']}", r["ID"]) for _, r in df_members.iterrows()
            ]
            self.current_target_id = node_id
        else:
            self.sel_members.options = []
            self.current_target_id = node_id
        self._refresh_params_for_current_target()
        self._refresh_details_from_selection()

    def _on_member_select(self, change: Dict[str, Any]) -> None:
        node_id = change["new"]
        if not node_id:
            return
        self.current_target_id = node_id
        self._refresh_params_for_current_target()
        self._refresh_details_from_selection()

    def _on_param_select(self, change: Dict[str, Any]) -> None:
        _ = change["new"]
        pname = self.sel_params.value
        if not pname:
            return
        cands = self.value_candidates_by_param.get(pname, [])
        self.sel_values.options = [
            (f"{c.code}  ({c.description})", c.code) for c in cands
        ]
        if cands:
            self.sel_values.value = cands[0].code
            self.selected_values_by_param[pname] = cands[0]
        self._render_params_tab()

    def _on_value_select(self, change: Dict[str, Any]) -> None:
        code = change["new"]
        pname = self.sel_params.value
        if not pname or not code:
            return
        cands = self.value_candidates_by_param.get(pname, [])
        for c in cands:
            if c.code == code:
                self.selected_values_by_param[pname] = c
                break
        self._render_params_tab()

    def _get_node_row(self, node_id: str) -> Optional[pd.Series]:
        if self.df_nodes.empty:
            return None
        row = self.df_nodes[self.df_nodes["ID"] == node_id]
        if row.empty:
            return None
        return row.iloc[0]

    def _resolve_object_for_row(self, row: pd.Series) -> Optional[Any]:
        t = str(row.get("Type", "")).lower()
        path = str(row.get("Path", "")) or str(row.get("ID", ""))
        origin_module = str(row.get("OriginModule", "") or "")
        name = str(row.get("Name", ""))

        try:
            if t in {"function", "class"}:
                if origin_module:
                    mod = importlib.import_module(origin_module)
                    return getattr(mod, name, None)
                if "." in path:
                    mod_name, attr = path.rsplit(".", 1)
                    mod = importlib.import_module(mod_name)
                    return getattr(mod, attr, None)
            elif t in {"method", "property"}:
                flags = row.get("Flags")
                member_of = ""
                if isinstance(flags, dict):
                    member_of = flags.get("member_of", "")
                if member_of and "." in member_of:
                    mod_name, cls_name = member_of.rsplit(".", 1)
                    mod = importlib.import_module(mod_name)
                    cls = getattr(mod, cls_name, None)
                    if cls is not None:
                        return getattr(cls, name, None)
        except Exception:
            return None
        return None

    def _build_params_for_row(self, row: pd.Series) -> None:
        obj = self._resolve_object_for_row(row)
        self.current_params = []
        self.value_candidates_by_param = {}
        if obj is None:
            return
        try:
            sig = inspect.signature(obj)
        except Exception:
            return

        params: List[ParamInfo] = []
        for p in sig.parameters.values():
            ann = _ann_to_str(p.annotation)
            has_default = not (p.default is inspect._empty)
            default_repr = repr(p.default) if has_default else ""
            pi = ParamInfo(
                name=p.name,
                kind=str(p.kind),
                annotation=ann,
                has_default=has_default,
                default_repr=default_repr,
            )
            params.append(pi)
            self.value_candidates_by_param[p.name] = suggest_values_for_param(pi)

        self.current_params = params
        if params:
            self.sel_params.options = [
                (f"{i + 1}. {p.name} : {p.annotation or 'Any'}", p.name)
                for i, p in enumerate(params)
            ]
            self.sel_params.value = params[0].name
            first_cands = self.value_candidates_by_param.get(params[0].name, [])
            self.sel_values.options = [
                (f"{c.code}  ({c.description})", c.code) for c in first_cands
            ]
            if first_cands:
                self.sel_values.value = first_cands[0].code
                self.selected_values_by_param[params[0].name] = first_cands[0]
        else:
            self.sel_params.options = []
            self.sel_values.options = []

    def _refresh_params_for_current_target(self) -> None:
        self.out_params.clear_output()
        self.sel_params.options = []
        self.sel_values.options = []
        if not self.current_target_id:
            return
        row = self._get_node_row(self.current_target_id)
        if row is None:
            return
        self._build_params_for_row(row)
        self._render_params_tab()

    def _refresh_details_from_selection(self) -> None:
        self.out_details.clear_output()
        if not self.current_target_id:
            return
        row = self._get_node_row(self.current_target_id)
        if row is None:
            return
        with self.out_details:
            title = f"{row.get('Type', '')}: {row.get('Path', row.get('ID', ''))}"
            display(Markdown(f"### 🔍 {html.escape(title)}"))

            basic = {
                "ID": row.get("ID"),
                "Type": row.get("Type"),
                "Name": row.get("Name"),
                "Path": row.get("Path"),
                "Module": row.get("Module"),
                "OriginModule": row.get("OriginModule"),
                "OriginFile": row.get("OriginFile"),
                "Line": row.get("Line"),
                "EndLine": row.get("EndLine"),
                "LOC": row.get("LOC"),
            }
            df_basic = pd.DataFrame(list(basic.items()), columns=["Field", "Value"])
            display(df_basic)

            sig = row.get("Signature") or ""
            doc = row.get("DocSummary") or ""
            if sig:
                display(Markdown(f"**Signature**\n\n```python\n{sig}\n```"))
            if doc:
                display(Markdown(f"**DocSummary**\n\n{html.escape(str(doc))}"))

    def _render_params_tab(self) -> None:
        self.out_params.clear_output()
        with self.out_params:
            if not self.current_params:
                print("No parameters for selected object.")
                return
            rows = []
            for p in self.current_params:
                cands = self.value_candidates_by_param.get(p.name, [])
                selected = self.selected_values_by_param.get(p.name)
                rows.append(
                    {
                        "Name": p.name,
                        "Kind": p.kind,
                        "Type": p.annotation or "Any",
                        "HasDefault": p.has_default,
                        "Default": p.default_repr,
                        "SelectedValue": selected.code if selected else "",
                        "Candidates": "; ".join(c.code for c in cands),
                    }
                )
            df = pd.DataFrame(rows)
            display(Markdown("### ⚙️ Parameters & Value candidates"))
            display(df)

    def _render_mermaid_tab(self) -> None:
        self.out_mermaid.clear_output()
        if self.df_nodes.empty:
            return
        with self.out_mermaid:
            mmd, html_doc = make_mermaid_and_html(
                self.df_nodes, self.df_edges, self.lib_name or "", max_nodes=260
            )
            display(Markdown("#### 🧩 Mermaid(MMD) code"))
            ta = widgets.Textarea(
                value=mmd,
                layout=widgets.Layout(width="100%", height="260px"),
            )
            display(ta)

            b64_mmd = base64.b64encode(mmd.encode("utf-8")).decode("ascii")
            b64_html = base64.b64encode(html_doc.encode("utf-8")).decode("ascii")
            btns = f"""
            <div style="margin-top: 8px;">
              <a download="{self.lib_name}.mmd" href="data:text/plain;base64,{b64_mmd}"
                 style="background:#111827;color:white;padding:6px 10px;text-decoration:none;border-radius:6px;">Download .mmd</a>
              <a download="{self.lib_name}.html" href="data:text/html;base64,{b64_html}"
                 style="background:#4B5563;color:white;padding:6px 10px;text-decoration:none;border-radius:6px;margin-left:8px;">Download HTML</a>
            </div>
            """
            display(HTML(btns))

            display(Markdown("#### 🧩 Live Mermaid Preview"))
            preview_html = f"""
            <div>
              <script src="https://cdn.jsdelivr.net/npm/mermaid/dist/mermaid.min.js"></script>
              <div class="mermaid">
            {html.escape(mmd)}
              </div>
              <script>mermaid.initialize({{startOnLoad:true}});</script>
            </div>
            """
            display(HTML(preview_html))

    def _on_generate_code(self, _btn: widgets.Button) -> None:
        self.out_codegen.clear_output()
        if not self.current_target_id or self.df_nodes.empty:
            with self.out_codegen:
                print("Select a function / method / class first.")
            return
        row = self._get_node_row(self.current_target_id)
        if row is None:
            with self.out_codegen:
                print("Target not found.")
            return
        if not self.current_params:
            self._build_params_for_row(row)

        code = generate_sample_code(
            self.lib_name or "",
            row,
            self.current_params,
            self.selected_values_by_param,
        )
        with self.out_codegen:
            display(Markdown("### 💡 Generated sample code"))
            ta = widgets.Textarea(
                value=code,
                layout=widgets.Layout(width="100%", height="320px"),
            )
            display(ta)
            b64_py = base64.b64encode(code.encode("utf-8")).decode("ascii")
            fname = (row.get("Name") or "sample").replace(" ", "_")
            btn = f"""
            <div style="margin-top: 8px;">
              <a download="{fname}_sample.py" href="data:text/x-python;base64,{b64_py}"
                 style="background:#2563EB;color:white;padding:6px 10px;text-decoration:none;border-radius:6px;">Download .py</a>
            </div>
            """
            display(HTML(btn))
            display(
                Markdown(
                    "※ 上記コードを次のコードセルにコピーして実行してください。"
                    "環境に応じて引数やデータセットを調整してください。"
                )
            )
