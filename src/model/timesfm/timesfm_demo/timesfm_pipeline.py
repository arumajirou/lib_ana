#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import inspect
from dataclasses import asdict
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np

import timesfm


def build_forecast_config(
    max_context: int = 1024,
    max_horizon: int = 256,
    normalize_inputs: bool = True,
    window_size: int = 0,
    per_core_batch_size: int = 1,
    use_continuous_quantile_head: bool = True,
    force_flip_invariance: bool = True,
    infer_is_positive: bool = False,
    fix_quantile_crossing: bool = True,
    return_backcast: bool = False,
) -> "timesfm.ForecastConfig":
    """
    TimesFM 2.5 のREADME例に寄せた推奨デフォルト。 :contentReference[oaicite:2]{index=2}
    """
    cfg = timesfm.ForecastConfig(
        max_context=max_context,
        max_horizon=max_horizon,
        normalize_inputs=normalize_inputs,
        window_size=window_size,
        per_core_batch_size=per_core_batch_size,
        use_continuous_quantile_head=use_continuous_quantile_head,
        force_flip_invariance=force_flip_invariance,
        infer_is_positive=infer_is_positive,
        fix_quantile_crossing=fix_quantile_crossing,
        return_backcast=return_backcast,
    )
    return cfg


def load_timesfm_2p5_torch(
    repo_id: str = "google/timesfm-2.5-200m-pytorch",
    forecast_config: Optional["timesfm.ForecastConfig"] = None,
):
    """
    TimesFM 2.5（torch版）を読み込み、compileまで完了させる。
    """
    model = timesfm.TimesFM_2p5_200M_torch.from_pretrained(repo_id)  # README例 :contentReference[oaicite:3]{index=3}
    if forecast_config is not None:
        model.compile(forecast_config)  # README例 :contentReference[oaicite:4]{index=4}
    return model


def _call_with_signature_adaptation(fn, **kwargs):
    """
    関数のsignatureを見て、渡せる引数だけ渡す（2.5/旧版の差分に強い）。
    """
    sig = inspect.signature(fn)
    filtered = {k: v for k, v in kwargs.items() if k in sig.parameters}
    return fn(**filtered)


def forecast_any(
    model,
    inputs: Sequence[np.ndarray],
    horizon: int,
):
    """
    TimesFM 2.5: forecast(horizon=..., inputs=[...])   :contentReference[oaicite:5]{index=5}
    旧版:        forecast(inputs=[...], freq=[...]) 等の可能性があるので吸収する。
    """
    fn = model.forecast
    # 2.5 形式を優先して試す
    try:
        return _call_with_signature_adaptation(fn, horizon=horizon, inputs=list(inputs))
    except TypeError:
        # 旧版っぽい形（freqが必要など）に寄せる：freqが必要ならダミー0を入れる
        b = len(inputs)
        return _call_with_signature_adaptation(fn, inputs=list(inputs), freq=[0] * b, horizon=horizon)


def forecast_with_covariates_any(
    model,
    inputs: Sequence[np.ndarray],
    horizon: int,
    dynamic_numerical_covariates: Optional[Dict[str, Sequence[np.ndarray]]] = None,
    dynamic_categorical_covariates: Optional[Dict[str, Sequence[np.ndarray]]] = None,
    static_numerical_covariates: Optional[Dict[str, Sequence[Any]]] = None,
    static_categorical_covariates: Optional[Dict[str, Sequence[Any]]] = None,
    xreg_mode: str = "xreg + timesfm",
    ridge: float = 1e-3,
    force_on_cpu: bool = False,
    normalize_xreg_target_per_input: bool = True,
):
    """
    共変量あり予測。TimesFMは XReg(外部回帰) を使うモードがある。 :contentReference[oaicite:6]{index=6}
    シグネチャは版で揺れるので、signature吸収で呼ぶ。

    注意：動的共変量(dynamic covariate)は「文脈(context=過去) + 予測区間(horizon=未来)」をカバーする長さが必要、
    という設計が一般的で、TimesFM系でもこの前提で話が進むことが多い。 :contentReference[oaicite:7]{index=7}
    """
    fn = model.forecast_with_covariates

    b = len(inputs)
    return _call_with_signature_adaptation(
        fn,
        inputs=list(inputs),
        horizon=horizon,
        dynamic_numerical_covariates=dynamic_numerical_covariates or {},
        dynamic_categorical_covariates=dynamic_categorical_covariates or {},
        static_numerical_covariates=static_numerical_covariates or {},
        static_categorical_covariates=static_categorical_covariates or {},
        freq=[0] * b,  # 旧版だと必要なことがあるので一応用意（2.5は捨てられるはず） :contentReference[oaicite:8]{index=8}
        xreg_mode=xreg_mode,
        ridge=ridge,
        force_on_cpu=force_on_cpu,
        normalize_xreg_target_per_input=normalize_xreg_target_per_input,
    )
