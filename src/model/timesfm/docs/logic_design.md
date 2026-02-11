# TimesFM ロジック設計書

## 1. 制御フロー
1. `DbConfig.from_env()` で接続定義作成
2. `TimesFmDatasetRepository` で `loto_y_ts` / `loto_hist_feat` 読込
3. `TimesFmTestRunner.run_stage_0()` で接続/件数確認
4. `run_stage_1()` で契約検証（必須列、ソート、欠損率）
5. `run_stage_2_contract_only()` で機能一覧と段階計画を取得
6. モデルがある場合のみ `run_with_timesfm()` で予測実行

## 2. 主要判定ロジック
- 識別子安全性: schema/tableは英数字+`_`のみ許可。
- データ契約: `unique_id`,`ds`,`y` が揃わない場合はNG。
- 並び順: `unique_id`,`ds` で昇順確認。
- 実行分岐: model未提供の場合は「契約テストのみ」モード。

## 3. 段階設計（探索的）
- Stage 0: 実行可能性
- Stage 1: データ品質
- Stage 2: API契約
- Stage 3: 共変量統合
- Stage 4: ロバスト性
- Stage 5: 評価・比較
