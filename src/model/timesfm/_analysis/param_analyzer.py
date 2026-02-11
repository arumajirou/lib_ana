# /mnt/e/env/ts/lib_ana/src/model/timesfm/_analysis/param_analyzer.py
from __future__ import annotations

import ast
import builtins
import dataclasses
import importlib
import inspect
import json
import math
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import pandas as pd


# -----------------------------
# データ構造
# -----------------------------
@dataclass
class CallSite:
    ipynb_path: str
    cell_index: int
    lineno: int
    col: int
    callee_expr: str           # 例: timesfm.ForecastConfig
    code_snippet: str          # 例: timesfm.ForecastConfig(max_context=512,...)
    keywords: Dict[str, str]   # param -> expr(str)
    positional: List[str]      # positional expr(str)


@dataclass
class ParamRow:
    callee: str
    param: str
    kind: str  # "positional_only" | "positional_or_keyword" | "keyword_only" | "var_positional" | "var_keyword"
    required: bool
    default_repr: str
    annotated_type: str
    specified: bool
    specified_expr: str
    value_kind: str  # "fixed_literal" | "fixed_from_const" | "variable_expr" | "default_used" | "unknown"
    value_literal: Any
    callsite: str
    filepath: str
    source_lineno: Optional[int]
    inferred_min: Any
    inferred_max: Any
    inferred_allowed: Any
    notes: str


# -----------------------------
# Notebook 読み込み
# -----------------------------
def load_ipynb_code_cells(ipynb_path: Union[str, Path]) -> List[str]:
    p = Path(ipynb_path)
    obj = json.loads(p.read_text(encoding="utf-8"))
    cells = obj.get("cells", [])
    code_cells = []
    for c in cells:
        if c.get("cell_type") == "code":
            src = "".join(c.get("source", []))
            code_cells.append(src)
    return code_cells


# -----------------------------
# 文字列化ユーティリティ
# -----------------------------
def _node_to_str(node: ast.AST, source: str) -> str:
    seg = ast.get_source_segment(source, node)
    if seg is not None:
        return seg.strip()
    # フォールバック
    try:
        return ast.unparse(node).strip()
    except Exception:
        return node.__class__.__name__


def _literal_eval_or_none(expr_node: ast.AST) -> Tuple[bool, Any]:
    """ast.literal_eval できれば fixed literal とみなす"""
    try:
        v = ast.literal_eval(expr_node)
        return True, v
    except Exception:
        return False, None


def _is_simple_const_assign(stmt: ast.stmt) -> Optional[Tuple[str, Any]]:
    """
    cell内で `NAME = <literal>` みたいな定数代入だけ拾う
    """
    if isinstance(stmt, ast.Assign) and len(stmt.targets) == 1 and isinstance(stmt.targets[0], ast.Name):
        ok, v = _literal_eval_or_none(stmt.value)
        if ok:
            return stmt.targets[0].id, v
    return None


# -----------------------------
# Call 抽出（AST）
# -----------------------------
class _CallCollector(ast.NodeVisitor):
    def __init__(self, ipynb_path: str, cell_index: int, source: str, const_env: Dict[str, Any]):
        self.ipynb_path = ipynb_path
        self.cell_index = cell_index
        self.source = source
        self.const_env = const_env
        self.calls: List[CallSite] = []

    def visit_Call(self, node: ast.Call):
        callee_expr = _node_to_str(node.func, self.source)
        code_snippet = _node_to_str(node, self.source)

        positional = [_node_to_str(a, self.source) for a in node.args]
        keywords: Dict[str, str] = {}
        for kw in node.keywords:
            if kw.arg is None:
                # **kwargs は解析困難なので丸ごと保持
                keywords["**kwargs"] = _node_to_str(kw.value, self.source)
            else:
                keywords[kw.arg] = _node_to_str(kw.value, self.source)

        lineno = getattr(node, "lineno", 0)
        col = getattr(node, "col_offset", 0)

        self.calls.append(
            CallSite(
                ipynb_path=self.ipynb_path,
                cell_index=self.cell_index,
                lineno=lineno,
                col=col,
                callee_expr=callee_expr,
                code_snippet=code_snippet,
                keywords=keywords,
                positional=positional,
            )
        )
        self.generic_visit(node)


