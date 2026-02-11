#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import numpy as np
import torch

from timesfm_pipeline import (
    build_forecast_config,
    load_timesfm_2p5_torch,
    forecast_with_covariates_any,
)


def main():
    torch.set_float32_matmul_precision("high")  # README例 :contentReference[oaicite:12]{index=12}

    # 共変量を使うなら、基本は xreg 依存が入る環境が必要になりがち（JAX等）という注意点が昔からある :contentReference[oaicite:13]{index=13}
    cfg = build_forecast_config(
        max_context=256,
        max_horizon=64,
        normalize_inputs=True,
        use_continuous_quantile_head=True,
        fix_quantile_crossing=True,
    )
    model = load_timesfm_2p5_torch(forecast_config=cfg)

    # 例：2系列の入力
    context_len = 30
    horizon = 7
    b = 2

    # 過去データ（context）
    inputs = [
        np.sin(np.linspace(0, 3, context_len)).astype(np.float32),
        np.cos(np.linspace(0, 3, context_len)).astype(np.float32),
    ]

    # 動的数値共変量(dynamic numerical covariate)：各系列ごとに「context+horizon」の長さを用意するのが典型 :contentReference[oaicite:14]{index=14}
    # ここでは「未来に既知な説明変数（例：曜日ダミー、予定価格、販促フラグ等）」を想定
    exog_1 = np.linspace(0.0, 1.0, context_len + horizon).astype(np.float32)
    exog_2 = np.linspace(1.0, 0.0, context_len + horizon).astype(np.float32)
    dynamic_numerical_covariates = {"exog": [exog_1, exog_2]}

    # 静的カテゴリ(static categorical covariate)：系列ごとに1個（例：商品カテゴリ）
    static_categorical_covariates = {"category": ["A", "B"]}

    # 実行（シグネチャ差分は吸収）
    cov_forecast, aux = forecast_with_covariates_any(
        model,
        inputs=inputs,
        horizon=horizon,
        dynamic_numerical_covariates=dynamic_numerical_covariates,
        static_categorical_covariates=static_categorical_covariates,
        xreg_mode="xreg + timesfm",  # 代表的な指定（古い例にも出る） :contentReference[oaicite:15]{index=15}
        ridge=1e-3,
        force_on_cpu=False,
        normalize_xreg_target_per_input=True,
    )

    print("cov_forecast shape:", getattr(cov_forecast, "shape", None))
    print("cov_forecast[0]:", np.asarray(cov_forecast)[0])


if __name__ == "__main__":
    main()
