# ファイルパス: C:\lib_ana\src\lib_ana\ui_components.py
from __future__ import annotations

import ipywidgets as widgets
from IPython.display import display, clear_output
from typing import Callable, Optional, Dict, Any
import io

# 同一パッケージ内のfile_ioを利用
# ※ パッケージとしてインストールされていない環境で動かす場合、パス設定が必要になることがあります
try:
    from . import file_io
except ImportError:
    import file_io  # フラットな配置の場合


class UniversalFileLoader:
    """
    ローカルファイルパス指定とファイルアップロード（Drag&Drop）の両方に対応した
    Jupyter Notebook用ファイル読み込みウィジェット。
    """

    def __init__(self, callback: Optional[Callable[[str, str, str], None]] = None):
        """
        Args:
            callback: 読み込み成功時に呼ばれる関数 func(content, filename, filetype)
        """
        self.callback = callback
        self.loaded_content: Optional[str] = None
        self.loaded_meta: Dict[str, Any] = {}

        # --- UI Components ---

        # 1. Method Selection (Tabs)
        self.input_path = widgets.Text(
            placeholder=r"C:\path\to\file.py",
            description="Path:",
            layout=widgets.Layout(width="98%"),
        )
        self.btn_load_path = widgets.Button(
            description="Load from Path", icon="folder-open", button_style="info"
        )

        self.uploader = widgets.FileUpload(
            accept="",  # All files
            multiple=False,
            description="Upload / Drag",
            layout=widgets.Layout(width="300px"),
        )

        # Output Area for Preview & Messages
        self.out = widgets.Output(
            layout=widgets.Layout(
                border="1px solid #ddd", padding="5px", height="200px", overflow="auto"
            )
        )

        # Event Binding
        self.btn_load_path.on_click(self._on_load_path_clicked)
        self.uploader.observe(self._on_upload_change, names="value")

        # Layout Assembly
        self.tab = widgets.Tab()
        self.tab.children = [
            widgets.VBox([self.input_path, self.btn_load_path]),
            widgets.VBox(
                [widgets.HTML("<b>Drag & Drop file here:</b>"), self.uploader]
            ),
        ]
        self.tab.set_title(0, "Local Path")
        self.tab.set_title(1, "File Upload")

        self.widget = widgets.VBox(
            [
                widgets.HTML("<h4>📁 Universal File Loader</h4>"),
                self.tab,
                widgets.Label("Log / Preview:"),
                self.out,
            ]
        )

    def display(self):
        """ウィジェットを表示します"""
        display(self.widget)

    def _on_load_path_clicked(self, b):
        """パス指定での読み込み処理"""
        path_str = self.input_path.value.strip()
        if not path_str:
            with self.out:
                print("⚠️ Path is empty.")
            return

        self.out.clear_output()
        with self.out:
            print(f"🔄 Reading from path: {path_str} ...")
            try:
                # file_io モジュールを利用
                content, enc = file_io.smart_read_text(path_str)
                ftype = file_io.detect_file_type(path_str)

                self._finalize_load(content, path_str, ftype, enc)

            except Exception as e:
                print(f"❌ Error: {e}")

    def _on_upload_change(self, change):
        """アップロードでの読み込み処理"""
        if not change.new:
            return

        self.out.clear_output()
        with self.out:
            print("🔄 Processing upload...")
            try:
                # ipywidgets >= 8.0 と < 8.0 で構造が違う場合の互換性考慮
                # value は tuple か dict か list の場合がある
                vals = change.new
                if isinstance(vals, tuple) or isinstance(vals, list):
                    f_obj = vals[0]
                elif isinstance(vals, dict):
                    # 古い ipywidgets または特定のdict構造
                    key = next(iter(vals))
                    f_obj = vals[key]
                else:
                    raise ValueError(f"Unknown upload structure: {type(vals)}")

                # contentの取得 (memoryview or bytes)
                content_bytes = f_obj.get("content", b"")
                filename = f_obj.get("name", "uploaded_file")

                if isinstance(content_bytes, memoryview):
                    content_bytes = content_bytes.tobytes()

                # file_io モジュールを利用
                content, enc = file_io.smart_read_text(content_bytes)
                ftype = file_io.detect_file_type(filename)

                self._finalize_load(content, filename, ftype, enc)

                # Reset uploader to allow reloading same file if needed
                self.uploader.value = ()

            except Exception as e:
                print(f"❌ Error during upload processing: {e}")
                import traceback

                traceback.print_exc()

    def _finalize_load(self, content: str, name: str, ftype: str, enc: str):
        """読み込み完了後の共通処理"""
        self.loaded_content = content
        self.loaded_meta = {
            "name": name,
            "type": ftype,
            "encoding": enc,
            "size": len(content),
        }

        print(f"✅ Success! ({len(content)} chars, {enc})")
        print(f"Type: {ftype}")
        print("-" * 40)
        print(file_io.get_snippet(content))

        # コールバック実行
        if self.callback:
            self.callback(content, name, ftype)
