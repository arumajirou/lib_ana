# C:\lib_ana\src\v6\streamlit_app\app.py
from __future__ import annotations

# ★最初に入れる（これが無いと v6 が見つからない）
import sys
from pathlib import Path

_THIS = Path(__file__).resolve()
_SRC_ROOT = _THIS.parents[2]  # ...\src\v6\streamlit_app\app.py -> ...\src
if str(_SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(_SRC_ROOT))

import streamlit as st

from v6.core.analyzer_service_v6 import (
    list_installed_libraries,
    analyze_library_with_progress,
)
from v6.core.session_store_v6 import load_session_state, save_session_state

APP_TITLE = "Cognitive Library Explorer V6 (Streamlit)"

# --- 以下、前回提示した main() / _init_state() を続ける ---
