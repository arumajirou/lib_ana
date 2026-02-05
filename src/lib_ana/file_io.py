# ファイルパス: C:\lib_ana\src\lib_ana\file_io.py
from __future__ import annotations

import os
import codecs
from pathlib import Path
from typing import Optional, Tuple, Union, List


class FileIOError(Exception):
    """ファイル操作に関するカスタム例外"""

    pass


def resolve_path(path_str: str, base_dir: Optional[str] = None) -> Path:
    """
    文字列のパスを解決し、絶対パスを持つPathオブジェクトを返します。

    Args:
        path_str (str): 入力パス文字列（例: "~/data/file.txt", "./src"）
        base_dir (str, optional): 相対パスの基準ディレクトリ。指定がない場合はカレントディレクトリ。

    Returns:
        Path: 解決された絶対パス
    """
    if not path_str:
        raise FileIOError("Path string is empty.")

    # ユーザーホーム (~) の展開
    expanded = os.path.expanduser(path_str)
    p = Path(expanded)

    # 絶対パスでない場合、base_dirまたはcwdを基準にする
    if not p.is_absolute():
        base = Path(base_dir) if base_dir else Path.cwd()
        p = base / p

    return p.resolve()


def detect_file_type(path: Union[str, Path]) -> str:
    """
    拡張子やファイル名からコンテンツタイプを推定します。

    Returns:
        str: 'python', 'json', 'csv', 'markdown', 'piplist', 'unknown'
    """
    p = Path(path)
    name = p.name.lower()
    ext = p.suffix.lower()

    if ext == ".py":
        return "python"
    elif ext == ".json":
        return "json"
    elif ext == ".csv":
        return "csv"
    elif ext in [".md", ".markdown"]:
        return "markdown"
    elif "requirements" in name or ext == ".txt":
        # 簡易的な判定。中身を見てpip listか判定するのは読み込み後に行う
        return "text"

    return "unknown"


def smart_read_text(
    target: Union[str, Path, bytes], encoding_candidates: List[str] = None
) -> Tuple[str, str]:
    """
    複数のエンコーディングを試行してテキストを読み込みます。

    Args:
        target: ファイルパス(str/Path) または バイト列(bytes)
        encoding_candidates: 試行するエンコーディングのリスト

    Returns:
        (content, used_encoding): 読み込んだ文字列と使用したエンコーディング
    """
    if encoding_candidates is None:
        # 日本語Windows環境と一般的なWeb標準を考慮した優先順位
        encoding_candidates = ["utf-8", "cp932", "shift_jis", "latin1"]

    content_bytes = b""

    # パス指定の場合はファイルを読み込む
    if isinstance(target, (str, Path)):
        p = resolve_path(str(target))
        if not p.exists():
            raise FileIOError(f"File not found: {p}")
        if not p.is_file():
            raise FileIOError(f"Target is not a file: {p}")

        try:
            with open(p, "rb") as f:
                content_bytes = f.read()
        except Exception as e:
            raise FileIOError(f"Failed to read file {p}: {e}")
    # バイト列が直接渡された場合（Upload widgetなどから）
    elif isinstance(target, bytes):
        content_bytes = target
    else:
        raise FileIOError("Target must be a path(str/Path) or bytes.")

    # エンコーディング試行ループ
    for enc in encoding_candidates:
        try:
            # BOM付きUTF-8のケア (utf-8-sig はBOMがあれば除去、なければutf-8として振る舞う)
            if enc == "utf-8" and content_bytes.startswith(codecs.BOM_UTF8):
                enc = "utf-8-sig"

            text = content_bytes.decode(enc)
            return text, enc
        except UnicodeDecodeError:
            continue

    raise FileIOError(f"Failed to decode content with encodings: {encoding_candidates}")


def get_snippet(text: str, max_lines: int = 5) -> str:
    """プレビュー用にテキストの先頭N行を取得します。"""
    lines = text.splitlines()
    snippet = "\n".join(lines[:max_lines])
    if len(lines) > max_lines:
        snippet += "\n... (more lines) ..."
    return snippet
