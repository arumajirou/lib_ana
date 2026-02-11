# ファイルパス: C:\lib_ana\src\v6\core\codegen_v6.py
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

import pandas as pd


def _extract_params(params_obj: Any) -> List[Dict[str, Any]]:
    if params_obj is None:
        return []
    if isinstance(params_obj, list):
        out: List[Dict[str, Any]] = []
        for it in params_obj:
            if isinstance(it, dict) and it.get("name"):
                out.append(it)
            elif isinstance(it, str) and it:
                out.append({"name": it, "kind": "", "annotation": "", "has_default": False, "default_repr": ""})
        return out
    if isinstance(params_obj, dict):
        return [{"name": str(k), "kind": "", "annotation": "", "has_default": False, "default_repr": ""} for k in params_obj.keys()]
    return []


def _fmt_default(p: Dict[str, Any]) -> str:
    if p.get("has_default") and p.get("default_repr"):
        return str(p.get("default_repr"))
    # annotationがあるときはヒントとしてコメントに残す
    ann = str(p.get("annotation") or "").strip()
    if ann:
        return f"None  # TODO: {ann}"
    return "None  # TODO"


def _indent(lines: List[str], n: int = 4) -> List[str]:
    pad = " " * n
    return [pad + x if x else x for x in lines]


def _is_timesfm_configs_class(module: str, path: str, t: str, name: str) -> bool:
    if t != "class":
        return False
    m = str(module or "")
    p = str(path or "")
    if not name or not str(name).endswith("Config"):
        return False
    return m.startswith("timesfm.configs") or p.startswith("timesfm.configs.")


def _find_class_row(nodes: pd.DataFrame, module_prefix: str, class_name: str) -> Optional[pd.Series]:
    if nodes is None or nodes.empty:
        return None
    if "Type" not in nodes.columns:
        return None
    cand = nodes[(nodes["Type"] == "class") & (nodes["Name"].astype(str) == str(class_name))].copy()
    if cand.empty:
        return None
    if "Path" in cand.columns:
        exact = cand[cand["Path"].astype(str) == f"{module_prefix}.{class_name}"]
        if not exact.empty:
            return exact.iloc[0]
    if "Module" in cand.columns:
        scoped = cand[cand["Module"].astype(str).str.startswith(module_prefix)]
        if not scoped.empty:
            return scoped.iloc[0]
    return cand.iloc[0]


def _build_timesfm_param_lines(class_name: str, params_wo_self: List[Dict[str, Any]]) -> List[str]:
    hints: Dict[str, Dict[str, str]] = {
        "ForecastConfig": {
            "max_context": "モデルに入力する最大過去データ点数",
            "max_horizon": "一度に予測する最大ステップ数",
            "normalize_inputs": "入力データを正規化するか",
            "window_size": "分解予測時のウィンドウサイズ",
            "per_core_batch_size": "コアごとのバッチサイズ",
            "use_continuous_quantile_head": "連続分位点ヘッドを使用するか",
            "force_flip_invariance": "反転不変性を強制するか",
            "infer_is_positive": "出力が非負であることを保証するか",
            "fix_quantile_crossing": "分位点の交差を修正するか",
            "return_backcast": "過去データの再構成を返すか",
        },
        "RandomFourierFeaturesConfig": {
            "input_dims": "入力次元数",
            "output_dims": "出力次元数",
            "projection_stddev": "投影重みの初期化標準偏差",
            "use_bias": "バイアス項を使用するか",
        },
        "ResidualBlockConfig": {
            "input_dims": "入力次元数",
            "hidden_dims": "隠れ層の次元数",
            "output_dims": "出力次元数",
            "use_bias": "バイアス項を使用するか",
            "activation": "活性化関数",
        },
        "TransformerConfig": {
            "model_dims": "モデル次元",
            "hidden_dims": "FFNの隠れ次元",
            "num_heads": "注意ヘッド数",
            "attention_norm": "Attention正規化方式",
            "feedforward_norm": "FFN正規化方式",
            "qk_norm": "QK正規化方式",
            "use_bias": "線形層にバイアスを使うか",
            "use_rotary_position_embeddings": "RoPEを使用するか",
            "ff_activation": "FFN活性化関数",
            "fuse_qkv": "QKVを融合実装するか",
        },
        "StackedTransformersConfig": {
            "num_layers": "積み上げるTransformer層数",
            "transformer": "TransformerConfigオブジェクト",
        },
    }
    cm = hints.get(class_name, {})
    lines: List[str] = []
    for p in params_wo_self:
        pn = str(p.get("name") or "").strip()
        if not pn:
            continue
        right = f"{pn}={_fmt_default(p)},"
        hint = cm.get(pn, "")
        if hint:
            lines.append(f"{right}  # {hint}")
        else:
            lines.append(right)
    return lines


