import os
import shutil
import re
from pathlib import Path

# 設定: 整理対象のルートディレクトリ（このスクリプトがある場所）
BASE_DIR = Path(__file__).parent.absolute()
SRC_DIR = BASE_DIR / "src"

# 除外するディレクトリ（これらの中身は触らない）
EXCLUDE_DIRS = {
    ".git",
    ".history",
    ".vscode",
    "__pycache__",
    "venv",
    "env",
    "logs",
    "tmp",
    "data",
    "configs",
    "outputs",
}


def organize_files():
    print(f"📂 整理を開始します: {BASE_DIR}")

    # srcディレクトリがなければ作成
    SRC_DIR.mkdir(exist_ok=True)

    # 移動対象のファイルを収集
    files_to_move = []

    # 1. ルートディレクトリと srcディレクトリをスキャン
    for target_dir in [BASE_DIR, SRC_DIR]:
        if not target_dir.exists():
            continue

        for file_path in target_dir.iterdir():
            if file_path.is_dir():
                continue
            if file_path.suffix != ".py":
                continue  # .pyファイルのみ対象
            if file_path.name == Path(__file__).name:
                continue  # 自分自身は移動しない

            files_to_move.append(file_path)

    # 移動処理
    moved_count = 0

    for file_path in files_to_move:
        file_name = file_path.name

        # バージョン番号を抽出 (例: analyzer_v3.py -> v3, models_v4.py -> v4)
        # "v" + 数字 のパターンを探す
        match = re.search(r"_(v\d+)", file_name)

        if match:
            version = match.group(1)  # "v2", "v3", "v4" など
            dest_dir = SRC_DIR / version
        else:
            # バージョンが付いていないファイル (lib.ipynbなどは対象外にしているが、pyファイルでバージョンなしの場合)
            # library_explorer.py などは `src/common` または `src/core` に移動するか、
            # 今回は安全のため `src` 直下に留める（移動しない）か選択できます。
            # ここでは "src直下" に集約するロジックにします。
            if file_path.parent == SRC_DIR:
                continue  # 既にsrcにあるバージョンなしファイルはスキップ
            dest_dir = SRC_DIR

        # 移動先ディレクトリ作成
        if not dest_dir.exists():
            dest_dir.mkdir(parents=True, exist_ok=True)
            # パッケージとして認識させるため __init__.py を作成
            (dest_dir / "__init__.py").touch()
            print(f"✨ ディレクトリ作成: {dest_dir}")

        # ファイル移動実行
        dest_path = dest_dir / file_name

        try:
            # 既に同名ファイルがある場合は上書き警告
            if dest_path.exists():
                print(f"⚠️ スキップ (同名ファイル存在): {file_name} -> {dest_dir}")
            else:
                shutil.move(str(file_path), str(dest_path))
                print(f"✅ 移動: {file_name} -> {version if match else 'src root'}/")
                moved_count += 1
        except Exception as e:
            print(f"❌ エラー: {file_name} の移動に失敗 - {e}")

    print(f"\n🎉 完了: {moved_count} 個のファイルを整理しました。")
    print("-" * 40)
    print("【整理後のインポート方法の注意】")
    print(
        "フォルダ構成が変わったため、import文を修正するか、sys.pathに追加が必要です。"
    )
    print("例: from src.v4.ui_v4 import ...")


if __name__ == "__main__":
    organize_files()
