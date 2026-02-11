# TimesFM 詳細機能設計書

## 1. データ設計
- `dataset.loto_y_ts` を予測対象データとする。
  - 必須列: `unique_id`, `ds`, `y`
- `dataset.loto_hist_feat` を共変量候補とする。
  - 数値/カテゴリ列を分離し `forecast_with_covariates` に投入可能な形へ整形する。

## 2. モジュール設計
- `config.py`: 接続情報の管理（環境変数優先）。
- `data_access.py`: PostgreSQLからの取得とDataFrame化。
- `analysis_engine.py`: 機能カタログと段階計画の生成。
- `test_runner.py`: Stage別テストの実行。

## 3. notebook 設計
- セクション1: 前提確認（依存、接続、件数）。
- セクション2: データ契約テスト（列、型、順序）。
- セクション3: TimesFM接続後の `forecast_on_df` 実行。
- セクション4: 共変量モード評価。
- セクション5: バックテスト/ベースライン比較。

## 4. 失敗時設計
- DB接続失敗時は `run_stage_0` で即失敗検知。
- モデル未指定時は `run_with_timesfm` を `skipped` で返し、契約テストのみ継続。
