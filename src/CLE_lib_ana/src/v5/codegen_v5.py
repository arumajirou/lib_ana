from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional

from .models_v5 import CallableSpec
from .sample_data_factory_v5 import SampleDataFactory


@dataclass
class CodeGenOptions:
    include_prelude: bool = True
    dry_run_comment: bool = True


class CodeGenV5:
    def __init__(self, factory: Optional[SampleDataFactory] = None):
        self.factory = factory or SampleDataFactory()

    def generate(self, spec: CallableSpec, selected_values: Optional[Dict[str, str]] = None, options: Optional[CodeGenOptions] = None) -> str:
        options = options or CodeGenOptions()
        selected_values = selected_values or {}

        lines: List[str] = []
        if options.include_prelude:
            lines.append(self.factory.prelude())

        top_pkg = spec.qualname.split(".")[0]
        lines.append("# --- target callable ---")
        lines.append(f"import {top_pkg}")
        lines.append("")

        args: List[str] = []
        for p in spec.params:
            if p.name in {"self", "cls"}:
                continue
            if p.name in selected_values:
                args.append(f"{p.name}={selected_values[p.name]}")
            elif p.required:
                val = self.factory.sample_for_annotation(p.annotation, p.name)
                args.append(f"{p.name}={val}")

        call_expr = f"{spec.qualname}({', '.join(args)})"
        if options.dry_run_comment:
            lines.append("# NOTE: generated snippet (tool does not auto-execute anything)")
        lines.append(f"result = {call_expr}")
        lines.append("print(result)")
        return "\n".join(lines).strip() + "\n"
