#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import numpy as np
import torch

from timesfm_pipeline import build_forecast_config, load_timesfm_2p5_torch, forecast_any


def main():
    # 推論の数値安定性/速度のため（README例） :contentReference[oaicite:9]{index=9}
    torch.set_float32_matmul_precision("high")

    cfg = build_forecast_config(
        max_context=1024,
        max_horizon=256,
        normalize_inputs=True,
        use_continuous_quantile_head=True,  # 分位点出したいならTrue :contentReference[oaicite:10]{index=10}
        force_flip_invariance=True,
        infer_is_positive=False,            # 非負制約が必要ならTrue
        fix_quantile_crossing=True,         # 分位点の交差を抑える :contentReference[oaicite:11]{index=11}
    )
    model = load_timesfm_2p5_torch(forecast_config=cfg)

    # ダミー入力（あなたの実データに置き換え）
    s1 = np.linspace(0, 1, 100).astype(np.float32)
    s2 = np.sin(np.linspace(0, 20, 67)).astype(np.float32)
    inputs = [s1, s2]

    horizon = 12
    point_forecast, quantile_forecast = forecast_any(model, inputs=inputs, horizon=horizon)

    print("point_forecast shape:", getattr(point_forecast, "shape", None))
    print("quantile_forecast shape:", getattr(quantile_forecast, "shape", None))
    print("point_forecast[0]:", np.asarray(point_forecast)[0])
    print("quantile_forecast[0,0]:", np.asarray(quantile_forecast)[0, 0])


if __name__ == "__main__":
    main()
