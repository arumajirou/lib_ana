# TimesFM 要件定義書

## 1. 目的
- TimesFM の主要機能を、`dataset.loto_y_ts` と `dataset.loto_hist_feat` を使って再現可能に検証する。
- 解析対象は `cle_v6_full_timesfm_20260211_182948.html`、`graph.mmd`、既存の解析メモを統合した内容とする。

## 2. 対象機能
- `load_from_checkpoint`
- `forecast`
- `forecast_on_df`
- `forecast_with_covariates`
- `TimeCovariates.get_covariates`
- 欠損補完/正規化 (`strip_leading_nans`, `linear_interpolation`, `_normalize`)

## 3. 成功条件
- DB取得から予測入力整形までを notebook 上で再現できる。
- APIごとの入出力契約を確認できる。
- 段階テスト（Stage 0-5）で実行結果を記録できる。

## 4. 非機能要件
- ローカル実行可能（Python + PostgreSQL）。
- 設計書、ロジック、実行計画を `src/model/timesfm/docs` に保存。
- ノートブックとモジュールの責務分離を行う。
