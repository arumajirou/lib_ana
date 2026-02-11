from __future__ import annotations
import sys
from pathlib import Path

def ensure_import_path() -> None:
    """Streamlit 実行時に import が壊れやすいので /lib_ana/src を sys.path に追加する。"""
    here = Path(__file__).resolve()
    db_root = here.parents[1]          # .../ui/lib_analysis/db
    src_root = db_root.parents[2]      # .../lib_ana/src
    if str(src_root) not in sys.path:
        sys.path.insert(0, str(src_root))