def extract_calls_from_ipynb(ipynb_path: Union[str, Path]) -> List[CallSite]:
    ipynb_path = str(ipynb_path)
    code_cells = load_ipynb_code_cells(ipynb_path)
    all_calls: List[CallSite] = []
    for i, src in enumerate(code_cells):
        # cell内の単純定数代入を拾う（固定値判定を少し賢くする）
        const_env: Dict[str, Any] = {}
        try:
            tree = ast.parse(src)
            for st in tree.body:
                kv = _is_simple_const_assign(st)
                if kv:
                    const_env[kv[0]] = kv[1]
        except Exception:
            tree = ast.parse("")  # 空

        collector = _CallCollector(ipynb_path, i, src, const_env)
        collector.visit(tree)
        all_calls.extend(collector.calls)
    return all_calls


# -----------------------------
# callable 解決（文字列 -> 実体）
# -----------------------------
def _import_attr(dotted: str) -> Any:
    """
    "a.b.c" を import して getattr していく
    """
    parts = dotted.split(".")
    # 最長モジュールを探す
    for k in range(len(parts), 0, -1):
        mod_name = ".".join(parts[:k])
        try:
            mod = importlib.import_module(mod_name)
            obj = mod
            for attr in parts[k:]:
                obj = getattr(obj, attr)
            return obj
        except Exception:
            continue
    raise ImportError(f"Cannot resolve: {dotted}")


def resolve_callable(expr: str) -> Optional[Any]:
    """
    ASTから取った callee_expr 例:
      - timesfm.ForecastConfig
      - TimeSeriesdata
      - obj.compile
    これを “できるだけ” 実体へ寄せる。
    """
    expr = expr.strip()

    # 1) dotted import できそうなら
    if re.match(r"^[A-Za-z_]\w*(\.[A-Za-z_]\w*)+$", expr):
        try:
            return _import_attr(expr)
        except Exception:
            return None

    # 2) builtins/グローバル名（Notebook実行中に有効なら取りうるが、ここは静的なので弱い）
    if hasattr(builtins, expr):
        return getattr(builtins, expr)

    return None


# -----------------------------
# シグネチャ情報
# -----------------------------
def get_signature_rows(callable_obj: Any) -> List[Dict[str, Any]]:
    sig = inspect.signature(callable_obj)
    rows = []
    for name, p in sig.parameters.items():
        if p.kind == inspect.Parameter.POSITIONAL_ONLY:
            kind = "positional_only"
        elif p.kind == inspect.Parameter.POSITIONAL_OR_KEYWORD:
            kind = "positional_or_keyword"
        elif p.kind == inspect.Parameter.KEYWORD_ONLY:
            kind = "keyword_only"
        elif p.kind == inspect.Parameter.VAR_POSITIONAL:
            kind = "var_positional"
        else:
            kind = "var_keyword"

        required = (p.default is inspect._empty) and (p.kind not in (inspect.Parameter.VAR_POSITIONAL, inspect.Parameter.VAR_KEYWORD))
        default_repr = "" if p.default is inspect._empty else repr(p.default)
        anno = "" if p.annotation is inspect._empty else repr(p.annotation)

        rows.append(
            {
                "param": name,
                "kind": kind,
                "required": required,
                "default_repr": default_repr,
                "annotated_type": anno,
            }
        )
    return rows


# -----------------------------
# 値の固定/変動 判定
# -----------------------------
def classify_value_expr(expr: str, cell_source: str) -> Tuple[str, Any]:
    """
    exprが literal なら fixed_literal
    cell内で NAME=<literal> の定数代入があれば NAME を fixed_from_const にできる
    それ以外は variable_expr
    """
    expr = expr.strip()

    try:
        tree = ast.parse(cell_source)
        const_env: Dict[str, Any] = {}
        for st in tree.body:
            kv = _is_simple_const_assign(st)
            if kv:
                const_env[kv[0]] = kv[1]
    except Exception:
        const_env = {}

    try:
        node = ast.parse(expr).body[0].value
    except Exception:
        return "unknown", None

    ok, v = _literal_eval_or_none(node)
    if ok:
        return "fixed_literal", v

    if isinstance(node, ast.Name) and node.id in const_env:
        return "fixed_from_const", const_env[node.id]

    return "variable_expr", None


