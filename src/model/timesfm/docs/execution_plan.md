# TimesFM 実行計画書

## フェーズ別計画
1. フェーズA: 基盤確認
- 依存関係確認（`pandas`, `psycopg`系）。
- DB疎通とテーブル存在確認。

2. フェーズB: 契約テスト
- `run_all_contract()` 実行。
- 結果を notebook に保存。

3. フェーズC: 推論テスト
- TimesFMモデルを初期化し `run_with_timesfm(model=...)` 実行。
- `forecast_on_df` の出力件数・列・horizon整合を確認。

4. フェーズD: 共変量テスト
- `loto_hist_feat` から covariates を作成。
- `forecast_with_covariates` を mode別に比較。

5. フェーズE: 評価
- ローリング分割で MAE/MAPE/SMAPE を算出。
- ナイーブ予測と比較して極端な劣化がないか判定。

## 受入判定
- Stage 0-2 が全て pass。
- Stage 3-5 で重大な契約違反なし。
- 再実行して同等の結果を取得可能。
