# ファイルパス: C:\lib_ana\src\v6\core\inspect_params_v6.py
from __future__ import annotations
import importlib
import inspect
from typing import Any, Dict, List, Optional

def _safe_import_module(mod_name: str):
    try:
        return importlib.import_module(mod_name)
    except Exception:
        return None

def _safe_getattr_chain(obj: Any, attrs: List[str]) -> Any:
    cur = obj
    for a in attrs:
        try:
            cur = getattr(cur, a)
        except Exception:
            return None
    return cur

def _param_to_dict(p: inspect.Parameter) -> Dict[str, Any]:
    ann = p.annotation
    ann_s = "" if ann is inspect._empty else getattr(ann, "__name__", str(ann))
    has_default = p.default is not inspect._empty
    default_repr = "" if not has_default else repr(p.default)
    return {
        "name": p.name,
        "kind": str(p.kind),
        "annotation": ann_s,
        "has_default": bool(has_default),
        "default_repr": default_repr,
    }

def inspect_params_from_path(path: str) -> Optional[List[Dict[str, Any]]]:
    path = (path or "").strip()
    if not path or "." not in path:
        return None
    parts = path.split(".")
    # 左から順に import を試す（末尾から切る）
    for cut in range(len(parts), 0, -1):
        mod_name = ".".join(parts[:cut])
        mod = _safe_import_module(mod_name)
        if mod is None:
            continue
        attrs = parts[cut:]
        obj = _safe_getattr_chain(mod, attrs) if attrs else mod
        if obj is None:
            continue
        try:
            sig = inspect.signature(obj)
            return [_param_to_dict(p) for p in sig.parameters.values()]
        except Exception:
            try:
                if inspect.isclass(obj):
                    sig = inspect.signature(obj.__init__)
                    return [_param_to_dict(p) for p in sig.parameters.values()]
            except Exception:
                return None
    return None
