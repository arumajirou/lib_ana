from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional

import pandas as pd

from .analysis_engine import TimesFmAnalysisEngine
from .data_access import TimesFmDatasetRepository


@dataclass
class TimesFmTestRunner:
    """Runs staged validation for TimesFM workflows."""

    repository: TimesFmDatasetRepository
    engine: TimesFmAnalysisEngine = TimesFmAnalysisEngine()

    def run_stage_0(self) -> Dict[str, Any]:
        y_df = self.repository.load_target_series(limit=10)
        feat_df = self.repository.load_hist_features(limit=10)
        return {
            "y_rows": len(y_df),
            "feat_rows": len(feat_df),
            "y_columns": list(y_df.columns),
            "feat_columns": list(feat_df.columns),
        }

    def run_stage_1(self, y_df: pd.DataFrame, feat_df: pd.DataFrame) -> Dict[str, Any]:
        required_y = {"unique_id", "ds", "y"}
        y_ok = required_y.issubset(y_df.columns)
        sorted_ok = y_df.sort_values(["unique_id", "ds"]).index.equals(y_df.index)
        null_ratio = y_df["y"].isna().mean() if "y" in y_df.columns else 1.0
        return {
            "required_columns_ok": y_ok,
            "already_sorted": bool(sorted_ok),
            "target_null_ratio": float(null_ratio),
            "feature_column_count": int(len(feat_df.columns)),
        }

    def run_stage_2_contract_only(self, horizon_len: int = 16) -> Dict[str, Any]:
        catalog = self.engine.build_feature_catalog()
        plan = self.engine.staged_test_plan()
        return {
            "horizon_len": horizon_len,
            "feature_count": len(catalog),
            "stages": plan.to_dict(orient="records"),
        }

    def run_all_contract(self) -> Dict[str, Any]:
        stage0 = self.run_stage_0()
        y_df = self.repository.load_target_series(limit=1000)
        feat_df = self.repository.load_hist_features(limit=1000)
        stage1 = self.run_stage_1(y_df, feat_df)
        stage2 = self.run_stage_2_contract_only()
        return {"stage0": stage0, "stage1": stage1, "stage2": stage2}

    def run_all_contract_safe(self) -> Dict[str, Any]:
        try:
            return {"status": "ok", "result": self.run_all_contract()}
        except Exception as exc:  # noqa: BLE001
            return {
                "status": "error",
                "error_type": type(exc).__name__,
                "error_message": str(exc),
                "hint": "Set TIMESFM_DB_PASSWORD and re-run.",
            }

    def run_with_timesfm(
        self,
        model: Optional[Any] = None,
        freq: str = "D",
        value_name: str = "y",
        num_jobs: int = 1,
    ) -> Dict[str, Any]:
        y_df = self.repository.load_target_series()
        if model is None:
            return {
                "status": "skipped",
                "reason": "TimesFM model instance is required for runtime forecast checks.",
                "rows": len(y_df),
            }
        pred_df = model.forecast_on_df(
            y_df,
            freq=freq,
            value_name=value_name,
            num_jobs=num_jobs,
        )
        return {
            "status": "ok",
            "input_rows": len(y_df),
            "output_rows": len(pred_df),
            "output_columns": list(pred_df.columns),
        }