# -----------------------------
# 制約推定（ヒューリスティック）
# -----------------------------
def infer_numeric_constraints_from_source(callable_obj: Any) -> Dict[str, Dict[str, Any]]:
    """
    関数/メソッドのソースから、if/assert の比較を拾って min/max を推定する。
    完全ではないが “根拠のある下限/上限候補” を拾えることが多い。
    """
    try:
        src = inspect.getsource(callable_obj)
        src_path = inspect.getsourcefile(callable_obj) or ""
        src_lineno = inspect.getsourcelines(callable_obj)[1]
    except Exception:
        return {}

    try:
        tree = ast.parse(src)
    except Exception:
        return {}

    constraints: Dict[str, Dict[str, Any]] = {}

    def _upd_min(name: str, val: Any, note: str):
        d = constraints.setdefault(name, {"min": None, "max": None, "allowed": None, "notes": []})
        if isinstance(val, (int, float)) and (d["min"] is None or val > d["min"]):
            d["min"] = val
        d["notes"].append(note)

    def _upd_max(name: str, val: Any, note: str):
        d = constraints.setdefault(name, {"min": None, "max": None, "allowed": None, "notes": []})
        if isinstance(val, (int, float)) and (d["max"] is None or val < d["max"]):
            d["max"] = val
        d["notes"].append(note)

    def _extract_name(node: ast.AST) -> Optional[str]:
        if isinstance(node, ast.Name):
            return node.id
        return None

    def _extract_number(node: ast.AST) -> Optional[Union[int, float]]:
        ok, v = _literal_eval_or_none(node)
        if ok and isinstance(v, (int, float)):
            return v
        return None

    # if / assert の Compare を拾う
    for n in ast.walk(tree):
        if isinstance(n, ast.Assert) and isinstance(n.test, ast.Compare):
            cmp = n.test
        elif isinstance(n, ast.If) and isinstance(n.test, ast.Compare):
            cmp = n.test
        else:
            continue

        if len(cmp.ops) != 1 or len(cmp.comparators) != 1:
            continue

        left = cmp.left
        op = cmp.ops[0]
        right = cmp.comparators[0]

        name_l = _extract_name(left)
        name_r = _extract_name(right)
        num_l = _extract_number(left)
        num_r = _extract_number(right)

        # パターン: if x < 10
        if name_l and num_r is not None:
            if isinstance(op, ast.Lt):
                _upd_max(name_l, num_r, f"{src_path}:{src_lineno}  {name_l} < {num_r}")
            elif isinstance(op, ast.LtE):
                _upd_max(name_l, num_r, f"{src_path}:{src_lineno}  {name_l} <= {num_r}")
            elif isinstance(op, ast.Gt):
                _upd_min(name_l, num_r, f"{src_path}:{src_lineno}  {name_l} > {num_r}")
            elif isinstance(op, ast.GtE):
                _upd_min(name_l, num_r, f"{src_path}:{src_lineno}  {name_l} >= {num_r}")

        # パターン: if 1 <= x
        if num_l is not None and name_r:
            if isinstance(op, ast.Lt):
                _upd_min(name_r, num_l, f"{src_path}:{src_lineno}  {num_l} < {name_r}")
            elif isinstance(op, ast.LtE):
                _upd_min(name_r, num_l, f"{src_path}:{src_lineno}  {num_l} <= {name_r}")
            elif isinstance(op, ast.Gt):
                _upd_max(name_r, num_l, f"{src_path}:{src_lineno}  {num_l} > {name_r}")
            elif isinstance(op, ast.GtE):
                _upd_max(name_r, num_l, f"{src_path}:{src_lineno}  {num_l} >= {name_r}")

    return constraints