def _generate_timesfm_config_stub(
    nodes: pd.DataFrame,
    *,
    name: str,
    params_wo_self: List[Dict[str, Any]],
    include_header: bool = True,
) -> str:
    header = []
    if include_header:
        header = ["# Auto-generated call stub (CLE V6)", "", "# NOTE: TODO のところを埋めてください", ""]

    if name == "StackedTransformersConfig":
        tf_row = _find_class_row(nodes, "timesfm.configs", "TransformerConfig")
        tf_params: List[Dict[str, Any]] = []
        if tf_row is not None:
            tf_params = _extract_params(tf_row.get("Params"))
            if not tf_params:
                tf_path = str(tf_row.get("Path") or "")
                # fallback: inspect.signature
                from v6.core.inspect_params_v6 import inspect_params_from_path
                fb = inspect_params_from_path(tf_path) if tf_path else None
                tf_params = fb or []
        tf_params_wo_self = [p for p in tf_params if str(p.get("name")) not in {"self", "cls"}]
        tf_args = _build_timesfm_param_lines("TransformerConfig", tf_params_wo_self)
        st_args: List[str] = []
        for p in params_wo_self:
            pn = str(p.get("name") or "").strip()
            if not pn:
                continue
            if pn == "transformer":
                st_args.append("transformer=transformer_config,  # TransformerConfigオブジェクト")
            else:
                line = f"{pn}={_fmt_default(p)},"
                if pn == "num_layers":
                    line += "  # 積み上げるTransformer層数"
                st_args.append(line)
        body = [
            "from timesfm.configs import TransformerConfig, StackedTransformersConfig",
            "",
            "# 1. 個別のTransformer層の詳細設定",
            "transformer_config = TransformerConfig(",
            *_indent(tf_args),
            ")",
            "",
            "# 2. Transformerを積み上げる設定の作成",
            "obj = StackedTransformersConfig(",
            *_indent(st_args),
            ")",
            "",
            'print(f"Stacked Transformers: {obj.num_layers} layers of {obj.transformer.model_dims} dims")',
            "",
        ]
        return "\n".join(header + body)

    import_line = f"from timesfm.configs import {name}"
    args = _build_timesfm_param_lines(name, params_wo_self)
    top_comment = {
        "ForecastConfig": "# 予測設定の作成",
        "RandomFourierFeaturesConfig": "# ランダムフーリエ特徴量レイヤーの設定作成",
        "ResidualBlockConfig": "# 残差ブロックの設定作成",
        "TransformerConfig": "# Transformer層の設定作成",
    }.get(name, f"# {name} の設定作成")
    print_line = {
        "ForecastConfig": 'print(f"ForecastConfig created: context={obj.max_context}, horizon={obj.max_horizon}")',
        "RandomFourierFeaturesConfig": 'print(f"RFF Config created: input={obj.input_dims}, output={obj.output_dims}")',
        "ResidualBlockConfig": 'print(f"ResidualBlock Config created: {obj.input_dims} -> {obj.hidden_dims} -> {obj.output_dims} (act={obj.activation})")',
        "TransformerConfig": 'print(f"TransformerConfig created: dims={obj.model_dims}, heads={obj.num_heads}")',
    }.get(name, f'print(f"{name} created")')
    body = [
        import_line,
        "",
        top_comment,
        "# TODO: 用途に合わせて各パラメータを調整してください",
        f"obj = {name}(",
        *_indent(args),
        ")",
        "",
        print_line,
        "",
    ]
    return "\n".join(header + body)


