# tsl_loto_etl（パイプライン単体）

このフォルダを `C:\tsl\pipelines\tsl_loto_etl\` に置く想定です。

## 目的
- SQLiteのロト履歴（`C:\tsl\data\sqlite\loto.sqlite3`）を読み
- 時系列変換（raw/cumsum/roll3_sum/roll7_mean/diff1/is_odd）と横持ち特徴量を生成し
- PostgreSQL（推奨）または Spark/Parquet に書き込みます

## 実行（ノートブック）
- `run_loto_etl.ipynb` を開いて上から実行してください。
- PostgreSQLでの実行は `args.backend='psql'` で、`host/port/db/user/password/schema/psql_bin/tmp_dir` を設定します。

## 重要ポイント
- Windows + Jupyter では `psql` の出力が CP932 になり、`UnicodeDecodeError` が起きることがあります。
  - `run_loto_etl.ipynb` は decode を安全にするラッパーを同梱しています。
  - `loto_common.py` の `run_psql()` も UTF-8寄せ + replace で落ちにくくしています。

## PostgreSQL側の確認（例）
- schema / table / columns / indexes / row count はノートの「3) 書き込み確認」セルがそのまま使えます。
