# ファイルパス: C:\lib_ana\src\v5\ui_v5.py
from __future__ import annotations

import base64
import html
import importlib
import inspect
import io
import textwrap
from contextlib import redirect_stdout, redirect_stderr
from typing import Any, Dict, List, Optional, Set, Tuple

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


# ==========
# ヘルパー
# ==========


def _module_group(path: str, depth: int = 2) -> str:
    """
    モジュールパスからグループキーを作成する。

    例: "timesfm.flax.dense" -> depth=2 なら "timesfm.flax"
    """
    parts = (path or "").split(".")
    if len(parts) <= depth:
        return ".".join(parts)
    return ".".join(parts[:depth])


# ==========================
# メイン UI クラス
# ==========================


class CognitiveLibraryUIV5:
    """
    6 列ナビゲータ＋検索＋コード実行＋レポート出力 UI.

    - 0. Groups  → モジュールグループ（timesfm.flax / timesfm.torch など）
    - 1. Modules → モジュール
    - 2. Items   → クラス / 関数 / external
    - 3. Members → メソッド / プロパティ
    - 4. Params  → 引数
    - 5. Values  → 値候補

    追加機能:
    - 検索/履歴 Combobox で任意文字列 or 過去選択からジャンプ
    - Param Index タブで「一意な引数名 → それを使う API 一覧」逆引き
    - Summary での分布/ランキング可視化
    - Sample Code タブでコード生成 + Compile & Run
    - Export Report ボタンでタブ内容を Markdown 1 ファイルにまとめてダウンロード
    - Global Insight タブで、セッション中に解析した複数ライブラリを横断したインサイト
    """

    def __init__(self) -> None:
        # --- 内部状態 ---
        self.lib_name: Optional[str] = None
        self.df_nodes: pd.DataFrame = pd.DataFrame()
        self.df_edges: pd.DataFrame = pd.DataFrame()
        self.summary: Dict[str, Any] = {}
        self.current_target_id: Optional[str] = None
        self.current_params: List[ParamInfo] = []
        self.value_candidates_by_param: Dict[str, List[ValueCandidate]] = {}
        self.selected_values_by_param: Dict[str, ValueCandidate] = {}

        # モジュールグループ・モジュール一覧（フィルタ前）
        self._modules_all: List[Tuple[str, str]] = []  # (label, node_id)
        self._items_all: List[Tuple[str, str]] = []
        self._members_all: List[Tuple[str, str]] = []

        # 検索 / 履歴
        self.history_targets: List[str] = []
        self.history_labels: List[str] = []
        self.history_map: Dict[str, str] = {}  # label -> node_id

        # パラメータインデックス
        self.param_index: Dict[str, Set[str]] = {}  # param -> {node_id}
        self.param_counts: Dict[str, int] = {}  # param -> count

        # Global insight 用
        self.global_history: Dict[str, Dict[str, Any]] = {}

        # サンプルコード実行用
        self.generated_code: str = ""
        self._code_textarea: Optional[widgets.Textarea] = None

        # -----------------
        # パッケージ一覧
        # -----------------
        catalog = build_package_catalog(max_items=2000)
        lib_options = [
            (f"{it.import_name}   ({it.dist_name} {it.version})", it.import_name)
            for it in catalog
        ]
        lib_options = sorted(lib_options, key=lambda x: x[1].lower())

        self.dd_lib = widgets.Dropdown(
            options=lib_options[:1500],
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

        # -----------------
        # 検索 / 履歴コンボボックス
        # -----------------
        self.cb_search = widgets.Combobox(
            description="Search/History:",
            options=[],
            placeholder="関数名やモジュール名の一部を入力 / 過去の選択から選ぶ",
            layout=widgets.Layout(width="600px"),
        )
        self.cb_search.observe(self._on_search_change, names="value")

        # -----------------
        # 6 列ナビゲータ
        # -----------------
        list_layout = widgets.Layout(width="16%", height="260px")
        self.sel_groups = widgets.Select(
            options=[], description="0. Groups", layout=list_layout
        )
        self.sel_modules = widgets.Select(
            options=[], description="1. Modules", layout=list_layout
        )
        self.sel_items = widgets.Select(
            options=[], description="2. Items", layout=list_layout
        )
        self.sel_members = widgets.Select(
            options=[], description="3. Members", layout=list_layout
        )
        self.sel_params = widgets.Select(
            options=[], description="4. Params", layout=list_layout
        )
        self.sel_values = widgets.Select(
            options=[], description="5. Values", layout=list_layout
        )

        self.sel_groups.observe(self._on_group_select, names="value")
        self.sel_modules.observe(self._on_module_select, names="value")
        self.sel_items.observe(self._on_item_select, names="value")
        self.sel_members.observe(self._on_member_select, names="value")
        self.sel_params.observe(self._on_param_select, names="value")
        self.sel_values.observe(self._on_value_select, names="value")

        # -----------------
        # タブ用 Output
        # -----------------
        self.out_summary = widgets.Output(layout=widgets.Layout(padding="10px"))
        self.out_details = widgets.Output(layout=widgets.Layout(padding="10px"))
        self.out_params = widgets.Output(layout=widgets.Layout(padding="10px"))
        self.out_mermaid = widgets.Output(layout=widgets.Layout(padding="10px"))
        self.out_codegen = widgets.Output(layout=widgets.Layout(padding="10px"))
        self.out_param_index = widgets.Output(layout=widgets.Layout(padding="10px"))
        self.out_global = widgets.Output(layout=widgets.Layout(padding="10px"))

        self.tabs = widgets.Tab(
            children=[
                self.out_summary,
                self.out_details,
                self.out_params,
                self.out_mermaid,
                self.out_codegen,
                self.out_param_index,
                self.out_global,
            ]
        )
        self.tabs.set_title(0, "📊 Summary")
        self.tabs.set_title(1, "🔎 Inspector")
        self.tabs.set_title(2, "⚙️ Params & Values")
        self.tabs.set_title(3, "🧩 Mermaid & HTML")
        self.tabs.set_title(4, "💡 Sample Code")
        self.tabs.set_title(5, "🧬 Param Index")
        self.tabs.set_title(6, "🌐 Global Insight")

        # -----------------
        # サンプルコード関連ボタン
        # -----------------
        self.btn_generate = widgets.Button(
            description="Generate Sample Code",
            icon="code",
            layout=widgets.Layout(width="220px"),
        )
        self.btn_generate.on_click(self._on_generate_code)

        self.btn_run_code = widgets.Button(
            description="Compile & Run",
            icon="play",
            layout=widgets.Layout(width="150px"),
        )
        self.btn_run_code.on_click(self._on_run_code)

        self.btn_export_report = widgets.Button(
            description="Export Report",
            icon="download",
            layout=widgets.Layout(width="180px"),
        )
        self.btn_export_report.on_click(self._on_export_report)

        # コード実行結果用 Output
        self.out_run = widgets.Output(layout=widgets.Layout(padding="4px"))

        # -----------------
        # レイアウト
        # -----------------
        title_html = (
            "<div style='font-size:18px;font-weight:bold;margin-bottom:4px;'>"
            "🔧 Cognitive Library Explorer <span style='color:#4F46E5;'>V5</span>"
            "</div>"
            "<div style='color:#6B7280;font-size:12px;margin-bottom:4px;'>"
            "Groups → Modules → Items → Members → Params → Values の 6 列ナビゲータで "
            "Python ライブラリを探索"
            "</div>"
        )

        self.header = widgets.VBox(
            [
                widgets.HTML(title_html),
                widgets.HBox([self.dd_lib, self.btn_analyze]),
                self.cb_search,
                widgets.HTML("<hr style='margin:4px 0;'>"),
            ],
            layout=widgets.Layout(padding="8px"),
        )

        self.navigator = widgets.HBox(
            [
                self.sel_groups,
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
                    [
                        widgets.HTML("<div style='flex:1'></div>"),
                        self.btn_generate,
                        self.btn_run_code,
                        self.btn_export_report,
                    ],
                    layout=widgets.Layout(
                        justify_content="flex-end",
                        padding="0 8px 8px 8px",
                        column_gap="8px",
                    ),
                ),
                self.tabs,
            ]
        )

    # ==========
    # 公開 API
    # ==========
    def display(self) -> None:
        display(self.app)

    # ==========
    # 解析実行
    # ==========

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

        self._build_param_index()
        self._render_summary()
        self._refresh_module_groups()
        self._render_mermaid_tab()
        self._refresh_details_from_selection()
        self._render_param_index_tab()
        self._update_global_history()
        self._render_global_insight_tab()
        self.tabs.selected_index = 0

    def _clear_state(self) -> None:
        self.df_nodes = pd.DataFrame()
        self.df_edges = pd.DataFrame()
        self.summary = {}
        self.current_target_id = None
        self.current_params = []
        self.value_candidates_by_param = {}
        self.selected_values_by_param = {}
        self._modules_all = []
        self._items_all = []
        self._members_all = []
        self.param_index = {}
        self.param_counts = {}
        self.history_targets = []
        self.history_labels = []
        self.history_map = {}
        self.generated_code = ""
        self._code_textarea = None

        self.sel_groups.options = []
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
            self.out_param_index,
            self.out_global,
            self.out_run,
        ]:
            out.clear_output()

    # ==========
    # Summary / Analytics
    # ==========

    def _render_summary(self) -> None:
        self.out_summary.clear_output()
        with self.out_summary:
            if not self.summary:
                print("No data.")
                return

            s = self.summary
            df_summary = pd.DataFrame(
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
            display(df_summary)

            # タイプ別カウント
            if not self.df_nodes.empty and "Type" in self.df_nodes.columns:
                by_type = self.df_nodes["Type"].value_counts().reset_index()
                by_type.columns = ["Type", "Count"]
                fig = px.bar(by_type, x="Type", y="Count", title="Objects by Type")
                fig.update_layout(height=260, margin=dict(l=0, r=0, t=40, b=0))
                display(fig)

            # モジュール別の要素数
            if not self.df_nodes.empty and "Module" in self.df_nodes.columns:
                df_mod = (
                    self.df_nodes[
                        self.df_nodes["Type"].isin(
                            ["class", "function", "method", "property"]
                        )
                    ]
                    .groupby("Module")["ID"]
                    .count()
                    .reset_index()
                    .rename(columns={"ID": "Objects"})
                    .sort_values("Objects", ascending=False)
                    .head(20)
                )
                if not df_mod.empty:
                    display(Markdown("#### Top modules by number of objects"))
                    display(df_mod)
                    fig2 = px.bar(df_mod, x="Module", y="Objects", title="Top modules")
                    fig2.update_layout(
                        height=260,
                        margin=dict(l=0, r=0, t=40, b=80),
                        xaxis_tickangle=-45,
                    )
                    display(fig2)

            # LOC 分布
            if "LOC" in self.df_nodes.columns:
                df_loc = self.df_nodes[self.df_nodes["LOC"].notnull()].copy()
                if not df_loc.empty:
                    display(Markdown("#### LOC distribution"))
                    fig3 = px.histogram(df_loc, x="LOC", nbins=40)
                    fig3.update_layout(height=260, margin=dict(l=0, r=0, t=40, b=40))
                    display(fig3)

            # 一意パラメータ名テーブル
            if self.param_counts:
                display(Markdown("#### Unique parameter names (overview)"))
                rows = [
                    {"ParamName": name, "Count": cnt}
                    for name, cnt in sorted(
                        self.param_counts.items(), key=lambda kv: kv[1], reverse=True
                    )
                ]
                df_params = pd.DataFrame(rows)
                display(df_params.head(50))

            # 詳細テーブル (Accordion)
            if not self.df_nodes.empty:
                acc_children = []
                acc_titles = []

                def _add_table(df: pd.DataFrame, title: str, cols: List[str]) -> None:
                    if df.empty:
                        return
                    out = widgets.Output()
                    with out:
                        use_cols = [c for c in cols if c in df.columns]
                        if not use_cols:
                            use_cols = list(df.columns)
                        display(df[use_cols])
                    acc_children.append(out)
                    acc_titles.append(title)

                _add_table(
                    self.df_nodes[self.df_nodes["Type"] == "module"],
                    "Modules",
                    ["Path", "OriginFile", "LOC"],
                )
                _add_table(
                    self.df_nodes[self.df_nodes["Type"] == "class"],
                    "Classes",
                    ["Name", "Path", "Module", "LOC"],
                )
                _add_table(
                    self.df_nodes[self.df_nodes["Type"] == "function"],
                    "Functions",
                    ["Name", "Path", "Module", "LOC"],
                )
                _add_table(
                    self.df_nodes[self.df_nodes["Type"].isin(["method", "property"])],
                    "Methods/Props",
                    ["Name", "Path", "Module", "LOC"],
                )
                _add_table(
                    self.df_nodes[self.df_nodes["Type"] == "external"],
                    "External",
                    ["Name", "Path", "Module"],
                )

                if acc_children:
                    display(Markdown("#### Detailed tables"))
                    acc = widgets.Accordion(children=acc_children)
                    for i, t in enumerate(acc_titles):
                        acc.set_title(i, t)
                    display(acc)

    # ==========
    # Navigator: Groups / Modules / Items / Members
    # ==========

    def _refresh_module_groups(self) -> None:
        if self.df_nodes.empty:
            self.sel_groups.options = []
            self.sel_modules.options = []
            return

        df_mod = self.df_nodes[self.df_nodes["Type"] == "module"].copy()
        df_mod = df_mod.sort_values("Path")
        self._modules_all = [
            (str(row["Path"]), str(row["ID"])) for _, row in df_mod.iterrows()
        ]

        groups: Dict[str, Set[str]] = {}
        for label, node_id in self._modules_all:
            g = _module_group(label)
            groups.setdefault(g, set()).add(node_id)

        group_options = [(g, g) for g in sorted(groups.keys())]
        self.sel_groups.options = group_options
        self.sel_modules.options = []
        self.sel_items.options = []
        self.sel_members.options = []
        self.sel_params.options = []
        self.sel_values.options = []

        if group_options:
            self.sel_groups.value = group_options[0][1]

    def _on_group_select(self, change: Dict[str, Any]) -> None:
        group = change["new"]
        if not group:
            return

        mods = [
            (label, node_id)
            for (label, node_id) in self._modules_all
            if label.startswith(group)
        ]
        self.sel_modules.options = mods
        self.sel_items.options = []
        self.sel_members.options = []
        self.sel_params.options = []
        self.sel_values.options = []
        self.current_target_id = None
        if mods:
            self.sel_modules.value = mods[0][1]
        self._refresh_details_from_selection()

    def _on_module_select(self, change: Dict[str, Any]) -> None:
        mod_id = change["new"]
        if not mod_id or self.df_nodes.empty:
            return

        df_items = self.df_nodes[
            (self.df_nodes["Parent"] == mod_id)
            & (self.df_nodes["Type"].isin(["class", "function", "external"]))
        ].copy()
        df_items = df_items.sort_values("Name")
        self._items_all = [
            (f"{r['Type']}: {r['Name']}", str(r["ID"])) for _, r in df_items.iterrows()
        ]
        self.sel_items.options = self._items_all
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
            self._members_all = [
                (f"{r['Type']}: {r['Name']}", str(r["ID"]))
                for _, r in df_members.iterrows()
            ]
            self.sel_members.options = self._members_all
            self.current_target_id = str(node_id)
        else:
            self.sel_members.options = []
            self.current_target_id = str(node_id)

        self._refresh_params_for_current_target()
        self._register_history_from_node(row)
        self._refresh_details_from_selection()

    def _on_member_select(self, change: Dict[str, Any]) -> None:
        node_id = change["new"]
        if not node_id:
            return

        self.current_target_id = str(node_id)
        row = self._get_node_row(node_id)
        if row is not None:
            self._register_history_from_node(row)
        self._refresh_params_for_current_target()
        self._refresh_details_from_selection()

    # ==========
    # Search / History
    # ==========

    def _on_search_change(self, change: Dict[str, Any]) -> None:
        value = change["new"]
        if not value:
            return

        q = str(value).strip()
        if not q or self.df_nodes.empty:
            return

        # 1. 履歴ラベル完全一致なら node_id で特定
        node_id = self.history_map.get(q)
        row = None
        if node_id:
            row = self._get_node_row(node_id)

        # 2. それ以外は Path / Name で部分一致検索
        if row is None:
            mask = self.df_nodes["Path"].astype(str).str.contains(
                q, case=False, na=False
            ) | self.df_nodes["Name"].astype(str).str.contains(q, case=False, na=False)
            hits = self.df_nodes[mask]
            if hits.empty:
                return
            row = hits.iloc[0]

        self._jump_to_row(row)

    def _jump_to_row(self, row: pd.Series) -> None:
        """検索/履歴から指定行へジャンプして選択状態を合わせる。"""
        mod = str(row.get("Module") or "")
        if not mod:
            path = str(row.get("Path") or "")
            mod = path.rsplit(".", 1)[0] if "." in path else path

        group = _module_group(mod)

        # グループ選択
        for label, value in self.sel_groups.options:
            if label == group:
                self.sel_groups.value = value
                break

        # モジュール選択
        for label, value in self.sel_modules.options:
            if label == mod:
                self.sel_modules.value = value
                break

        node_id = str(row.get("ID"))
        t = str(row.get("Type", "")).lower()

        # アイテム / メンバー選択
        if t in {"class", "function", "external"}:
            for label, value in self.sel_items.options:
                if value == node_id:
                    self.sel_items.value = value
                    break
        elif t in {"method", "property"}:
            parent_id = row.get("Parent")
            if parent_id:
                for label, value in self.sel_items.options:
                    if value == parent_id:
                        self.sel_items.value = value
                        break
            for label, value in self.sel_members.options:
                if value == node_id:
                    self.sel_members.value = value
                    break

        self.current_target_id = node_id
        self._refresh_params_for_current_target()
        self._refresh_details_from_selection()

    def _register_history_from_node(self, row: pd.Series) -> None:
        node_id = str(row.get("ID"))
        if not node_id:
            return
        label = f"{row.get('Type')}: {row.get('Path', row.get('Name', node_id))}"
        if label not in self.history_map:
            self.history_targets.append(node_id)
            self.history_labels.append(label)
            self.history_map[label] = node_id
            self.cb_search.options = self.history_labels

    # ==========
    # Node / Param 補助
    # ==========

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
            has_def = not (p.default is inspect._empty)
            default_repr = repr(p.default) if has_def else ""
            pi = ParamInfo(
                name=p.name,
                kind=str(p.kind),
                annotation=ann,
                has_default=has_def,
                default_repr=default_repr,
            )
            params.append(pi)
            self.value_candidates_by_param[p.name] = suggest_values_for_param(pi)

        self.current_params = params
        # Select を更新
        if params:
            self.sel_params.options = [
                (f"{i+1}. {p.name} : {p.annotation or 'Any'}", p.name)
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

    # ==========
    # Inspector / Params / Mermaid
    # ==========

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
                display(Markdown("**Signature**\n\n```python\n" + sig + "\n```"))
            if doc:
                display(Markdown("**DocSummary**\n\n" + html.escape(str(doc))))

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
            display(Markdown("### ⚙️ Parameters & value candidates"))
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
            btns = (
                "<div style='margin-top:8px;'>"
                f"<a download='{self.lib_name}.mmd' "
                f"href='data:text/plain;base64,{b64_mmd}' "
                "style='background:#111827;color:white;padding:6px 10px;"
                "text-decoration:none;border-radius:6px;'>Download .mmd</a>"
                f"<a download='{self.lib_name}.html' "
                f"href='data:text/html;base64,{b64_html}' "
                "style='background:#4B5563;color:white;padding:6px 10px;"
                "text-decoration:none;border-radius:6px;margin-left:8px;'>Download HTML</a>"
                "</div>"
            )
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

    # ==========
    # Params / Values 選択
    # ==========

    def _on_param_select(self, change: Dict[str, Any]) -> None:
        pname = change["new"]
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

    # ==========
    # サンプルコード生成 / 実行
    # ==========

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
        self.generated_code = code

        with self.out_codegen:
            display(Markdown("### 💡 Generated sample code"))
            self._code_textarea = widgets.Textarea(
                value=code,
                layout=widgets.Layout(width="100%", height="320px"),
            )
            display(self._code_textarea)

            b64_py = base64.b64encode(code.encode("utf-8")).decode("ascii")
            fname = (str(row.get("Name") or "sample")).replace(" ", "_")
            btn = (
                "<div style='margin-top:8px;'>"
                f"<a download='{fname}_sample.py' "
                f"href='data:text/x-python;base64,{b64_py}' "
                "style='background:#2563EB;color:white;padding:6px 10px;"
                "text-decoration:none;border-radius:6px;'>Download .py</a>"
                "</div>"
            )
            display(HTML(btn))
            display(
                Markdown(
                    "※ 上記コードは `Compile & Run` ボタンでその場実行もできますが、"
                    "ファイル IO やネットワークなど副作用がある処理の場合は、内容を確認してから実行してください。"
                )
            )
            display(Markdown("---"))
            display(Markdown("#### ▶ Run output"))
            display(self.out_run)

    def _on_run_code(self, _btn: widgets.Button) -> None:
        self.out_run.clear_output()
        if self._code_textarea is not None:
            code = self._code_textarea.value
        else:
            code = self.generated_code

        if not code:
            with self.out_run:
                print("Generate sample code first.")
            return

        with self.out_run:
            print("Compiling & running ...")
            buf = io.StringIO()
            ns: Dict[str, Any] = {}
            try:
                compiled = compile(code, "<sample_code>", "exec")
            except SyntaxError as e:
                print("SyntaxError while compiling sample code:")
                print(e)
                return

            try:
                with redirect_stdout(buf), redirect_stderr(buf):
                    exec(compiled, ns, ns)
            except Exception as e:
                output = buf.getvalue()
                if output:
                    print("=== stdout / stderr ===")
                    print(output)
                    print("=======================")
                print("Exception while executing sample code:")
                print(repr(e))
                return

            output = buf.getvalue()
            if output:
                print("=== stdout / stderr ===")
                print(output)
                print("=======================")
            else:
                print("No stdout/stderr captured.")

            if "result" in ns:
                print("Result variable:")
                print(repr(ns["result"]))

    # ==========
    # レポート出力
    # ==========

    def _on_export_report(self, _btn: widgets.Button) -> None:
        self.out_codegen.clear_output(wait=True)
        report = self._build_markdown_report()
        b64 = base64.b64encode(report.encode("utf-8")).decode("ascii")
        fname = f"CLE_report_{self.lib_name or 'library'}.md"

        with self.out_codegen:
            display(Markdown("### 📄 Exported report (Markdown preview)"))
            preview = "\n".join(report.splitlines()[:80])
            display(Markdown(f"```markdown\n{preview}\n```"))

            link = (
                "<div style='margin-top:8px;'>"
                f"<a download='{fname}' href='data:text/markdown;base64,{b64}' "
                "style='background:#10B981;color:white;padding:6px 10px;"
                "text-decoration:none;border-radius:6px;'>Download report (.md)</a>"
                "</div>"
            )
            display(HTML(link))

    def _build_markdown_report(self) -> str:
        """現在の内容を 1 つの Markdown レポートにまとめる。"""
        lines: List[str] = []
        lib = self.lib_name or "(unknown)"

        lines.append(f"# Cognitive Library Explorer V5 Report — `{lib}`")
        lines.append("")

        # Summary
        if self.summary:
            lines.append("## Summary metrics")
            df_summary = pd.DataFrame(
                {
                    "Metric": list(self.summary.keys()),
                    "Value": list(self.summary.values()),
                }
            )
            lines.append("```text")
            lines.append(df_summary.to_string(index=False))
            lines.append("```")
            lines.append("")

        # Modules / Classes / Functions 概要
        if not self.df_nodes.empty:
            lines.append("## Modules / Classes / Functions")
            df_modules = self.df_nodes[self.df_nodes["Type"] == "module"]
            df_classes = self.df_nodes[self.df_nodes["Type"] == "class"]
            df_funcs = self.df_nodes[self.df_nodes["Type"] == "function"]

            lines.append("### Modules (head)")
            if not df_modules.empty:
                lines.append("```text")
                lines.append(df_modules[["Path"]].head(40).to_string(index=False))
                lines.append("```")
            lines.append("")

            lines.append("### Classes (head)")
            if not df_classes.empty:
                cols = [
                    c for c in ["Name", "Path", "Module"] if c in df_classes.columns
                ]
                lines.append("```text")
                lines.append(df_classes[cols].head(40).to_string(index=False))
                lines.append("```")
            lines.append("")

            lines.append("### Functions (head)")
            if not df_funcs.empty:
                cols = [c for c in ["Name", "Path", "Module"] if c in df_funcs.columns]
                lines.append("```text")
                lines.append(df_funcs[cols].head(40).to_string(index=False))
                lines.append("```")
            lines.append("")

        # 現在のターゲット
        if self.current_target_id:
            row = self._get_node_row(self.current_target_id)
            if row is not None:
                lines.append("## Current target")
                title = f"{row.get('Type', '')}: {row.get('Path', row.get('ID', ''))}"
                lines.append(f"### {title}")
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
                lines.append("```text")
                lines.append(df_basic.to_string(index=False))
                lines.append("```")
                sig = row.get("Signature") or ""
                if sig:
                    lines.append("```python")
                    lines.append(sig)
                    lines.append("```")
                doc = row.get("DocSummary") or ""
                if doc:
                    lines.append("")
                    lines.append("DocSummary:")
                    lines.append("")
                    lines.append(textwrap.indent(str(doc), "> "))
                lines.append("")

        # Param & 候補
        if self.current_params:
            lines.append("## Parameters & value candidates")
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
            lines.append("```text")
            lines.append(df.to_string(index=False))
            lines.append("```")
            lines.append("")

        # Mermaid
        if not self.df_nodes.empty:
            lines.append("## Mermaid diagram")
            mmd, _ = make_mermaid_and_html(
                self.df_nodes, self.df_edges, lib, max_nodes=260
            )
            lines.append("```mermaid")
            lines.append(mmd)
            lines.append("```")
            lines.append("")

        # Sample code
        if self.generated_code:
            lines.append("## Generated sample code")
            lines.append("```python")
            lines.append(self.generated_code)
            lines.append("```")
            lines.append("")

        # Param index overview
        if self.param_counts:
            lines.append("## Param index overview")
            rows = [
                {"ParamName": name, "Count": cnt}
                for name, cnt in sorted(
                    self.param_counts.items(), key=lambda kv: kv[1], reverse=True
                )
            ]
            df_params = pd.DataFrame(rows)
            lines.append("```text")
            lines.append(df_params.to_string(index=False))
            lines.append("```")

        return "\n".join(lines)

    # ==========
    # Param Index
    # ==========

    def _extract_param_names_from_row(self, row: pd.Series) -> List[str]:
        candidates: List[str] = []
        for key in ["ParamNames", "param_names", "Params", "Parameters"]:
            if key in row:
                v = row[key]
                if isinstance(v, (list, tuple, set)):
                    candidates = [str(x) for x in v]
                elif isinstance(v, str) and v.strip():
                    txt = v.strip()
                    if txt.startswith("[") and txt.endswith("]"):
                        inner = txt[1:-1]
                        parts = [p.strip(" '\"") for p in inner.split(",") if p.strip()]
                    else:
                        parts = [p.strip() for p in txt.split(",") if p.strip()]
                    candidates = parts
                break
        cleaned = [
            p
            for p in candidates
            if isinstance(p, str) and p not in ("*args", "**kwargs") and p != ""
        ]
        return cleaned

    def _build_param_index(self) -> None:
        self.param_index = {}
        self.param_counts = {}
        if self.df_nodes.empty or "ID" not in self.df_nodes.columns:
            return

        for _, row in self.df_nodes.iterrows():
            node_id = row.get("ID")
            if not node_id:
                continue
            for p in self._extract_param_names_from_row(row):
                s = self.param_index.setdefault(p, set())
                s.add(node_id)

        for name, ids in self.param_index.items():
            self.param_counts[name] = len(ids)

    def _render_param_index_tab(self) -> None:
        self.out_param_index.clear_output()
        with self.out_param_index:
            if not self.param_index:
                print("No parameter index data.")
                return

            rows = [
                {"ParamName": name, "Count": len(ids)}
                for name, ids in sorted(
                    self.param_index.items(), key=lambda kv: len(kv[1]), reverse=True
                )
            ]
            df = pd.DataFrame(rows)
            display(Markdown("### 🧬 Unique parameter names"))
            display(df.head(80))

            txt_filter = widgets.Text(
                description="Filter:",
                placeholder="param 名の一部を入力",
                layout=widgets.Layout(width="40%"),
            )
            sel = widgets.Select(
                options=[
                    (f"{r['ParamName']} ({r['Count']})", r["ParamName"]) for r in rows
                ],
                layout=widgets.Layout(width="40%", height="260px"),
            )
            out_table = widgets.Output()

            def on_filter(change: Dict[str, Any]) -> None:
                q = change["new"].lower()
                if not q:
                    subset = rows
                else:
                    subset = [r for r in rows if q in r["ParamName"].lower()]
                if not subset:
                    sel.options = [("No match", None)]
                else:
                    sel.options = [
                        (f"{r['ParamName']} ({r['Count']})", r["ParamName"])
                        for r in subset
                    ]

            def on_select(change: Dict[str, Any]) -> None:
                name = change["new"]
                out_table.clear_output()
                if not name:
                    return
                ids = self.param_index.get(name, set())
                if not ids:
                    return
                df_hits = self.df_nodes[self.df_nodes["ID"].isin(list(ids))].copy()
                with out_table:
                    display(Markdown(f"#### APIs using param `{name}` (top 80)"))
                    cols = [
                        c
                        for c in ["Type", "Name", "Path", "Module", "Signature"]
                        if c in df_hits.columns
                    ]
                    display(df_hits[cols].head(80))

            txt_filter.observe(on_filter, names="value")
            sel.observe(on_select, names="value")

            display(widgets.HBox([txt_filter, sel]))
            display(out_table)

    # ==========
    # Global Insight
    # ==========

    def _update_global_history(self) -> None:
        if not self.lib_name or not self.summary:
            return
        lib = self.lib_name
        unique_params_set: Set[str] = set(self.param_index.keys())

        roles = {"has_plot": False, "has_forecast": False, "has_client": False}
        if not self.df_nodes.empty and "Name" in self.df_nodes.columns:
            names = " ".join(str(n) for n in self.df_nodes["Name"].tolist()).lower()
            if any(k in names for k in ["plot", "figure", "axis", "chart"]):
                roles["has_plot"] = True
            if any(k in names for k in ["forecast", "predict", "prediction"]):
                roles["has_forecast"] = True
            if any(k in names for k in ["client", "api", "request"]):
                roles["has_client"] = True

        self.global_history[lib] = {
            "summary": self.summary,
            "unique_params": unique_params_set,
            "roles": roles,
        }

    def _render_global_insight_tab(self) -> None:
        self.out_global.clear_output()
        with self.out_global:
            if not self.global_history:
                print("Analyze at least one library to see global insights.")
                return

            display(Markdown("### 🌐 Global insights across analyzed libraries"))

            rows = []
            for lib, info in self.global_history.items():
                s = info["summary"]
                rows.append(
                    {
                        "Library": lib,
                        "Modules": s.get("Modules", 0),
                        "Classes": s.get("Classes", 0),
                        "Functions": s.get("Functions", 0),
                        "Methods/Props": s.get("Methods/Props", 0),
                        "UniqueParams": s.get("UniqueParamNames", 0),
                    }
                )
            df_libs = pd.DataFrame(rows)
            display(df_libs)

            # パラメータ名のグローバル頻度
            global_param_counts: Dict[str, int] = {}
            for info in self.global_history.values():
                for p in info["unique_params"]:
                    global_param_counts[p] = global_param_counts.get(p, 0) + 1

            if global_param_counts:
                rows = [
                    {"ParamName": name, "Libraries": cnt}
                    for name, cnt in sorted(
                        global_param_counts.items(), key=lambda kv: kv[1], reverse=True
                    )
                ]
                df_gp = pd.DataFrame(rows)
                display(Markdown("#### Param names shared across libraries"))
                display(df_gp.head(80))

            # ライブラリ間の類似度 (Jaccard)
            libs = list(self.global_history.keys())
            pairs = []
            for i in range(len(libs)):
                for j in range(i + 1, len(libs)):
                    a = libs[i]
                    b = libs[j]
                    pa = self.global_history[a]["unique_params"]
                    pb = self.global_history[b]["unique_params"]
                    if not pa or not pb:
                        continue
                    inter = len(pa & pb)
                    union = len(pa | pb)
                    jacc = inter / union if union else 0.0
                    pairs.append(
                        {
                            "LibA": a,
                            "LibB": b,
                            "SharedParams": inter,
                            "Jaccard": round(jacc, 3),
                        }
                    )

            if pairs:
                df_pairs = pd.DataFrame(pairs).sort_values("Jaccard", ascending=False)
                display(Markdown("#### Similar API surface (by param names)"))
                display(df_pairs.head(40))

                insights: List[str] = []
                for _, row in df_pairs.head(10).iterrows():
                    if row["Jaccard"] >= 0.35 and row["SharedParams"] >= 5:
                        insights.append(
                            f"- `{row['LibA']}` と `{row['LibB']}` は引数パターンがかなり似ています "
                            f"(Jaccard={row['Jaccard']}, shared={row['SharedParams']})。"
                            "一方を学ぶともう一方もスムーズに使える可能性があります。"
                        )

                # 役割の補完関係
                for a in libs:
                    roles_a = self.global_history[a]["roles"]
                    for b in libs:
                        if a == b:
                            continue
                        roles_b = self.global_history[b]["roles"]
                        if (
                            roles_a["has_forecast"]
                            and not roles_a["has_plot"]
                            and roles_b["has_plot"]
                        ):
                            insights.append(
                                f"- `{a}` は予測/推論寄り、`{b}` は可視化寄りの API を多く含みます。"
                                "時系列予測の結果をプロットする用途では組み合わせ利用が有効かもしれません。"
                            )

                if insights:
                    display(Markdown("#### 💡 Heuristic insights"))
                    display(Markdown("\n".join(insights)))