def generate_timesfm_configs_bundle(nodes: pd.DataFrame, module_prefix: str = "timesfm.configs") -> str:
    """timesfm.configs の主要 Config をまとめて自動生成する。"""
    if nodes is None or nodes.empty:
        return "# No nodes available"
    preferred = [
        "ForecastConfig",
        "RandomFourierFeaturesConfig",
        "ResidualBlockConfig",
        "TransformerConfig",
        "StackedTransformersConfig",
    ]
    blocks: List[str] = ["# Auto-generated timesfm.configs bundle (CLE V6)", ""]
    found = 0
    for idx, cls in enumerate(preferred):
        row = _find_class_row(nodes, module_prefix, cls)
        if row is None:
            continue
        found += 1
        params = _extract_params(row.get("Params"))
        if not params:
            from v6.core.inspect_params_v6 import inspect_params_from_path
            pth = str(row.get("Path") or "")
            fb = inspect_params_from_path(pth) if pth else None
            params = fb or []
        ps = [p for p in params if str(p.get("name")) not in {"self", "cls"}]
        one = _generate_timesfm_config_stub(
            nodes,
            name=str(row.get("Name") or cls),
            params_wo_self=ps,
            include_header=False,
        )
        if idx > 0:
            blocks += ["# ----", ""]
        blocks += [one.rstrip(), ""]
    if found == 0:
        return "# No timesfm.configs classes found"
    return "\n".join(blocks).rstrip() + "\n"


def generate_call_stub(
    nodes: pd.DataFrame,
    *,
    target_id: str,
    fallback_params: Optional[List[Dict[str, Any]]] = None,
) -> str:
    """選択ノード（function/class/method/property）を「引数全部入りの呼び出しテンプレ」にする。"""
    if nodes is None or nodes.empty or not target_id:
        return "# No selection"

    row = nodes[nodes["ID"].astype(str) == str(target_id)].head(1)
    if row.empty:
        return "# Node not found"
    r = row.iloc[0]
    t = str(r.get("Type", ""))
    name = str(r.get("Name", ""))
    path = str(r.get("Path", ""))
    module = str(r.get("Module", ""))
    parent_id = str(r.get("Parent", ""))
    params = _extract_params(r.get("Params"))
    if not params and fallback_params:
        params = fallback_params

    # self/cls は除外（methodや__init__向け）
    params_wo_self = [p for p in params if str(p.get("name")) not in {"self", "cls"}]

    def build_args(ps: List[Dict[str, Any]]) -> List[str]:
        if not ps:
            return []
        lines: List[str] = []
        for p in ps:
            pn = str(p.get("name"))
            if not pn:
                continue
            lines.append(f"{pn}={_fmt_default(p)},")
        return lines

    header = ["# Auto-generated call stub (CLE V6)", "", "# NOTE: TODO のところを埋めてください", ""]

    # function
    if t == "function":
        imp_mod = module or ".".join(path.split(".")[:-1])
        imp = f"from {imp_mod} import {name}" if imp_mod else f"import {name}"
        args = build_args(params_wo_self)
        call = [f"result = {name}("] + _indent(args) + [")"]
        return "\n".join(header + [imp, ""] + call + [""])

    # class -> constructor
    if t == "class":
        if _is_timesfm_configs_class(module, path, t, name):
            return _generate_timesfm_config_stub(
                nodes,
                name=name,
                params_wo_self=params_wo_self,
                include_header=True,
            )
        imp_mod = module or ".".join(path.split(".")[:-1])
        imp = f"from {imp_mod} import {name}" if imp_mod else f"import {name}"
        args = build_args(params_wo_self)
        call = [f"obj = {name}("] + _indent(args) + [")"]
        return "\n".join(header + [imp, ""] + call + [""])

    # method/property
    if t in {"method", "property"}:
        # 親クラスを探す
        cls_row = nodes[nodes["ID"].astype(str) == str(parent_id)].head(1)
        cls_name = str(cls_row.iloc[0].get("Name", "MyClass")) if not cls_row.empty else "MyClass"
        cls_path = str(cls_row.iloc[0].get("Path", "")) if not cls_row.empty else ""
        cls_module = str(cls_row.iloc[0].get("Module", "")) if not cls_row.empty else ""

        imp_mod = cls_module or ".".join(cls_path.split(".")[:-1])
        imp = f"from {imp_mod} import {cls_name}" if imp_mod else f"import {cls_name}"

        # コンストラクタ引数は取れないことが多いので、空にして TODO コメント
        obj_lines = [f"obj = {cls_name}()  # TODO: __init__ args"]

        if t == "property":
            access = [f"value = obj.{name}"]
            return "\n".join(header + [imp, ""] + obj_lines + [""] + access + [""])

        args = build_args(params_wo_self)
        call = [f"result = obj.{name}("] + _indent(args) + [")"]
        return "\n".join(header + [imp, ""] + obj_lines + [""] + call + [""])

    # fallback
    return "\n".join(header + [f"# Unsupported node type: {t}", f"# Path: {path}"])