# -----------------------------
# メイン：対応表生成
# -----------------------------
def build_param_mapping_table(
    ipynb_path: Union[str, Path],
    target_callees: List[str],
    export_csv_path: Optional[Union[str, Path]] = None,
) -> pd.DataFrame:
    """
    - ipynb 内の Call を全部拾う
    - target_callees（例: ["timesfm.ForecastConfig", "timesfm.data_loader.TimeSeriesdata"]）に一致する callsite を解析
    - 引数指定有無、固定/変動、推定制約(min/max) を列として持つ対応表 DataFrame を返す
    """
    ipynb_path = str(ipynb_path)
    calls = extract_calls_from_ipynb(ipynb_path)

    # 解析対象 callsite に絞る（callee_expr が target と一致 or 末尾一致）
    def _match(callee_expr: str, target: str) -> bool:
        if callee_expr == target:
            return True
        # 例: from timesfm.data_loader import TimeSeriesdata -> callee_expr == "TimeSeriesdata"
        if callee_expr.split(".")[-1] == target.split(".")[-1]:
            return True
        return False

    matched: List[CallSite] = []
    for cs in calls:
        if any(_match(cs.callee_expr, t) for t in target_callees):
            matched.append(cs)

    rows: List[ParamRow] = []

    # targetごとに callable を解決・制約推定
    callee_obj_cache: Dict[str, Any] = {}
    constraint_cache: Dict[str, Dict[str, Dict[str, Any]]] = {}

    for target in target_callees:
        obj = resolve_callable(target)
        if obj is not None:
            callee_obj_cache[target] = obj
            constraint_cache[target] = infer_numeric_constraints_from_source(obj)
        else:
            callee_obj_cache[target] = None
            constraint_cache[target] = {}

    # callsiteごとにシグネチャに照合
    for cs in matched:
        # cs.callee_expr に最も近いtargetを決める（末尾一致優先）
        best = None
        for t in target_callees:
            if cs.callee_expr == t:
                best = t
                break
        if best is None:
            # 末尾一致
            for t in target_callees:
                if cs.callee_expr.split(".")[-1] == t.split(".")[-1]:
                    best = t
                    break
        if best is None:
            continue

        obj = callee_obj_cache.get(best)
        if obj is None:
            # callable が解決できない場合でも、呼び出しの情報だけは残す（引数指定の有無など）
            # ただし required/default などは不明
            callsite_str = f"{cs.ipynb_path}#cell{cs.cell_index}:L{cs.lineno}"
            for k, expr in cs.keywords.items():
                vk, vv = classify_value_expr(expr, load_ipynb_code_cells(cs.ipynb_path)[cs.cell_index])
                rows.append(
                    ParamRow(
                        callee=best,
                        param=k,
                        kind="unknown",
                        required=False,
                        default_repr="",
                        annotated_type="",
                        specified=True,
                        specified_expr=expr,
                        value_kind=vk,
                        value_literal=vv,
                        callsite=callsite_str,
                        filepath="",
                        source_lineno=None,
                        inferred_min=None,
                        inferred_max=None,
                        inferred_allowed=None,
                        notes="callable unresolved (import/path mismatch?)",
                    )
                )
            continue

        sig_rows = get_signature_rows(obj)
        constraints = constraint_cache.get(best, {})

        # 呼び出しソース断片（固定/変動判定のため）
        cell_src = load_ipynb_code_cells(cs.ipynb_path)[cs.cell_index]

        # 位置引数をシグネチャに割り当て
        sig = inspect.signature(obj)
        param_names = list(sig.parameters.keys())

        provided_pos = cs.positional[:]  # expr list
        provided_kw = cs.keywords.copy()

        # **kwargs は精密に展開不能
        has_kwargs_blob = "**kwargs" in provided_kw

        callsite_str = f"{cs.ipynb_path}#cell{cs.cell_index}:L{cs.lineno}"
        src_file = inspect.getsourcefile(obj) or ""
        src_lineno = None
        try:
            src_lineno = inspect.getsourcelines(obj)[1]
        except Exception:
            pass

        # 位置引数 -> param へ割当（VAR_POSITIONALはまとめて扱う）
        bound = None
        try:
            # 解析用にダミー値を使わず bind_partial で “形” だけ束縛
            # ただし exprは文字列なので実値にできない。ここは “何が指定されたか” のみ見る。
            # bind_partialに渡す実値は不要なので、個数だけ合わせるため None を入れる。
            dummy_args = [None] * len(provided_pos)
            dummy_kwargs = {k: None for k in provided_kw.keys() if k != "**kwargs"}
            bound = sig.bind_partial(*dummy_args, **dummy_kwargs)
        except Exception:
            bound = None

        # 各paramについて行を作る
        for sr in sig_rows:
            p = sr["param"]
            kind = sr["kind"]
            required = sr["required"]
            default_repr = sr["default_repr"]
            annotated_type = sr["annotated_type"]

            specified = False
            specified_expr = ""
            value_kind = "default_used"
            value_literal = None
            notes = ""

            # 位置で指定されたか？
            # bound.arguments はダミーなので “指定されたか” の判定に使う
            if bound is not None and p in bound.arguments:
                specified = True
                # 実expr文字列へ戻す：位置 or keyword
                if p in provided_kw:
                    specified_expr = provided_kw[p]
                else:
                    # 位置引数の何番目か推定
                    try:
                        idx = list(bound.arguments.keys()).index(p)
                        if idx < len(provided_pos):
                            specified_expr = provided_pos[idx]
                    except Exception:
                        specified_expr = ""
            elif p in provided_kw:
                specified = True
                specified_expr = provided_kw[p]

            if specified and specified_expr:
                vk, vv = classify_value_expr(specified_expr, cell_src)
                value_kind = vk
                value_literal = vv
            elif specified and not specified_expr:
                value_kind = "unknown"
            else:
                value_kind = "default_used"

            # 制約推定
            c = constraints.get(p, {})
            inferred_min = c.get("min")
            inferred_max = c.get("max")
            inferred_allowed = c.get("allowed")
            if c.get("notes"):
                notes = " | ".join(c["notes"])[:400]

            if has_kwargs_blob and not specified:
                # **kwargs があると未指定でも入ってる可能性がある
                notes = (notes + " ; " if notes else "") + "has **kwargs: may override"

            rows.append(
                ParamRow(
                    callee=best,
                    param=p,
                    kind=kind,
                    required=required,
                    default_repr=default_repr,
                    annotated_type=annotated_type,
                    specified=specified,
                    specified_expr=specified_expr,
                    value_kind=value_kind,
                    value_literal=value_literal,
                    callsite=callsite_str,
                    filepath=src_file,
                    source_lineno=src_lineno,
                    inferred_min=inferred_min,
                    inferred_max=inferred_max,
                    inferred_allowed=inferred_allowed,
                    notes=notes,
                )
            )

    df = pd.DataFrame([dataclasses.asdict(r) for r in rows])

    # 便利な集計列（固定/変動のざっくり判定）
    def _is_fixed(vk: str) -> bool:
        return vk in ("fixed_literal", "fixed_from_const")

    if not df.empty:
        df["is_fixed"] = df["value_kind"].map(_is_fixed)
        df["missing_required"] = df["required"] & (~df["specified"])  # 必須なのに未指定

    if export_csv_path is not None:
        Path(export_csv_path).parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(str(export_csv_path), index=False, encoding="utf-8")

    return df


