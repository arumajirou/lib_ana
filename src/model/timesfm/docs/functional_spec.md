# TimesFM 詳細機能定義書

## 機能一覧

| 機能ID | 機能名 | API | 入力 | 出力 | 検証観点 |
|---|---|---|---|---|---|
| F-01 | チェックポイント読込 | `TimesFmBase.load_from_checkpoint` | checkpoint path/version | 初期化済みモデル | 互換性、例外系 |
| F-02 | 配列予測 | `TimesFmBase.forecast` | list[np.ndarray] | mean/quantiles | shape、NaN処理 |
| F-03 | DF予測 | `TimesFmBase.forecast_on_df` | `unique_id`,`ds`,`y` | 予測DF | freq/並列実行 |
| F-04 | 共変量予測 | `TimesFmBase.forecast_with_covariates` | target+covariates | model/xreg予測 | 行列整合、mode切替 |
| F-05 | 時間特徴量生成 | `TimeCovariates.get_covariates` | datetime index | covariate matrix | 祝日距離、欠損 |
| F-06 | 前処理 | `strip_leading_nans` 他 | 連続系列 | 補間・正規化系列 | 先頭NaN、全NaN |

## 機能分解（再帰）
- L1: 推論API層
- L2: 前処理/特徴量層
- L3: デコーダ内部層（JAX/Torch）
- L4: 外部依存層（DB、checkpoint、runtime backend）
