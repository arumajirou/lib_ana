from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass
class SampleDataFactory:
    def sample_for_annotation(self, annotation: Optional[str], param_name: str) -> str:
        ann = (annotation or "").lower().strip()

        if ann in {"int", "builtins.int"}:
            return "1"
        if ann in {"float", "builtins.float"}:
            return "0.1"
        if ann in {"str", "builtins.str"}:
            return repr(param_name or "example")
        if ann in {"bool", "builtins.bool"}:
            return "True"

        if "path" in ann or "file" in ann or param_name.lower() in {"path", "filepath", "filename"}:
            return "tmp_path"
        if "dataframe" in ann or param_name.lower() in {"df", "dataframe"}:
            return "sample_df"
        if "ndarray" in ann or "numpy" in ann or param_name.lower() in {"x", "y", "arr", "array"}:
            return "sample_arr"

        return "None"

    def prelude(self) -> str:
        return "\n".join(
            [
                "from pathlib import Path",
                "import tempfile",
                "",
                "# --- sample inputs ---",
                "tmp_dir = Path(tempfile.mkdtemp())",
                "tmp_path = str(tmp_dir / 'sample.txt')",
                "",
                "try:",
                "    import numpy as np",
                "    sample_arr = np.array([1, 2, 3])",
                "except Exception:",
                "    sample_arr = [1, 2, 3]",
                "",
                "try:",
                "    import pandas as pd",
                "    sample_df = pd.DataFrame({'a':[1,2,3]})",
                "except Exception:",
                "    sample_df = [{'a':1},{'a':2},{'a':3}]",
                "",
            ]
        )
