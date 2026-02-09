# ファイルパス: C:\lib_ana\src\v6\streamlit_app\app.py
from __future__ import annotations

# ★最重要：C:\lib_ana\src を import 探索パスに追加（どこから起動しても v6 が通る）
import sys
from pathlib import Path

_THIS = Path(__file__).resolve()
_SRC_ROOT = _THIS.parents[2]  # ...\src\v6\streamlit_app -> parents[2] = ...\src
if str(_SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(_SRC_ROOT))

import streamlit as st

from v6.core.analyzer_service_v6 import list_installed_libraries, analyze_library_with_progress
from v6.core.session_store_v6 import load_session_state, save_session_state
from v6.streamlit_app.ui_explorer_v6 import render_explorer

APP_TITLE = "🔧 Cognitive Library Explorer V6 (Streamlit)"

def _init_state() -> None:
    st.set_page_config(page_title=APP_TITLE, layout="wide")

    if "initialized" not in st.session_state:
        st.session_state.initialized = True
        st.session_state.analysis = None
        st.session_state.open_new_tab = True
        st.session_state.color_tables = False
        st.session_state.enable_online_lookup = True
        st.session_state.max_list_items = 500
        st.session_state.dedupe_ui = True  # UI上で重複レコードをまとめる
        st.session_state.deep_param_inspect = False
        st.session_state.enable_callgraph = False
        st.session_state.callgraph_max_files = 600
        st.session_state.callgraph_max_edges = 30000
        st.session_state.last_selected = {}
        st.session_state.session_path = r"C:\lib_ana\configs\cle_v6_session.json"

        restored = load_session_state(st.session_state.session_path)
        if restored:
            for k, v in restored.items():
                st.session_state[k] = v

def main() -> None:
    _init_state()
    st.title(APP_TITLE)

    libs = list_installed_libraries()

    with st.sidebar:
        st.header("⚙️ Settings")

        default_lib = st.session_state.last_selected.get("library")
        default_idx = libs.index(default_lib) if libs and default_lib in libs else (0 if libs else 0)
        lib_name = st.selectbox("Library", options=libs, index=default_idx)

        st.session_state.open_new_tab = st.checkbox("外部URLを新規タブで開く", value=bool(st.session_state.open_new_tab))
        st.session_state.color_tables = st.checkbox("表を色分けする（Type別）", value=bool(st.session_state.color_tables))
        st.session_state.enable_online_lookup = st.checkbox("PyPI/GitHub/HF をオンライン探索", value=bool(st.session_state.enable_online_lookup))
        st.session_state.max_list_items = st.slider("リスト最大表示件数（重さ対策）", 100, 5000, int(st.session_state.max_list_items), step=100)
        st.session_state.dedupe_ui = st.checkbox("重複レコードをまとめる（UI）", value=bool(st.session_state.dedupe_ui))

        st.divider()
        st.subheader("Deep options")
        st.session_state.deep_param_inspect = st.checkbox(
            "Deep param inspect（inspect.signatureでParams補完）",
            value=bool(st.session_state.deep_param_inspect),
            help="Params列が無い/薄い場合に補完します（重くなるので必要時だけ）",
        )

        col_a, col_b = st.columns(2)
        analyze_clicked = col_a.button("Analyze", use_container_width=True, type="primary")
        save_clicked = col_b.button("Save session", use_container_width=True)

        if save_clicked:
            save_session_state(
                st.session_state.session_path,
                {
                    "analysis": None,
                    "open_new_tab": st.session_state.open_new_tab,
                    "color_tables": st.session_state.color_tables,
                    "enable_online_lookup": st.session_state.enable_online_lookup,
                    "max_list_items": st.session_state.max_list_items,
                    "dedupe_ui": st.session_state.dedupe_ui,
                    "deep_param_inspect": st.session_state.deep_param_inspect,
                    "enable_callgraph": st.session_state.enable_callgraph,
                    "callgraph_max_files": st.session_state.callgraph_max_files,
                    "callgraph_max_edges": st.session_state.callgraph_max_edges,
                    "last_selected": {**st.session_state.last_selected, "library": lib_name},
                },
            )
            st.success("Saved.")

        if analyze_clicked:
            st.session_state.last_selected["library"] = lib_name
            st.session_state.analysis = analyze_library_with_progress(
                lib_name,
                deep_param_inspect=bool(st.session_state.deep_param_inspect),
                enable_callgraph=bool(st.session_state.enable_callgraph),
                callgraph_max_files=int(st.session_state.callgraph_max_files),
                callgraph_max_edges=int(st.session_state.callgraph_max_edges),
            )

    st.caption("解析にラグがある場合は進捗バーを表示します。大規模ライブラリは表示件数を絞ると快適です。")

    if st.session_state.analysis is None:
        st.info("まだ解析結果がありません。サイドバーで Analyze を実行してください。")
        return

    render_explorer(st.session_state.analysis)

if __name__ == "__main__":
    main()