# -----------------------------
# 最適値探索（任意：評価関数を渡す）
# -----------------------------
def grid_search_best(
    base_params: Dict[str, Any],
    search_space: Dict[str, List[Any]],
    evaluate_fn,
    maximize: bool = False,
) -> Tuple[Dict[str, Any], float, pd.DataFrame]:
    """
    base_params を土台に search_space を全探索して evaluate_fn(params)->score を評価
    maximize=False なら最小化（例: MAE）
    """
    keys = list(search_space.keys())
    results = []

    def _rec(i: int, cur: Dict[str, Any]):
        if i == len(keys):
            params = dict(base_params)
            params.update(cur)
            score = float(evaluate_fn(params))
            results.append({"score": score, **params})
            return
        k = keys[i]
        for v in search_space[k]:
            cur[k] = v
            _rec(i + 1, cur)
        cur.pop(k, None)

    _rec(0, {})

    df = pd.DataFrame(results).sort_values("score", ascending=not maximize).reset_index(drop=True)
    best = df.iloc[0].to_dict()
    best_score = float(best.pop("score"))
    return best, best_score, df


def random_search_best(
    base_params: Dict[str, Any],
    search_space: Dict[str, List[Any]],
    evaluate_fn,
    n_trials: int = 30,
    seed: int = 42,
    maximize: bool = False,
) -> Tuple[Dict[str, Any], float, pd.DataFrame]:
    import random
    rng = random.Random(seed)
    results = []
    keys = list(search_space.keys())

    for _ in range(n_trials):
        params = dict(base_params)
        for k in keys:
            params[k] = rng.choice(search_space[k])
        score = float(evaluate_fn(params))
        results.append({"score": score, **params})

    df = pd.DataFrame(results).sort_values("score", ascending=not maximize).reset_index(drop=True)
    best = df.iloc[0].to_dict()
    best_score = float(best.pop("score"))
    return best, best_score, df
