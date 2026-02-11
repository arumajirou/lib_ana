# ui.lib_analysis.db（PostgreSQL 管理 + 可視化）

## 目的
- PostgreSQL の構造（DB/スキーマ/テーブル/制約/索引）を内省（introspection）して可視化する
- ER図（Entity-Relationship）/ 依存関係グラフ / 統計ダッシュボードを Streamlit で表示する
- DB/スキーマ/テーブル作成・削除などの破壊操作は「強い安全策付き」で実行する

## 実行（例）
```bash
cd /mnt/e/env/ts/lib_ana/src/ui/lib_analysis/db/streamlit_app
streamlit run /mnt/e/env/ts/lib_ana/src/ui/lib_analysis/db/streamlit_app/app.py
```

## トラブルシュート
### `TypeError: Failed to fetch dynamically imported module` が出る場合
このエラーは、多くの場合 Streamlit 本体の静的 JS 読み込み不整合で発生します。  
（`/static/js/index.<hash>.js` の取得失敗）

1. Streamlit を固定バージョンで入れ直す
```bash
pip install --force-reinstall "streamlit==1.54.0"
```

2. ブラウザで `http://localhost:8501` を開き、ハードリロードする
3. それでも解消しない場合は、別ポートで起動して確認する
```bash
streamlit run /mnt/e/env/ts/lib_ana/src/ui/lib_analysis/db/streamlit_app/app.py --server.port 8502
```

## 設定
- 接続プロファイル: `configs/db_admin_profiles.example.json` を参考に作成
- パスワードは `Streamlit secrets (.streamlit/secrets.toml)` か環境変数で管理すること（コード直書き禁止）

## 注意（安全）
- 破壊操作（DROP等）は二段階確認 + 対象名のタイピング確認が必須です
- 本番相当への接続は `allow_hosts` / `environment_label` で強く制限する前提です
