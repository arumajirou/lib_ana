from __future__ import annotations

import importlib
import inspect
from dataclasses import asdict
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

from .models_v5 import ApiObjectRow, CallableSpec, ParamKind, ParamSpec, ValueCandidate


def _is_public(name: str) -> bool:
    return not name.startswith("_")


def _safe_doc_summary(doc: Optional[str]) -> Optional[str]:
    if not doc:
        return None
    first = doc.strip().splitlines()[0].strip()
    return first[:240] if first else None


def _param_kind(kind: inspect._ParameterKind) -> ParamKind:
    mapping = {
        inspect.Parameter.POSITIONAL_ONLY: ParamKind.POSITIONAL_ONLY,
        inspect.Parameter.POSITIONAL_OR_KEYWORD: ParamKind.POSITIONAL_OR_KEYWORD,
        inspect.Parameter.VAR_POSITIONAL: ParamKind.VAR_POSITIONAL,
        inspect.Parameter.KEYWORD_ONLY: ParamKind.KEYWORD_ONLY,
        inspect.Parameter.VAR_KEYWORD: ParamKind.VAR_KEYWORD,
    }
    return mapping.get(kind, ParamKind.POSITIONAL_OR_KEYWORD)


def _annotation_to_str(ann: Any) -> Optional[str]:
    if ann is inspect._empty:
        return None
    try:
        return getattr(ann, "__name__", str(ann))
    except Exception:
        return None


def _default_to_str(d: Any) -> Optional[str]:
    if d is inspect._empty:
        return None
    try:
        return repr(d)
    except Exception:
        return None


def _value_candidates(param: ParamSpec) -> List[ValueCandidate]:
    cands: List[ValueCandidate] = []
    if param.default is not None and param.default != "None":
        cands.append(ValueCandidate(value=param.default, source="default", confidence=0.95))
    if (param.annotation or "").lower() in {"bool", "builtins.bool"} or param.name.lower().startswith(("is_", "has_", "use_", "enable_")):
        cands.append(ValueCandidate(value="True", source="bool", confidence=0.80))
        cands.append(ValueCandidate(value="False", source="bool", confidence=0.80))
    return cands


class V5Analyzer:
    # Runtime-based analyzer (minimal working skeleton).
    # Safety: this imports the distribution when enable_runtime=True.

    def analyze_distribution(self, distribution: str, enable_runtime: bool = False) -> Tuple[pd.DataFrame, List[str]]:
        errors: List[str] = []
        if not enable_runtime:
            errors.append("runtime_import_disabled: set enable_runtime=True to import the package")
            return pd.DataFrame(), errors

        try:
            mod = importlib.import_module(distribution)
        except Exception as e:
            errors.append(f"import_failed: {distribution}: {e}")
            return pd.DataFrame(), errors

        rows: List[Dict[str, Any]] = []
        for name, obj in inspect.getmembers(mod):
            try:
                if inspect.isfunction(obj):
                    rows.extend(self._analyze_callable(distribution, mod.__name__, name, obj, kind="function"))
                elif inspect.isclass(obj):
                    rows.extend(self._analyze_class(distribution, mod.__name__, name, obj))
            except Exception as e:
                errors.append(f"member_failed: {distribution}.{name}: {e}")

        return pd.DataFrame(rows), errors

    def _analyze_callable(self, distribution: str, module: str, name: str, obj: Any, kind: str) -> List[Dict[str, Any]]:
        qualname = f"{module}.{name}"
        signature_str: Optional[str] = None
        params: List[Dict[str, Any]] = []
        ret: Optional[str] = None

        try:
            sig = inspect.signature(obj)
            signature_str = str(sig)
            for p in sig.parameters.values():
                params.append({
                    "name": p.name,
                    "annotation": _annotation_to_str(p.annotation),
                    "default": _default_to_str(p.default),
                    "kind": _param_kind(p.kind).value,
                    "required": p.default is inspect._empty and p.kind not in (inspect.Parameter.VAR_POSITIONAL, inspect.Parameter.VAR_KEYWORD),
                })
            ret = _annotation_to_str(sig.return_annotation)
        except Exception:
            pass

        doc = inspect.getdoc(obj)
        row = ApiObjectRow(
            distribution=distribution,
            module=module,
            qualname=qualname,
            object_kind=kind,
            is_public=_is_public(name),
            signature_str=signature_str,
            parameters=params,
            return_annotation=ret,
            docstring=doc,
            doc_summary=_safe_doc_summary(doc),
            extraction_method="runtime",
        )
        return [asdict(row)]

    def _analyze_class(self, distribution: str, module: str, name: str, cls: Any) -> List[Dict[str, Any]]:
        rows: List[Dict[str, Any]] = []
        qualname = f"{module}.{name}"
        doc = inspect.getdoc(cls)
        rows.append(asdict(ApiObjectRow(
            distribution=distribution,
            module=module,
            qualname=qualname,
            object_kind="class",
            is_public=_is_public(name),
            docstring=doc,
            doc_summary=_safe_doc_summary(doc),
            extraction_method="runtime",
        )))

        for mname, mobj in inspect.getmembers(cls):
            if mname.startswith("_"):
                continue
            if inspect.isfunction(mobj) or inspect.ismethod(mobj):
                rows.extend(self._analyze_callable(distribution, qualname, mname, mobj, kind="method"))
        return rows

    def to_callable_spec(self, api_row: Dict[str, Any]) -> CallableSpec:
        sig = api_row.get("signature_str") or "()"
        params: List[ParamSpec] = []
        for p in api_row.get("parameters", []) or []:
            params.append(ParamSpec(
                name=p.get("name",""),
                annotation=p.get("annotation"),
                default=p.get("default"),
                kind=ParamKind(p.get("kind", ParamKind.POSITIONAL_OR_KEYWORD.value)),
                required=bool(p.get("required", True)),
            ))
        return CallableSpec(
            qualname=api_row["qualname"],
            signature_str=sig,
            params=params,
            return_annotation=api_row.get("return_annotation"),
            doc_summary=api_row.get("doc_summary"),
        )

    def value_candidates_for_param(self, param: ParamSpec) -> List[ValueCandidate]:
        return _value_candidates(param)
