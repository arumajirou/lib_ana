# ファイルパス: C:\lib_ana\src\v6\core\session_store_v6.py
from __future__ import annotations
import json
from typing import Any, Dict, Optional

def load_session_state(path: str) -> Optional[Dict[str, Any]]:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None

def save_session_state(path: str, state: Dict[str, Any]) -> None:
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False, indent=2)
    except Exception:
        pass
