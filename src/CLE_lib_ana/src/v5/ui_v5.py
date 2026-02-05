from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional

import pandas as pd

try:
    import ipywidgets as widgets
    from IPython.display import display, HTML
except Exception:  # pragma: no cover
    widgets = None
    display = None
    HTML = None

from .analyzer_v5 import V5Analyzer
from .codegen_v5 import CodeGenV5
from .mermaid_export_v5 import export_mermaid_html


@dataclass
class V5ExplorerState:
    distribution: str = ""
    selected_qualname: str = ""
    selected_param: str = ""
    selected_values: Dict[str, str] = None


class V5ExplorerUI:
    def __init__(self, df_api: pd.DataFrame, distribution: str, analyzer: Optional[V5Analyzer] = None):
        if widgets is None:
            raise RuntimeError("ipywidgets not available (HTML/JS fallback not included in this skeleton).")
        self.df_api = df_api.copy()
        self.distribution = distribution
        self.analyzer = analyzer or V5Analyzer()
        self.codegen = CodeGenV5()
        self.state = V5ExplorerState(distribution=distribution, selected_values={})
        self._build()

    def _build(self):
        self.dd_qualname = widgets.Dropdown(options=self._qualname_options(), description="Item:", layout=widgets.Layout(width="95%"))
        self.dd_param = widgets.Dropdown(options=[("", "")], description="Param:", layout=widgets.Layout(width="95%"))
        self.dd_value = widgets.Dropdown(options=[("", "")], description="Value:", layout=widgets.Layout(width="95%"))

        self.out_details = widgets.Output(layout={"border": "1px solid #ddd", "padding": "8px"})
        self.out_code = widgets.Output(layout={"border": "1px solid #ddd", "padding": "8px"})
        self.out_mermaid = widgets.Output(layout={"border": "1px solid #ddd", "padding": "8px"})

        self.btn_codegen = widgets.Button(description="Generate Code", button_style="primary")
        self.btn_mermaid = widgets.Button(description="Mermaid (simple)")
        self.btn_export_mermaid = widgets.Button(description="Export Mermaid HTML")

        self.dd_qualname.observe(self._on_select_item, names="value")
        self.dd_param.observe(self._on_select_param, names="value")
        self.dd_value.observe(self._on_select_value, names="value")
        self.btn_codegen.on_click(self._on_codegen)
        self.btn_mermaid.on_click(self._on_mermaid)
        self.btn_export_mermaid.on_click(self._on_export_mermaid)

        left = widgets.VBox(
            [self.dd_qualname, self.dd_param, self.dd_value, widgets.HBox([self.btn_codegen, self.btn_mermaid, self.btn_export_mermaid])],
            layout=widgets.Layout(width="40%"),
        )
        right = widgets.Tab(children=[self.out_details, self.out_code, self.out_mermaid])
        right.set_title(0, "Inspector")
        right.set_title(1, "CodeGen")
        right.set_title(2, "Mermaid")

        self.ui = widgets.HBox([left, right], layout=widgets.Layout(width="100%"))

    def _qualname_options(self):
        if self.df_api.empty or "qualname" not in self.df_api.columns:
            return [("No API objects", "")]
        df = self.df_api.sort_values(["is_public", "qualname"], ascending=[False, True])
        opts = [(q, q) for q in df["qualname"].tolist()[:5000]]
        return opts or [("No API objects", "")]

    def display(self):
        display(self.ui)
        if self.dd_qualname.value:
            self._on_select_item({"new": self.dd_qualname.value})

    def _get_selected_row(self) -> Optional[Dict]:
        q = self.dd_qualname.value
        if not q:
            return None
        df = self.df_api[self.df_api["qualname"] == q]
        if df.empty:
            return None
        return df.iloc[0].to_dict()

    def _on_select_item(self, change):
        row = self._get_selected_row()
        self.state.selected_values = {}
        if not row:
            return

        spec = self.analyzer.to_callable_spec(row)
        param_names = [p.name for p in spec.params if p.name not in {"self", "cls"}]
        self.dd_param.options = [("", "")] + [(n, n) for n in param_names]
        self.dd_param.value = ""
        self.dd_value.options = [("", "")]
        self.dd_value.value = ""

        with self.out_details:
            self.out_details.clear_output()
            print(f"Qualname: {spec.qualname}")
            print(f"Signature: {spec.signature_str}")
            if spec.doc_summary:
                print(f"Doc: {spec.doc_summary}")
            print("\\nParams:")
            for p in spec.params:
                print(f"  - {p.name:15s} kind={p.kind.value:20s} ann={p.annotation} default={p.default} required={p.required}")

    def _on_select_param(self, change):
        row = self._get_selected_row()
        if not row:
            return
        spec = self.analyzer.to_callable_spec(row)
        pname = self.dd_param.value
        if not pname:
            self.dd_value.options = [("", "")]
            self.dd_value.value = ""
            return
        p = next((x for x in spec.params if x.name == pname), None)
        if p is None:
            return
        cands = self.analyzer.value_candidates_for_param(p)
        if not cands:
            self.dd_value.options = [("(no candidates)", "")]
            self.dd_value.value = ""
            return
        self.dd_value.options = [("", "")] + [(f"{c.value} ({c.source}, {c.confidence:.2f})", c.value) for c in cands]
        self.dd_value.value = ""

    def _on_select_value(self, change):
        pname = self.dd_param.value
        val = self.dd_value.value
        if pname and val:
            self.state.selected_values[pname] = val

    def _on_codegen(self, btn):
        row = self._get_selected_row()
        if not row:
            return
        spec = self.analyzer.to_callable_spec(row)
        code = self.codegen.generate(spec, selected_values=self.state.selected_values)
        with self.out_code:
            self.out_code.clear_output()
            print(code)

    def _on_mermaid(self, btn):
        row = self._get_selected_row()
        if not row:
            return
        dist = row.get("distribution", self.distribution)
        module = row.get("module", "")
        q = row.get("qualname", "")
        diagram = f'''graph TD
  A[{dist}] --> B[{module}]
  B --> C[{q}]
'''
        with self.out_mermaid:
            self.out_mermaid.clear_output()
            if HTML:
                display(HTML(f"<pre>{diagram}</pre>"))
            else:
                print(diagram)

    def _on_export_mermaid(self, btn):
        row = self._get_selected_row()
        if not row:
            return
        dist = row.get("distribution", self.distribution)
        module = row.get("module", "")
        q = row.get("qualname", "")
        diagram = f'''graph TD
  A[{dist}] --> B[{module}]
  B --> C[{q}]
'''
        try:
            from lib_ana.config import ensure_dirs
            paths = ensure_dirs()
            out = paths.exports / f"diagram_{dist}.html"
        except Exception:
            out = None
        with self.out_mermaid:
            if out is None:
                print("Could not resolve exports path. Set LIB_ANA_ROOT or run from project root.")
                return
            export_mermaid_html(diagram, out)
            print(f"Exported: {out}")
