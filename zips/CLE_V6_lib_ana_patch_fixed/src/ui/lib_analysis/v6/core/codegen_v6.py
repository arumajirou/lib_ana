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
