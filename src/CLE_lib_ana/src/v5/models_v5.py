from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class ObjectKind(str, Enum):
    MODULE = "module"
    CLASS = "class"
    FUNCTION = "function"
    METHOD = "method"
    PROPERTY = "property"
    ATTRIBUTE = "attribute"


class ParamKind(str, Enum):
    POSITIONAL_ONLY = "POSITIONAL_ONLY"
    POSITIONAL_OR_KEYWORD = "POSITIONAL_OR_KEYWORD"
    VAR_POSITIONAL = "VAR_POSITIONAL"
    KEYWORD_ONLY = "KEYWORD_ONLY"
    VAR_KEYWORD = "VAR_KEYWORD"


@dataclass(frozen=True)
class ParamSpec:
    name: str
    annotation: Optional[str] = None
    default: Optional[str] = None
    kind: ParamKind = ParamKind.POSITIONAL_OR_KEYWORD
    required: bool = True


@dataclass(frozen=True)
class ValueCandidate:
    value: str
    source: str
    confidence: float


@dataclass(frozen=True)
class CallableSpec:
    qualname: str
    signature_str: str
    params: List[ParamSpec] = field(default_factory=list)
    return_annotation: Optional[str] = None
    doc_summary: Optional[str] = None


@dataclass
class ApiObjectRow:
    distribution: str
    module: str
    qualname: str
    object_kind: str
    is_public: bool
    signature_str: Optional[str] = None
    parameters: List[Dict[str, Any]] = field(default_factory=list)
    return_annotation: Optional[str] = None
    docstring: Optional[str] = None
    doc_summary: Optional[str] = None
    source_path: Optional[str] = None
    lineno: Optional[int] = None
    extraction_method: str = "runtime"
    errors: Optional[str] = None
