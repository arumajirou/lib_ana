from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List

import pandas as pd


@dataclass(frozen=True)
class FeatureEntry:
    name: str
    api: str
    objective: str
    key_checks: str


CORE_FEATURES: List[FeatureEntry] = [
    FeatureEntry(
        name="Checkpoint Loading",
        api="TimesFmBase.load_from_checkpoint",
        objective="Load compatible model checkpoints for backend runtime.",
        key_checks="path validity, version compatibility, first-load latency",
    ),
    FeatureEntry(
        name="Array Forecast",
        api="TimesFmBase.forecast",
        objective="Forecast from list-like time series inputs.",
        key_checks="shape, quantiles, NaN handling, normalize switch",
    ),
    FeatureEntry(
        name="DataFrame Forecast",
        api="TimesFmBase.forecast_on_df",
        objective="Batch forecast from DataFrame with unique_id/ds/value columns.",
        key_checks="column contract, frequency map, output horizon alignment",
    ),
    FeatureEntry(
        name="Forecast with Covariates",
        api="TimesFmBase.forecast_with_covariates",
        objective="Combine covariate regression with TimesFM forecast.",
        key_checks="xreg_mode, categorical features, matrix shape integrity",
    ),
    FeatureEntry(
        name="Time Covariates",
        api="TimeCovariates.get_covariates",
        objective="Generate calendar and holiday distance features.",
        key_checks="timezone safety, holiday feature availability",
    ),
]


class TimesFmAnalysisEngine:
    """Recursive and stage-based analysis helpers for TimesFM verification."""

    def build_feature_catalog(self) -> pd.DataFrame:
        return pd.DataFrame(
            [
                {
                    "feature_name": item.name,
                    "api": item.api,
                    "objective": item.objective,
                    "key_checks": item.key_checks,
                }
                for item in CORE_FEATURES
            ]
        )

    def recursive_scope_map(self) -> Dict[str, List[str]]:
        return {
            "L1-Core APIs": [
                "TimesFmBase",
                "TimesFmJax",
                "TimesFmTorch",
            ],
            "L2-Pre/Post Processing": [
                "strip_leading_nans",
                "linear_interpolation",
                "_normalize/_renormalize",
            ],
            "L2-Feature Engineering": [
                "TimeCovariates.get_covariates",
                "xreg_lib.BatchedInContextXRegBase.create_covariate_matrix",
            ],
            "L3-Decoder Internals": [
                "patched_decoder.PatchedTimeSeriesDecoder",
                "pytorch_patched_decoder.PatchedTimeSeriesDecoder",
            ],
        }

    def staged_test_plan(self) -> pd.DataFrame:
        stages = [
            ("Stage 0", "Environment", "Dependency and DB connectivity checks"),
            ("Stage 1", "Data Contract", "Schema, nulls, and timestamp ordering"),
            ("Stage 2", "Base Forecast", "forecast_on_df without covariates"),
            ("Stage 3", "Covariate Forecast", "forecast_with_covariates validation"),
            ("Stage 4", "Robustness", "Missing values and corner-case behavior"),
            ("Stage 5", "Evaluation", "Rolling backtest and baseline comparison"),
        ]
        return pd.DataFrame(stages, columns=["stage", "event", "description"])
