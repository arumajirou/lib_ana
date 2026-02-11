from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, Optional

import json
import numpy as np
import pandas as pd

from .config import DbConfig
from .data_access import TimesFmDatasetRepository


@dataclass
class TimesFmRuntimeConfig:
    """Runtime settings for practical TimesFM execution."""

    freq: str = "D"
    value_name: str = "y"
    horizon_len: int = 16
    context_len: int = 128
    per_core_batch_size: int = 32
    backend: str = "cpu"
    model_dims: int = 1280
    num_layers: int = 20
    num_heads: int = 16
    input_patch_len: int = 32
    output_patch_len: int = 128
    point_forecast_mode: str = "median"
    checkpoint_path: Optional[str] = None
    huggingface_repo_id: Optional[str] = None
    checkpoint_version: str = "torch"
    checkpoint_local_dir: Optional[str] = None


def load_dataset_for_timesfm(
    db_config: Optional[DbConfig] = None,
    limit: Optional[int] = None,
    fallback_rows: int = 256,
) -> Dict[str, Any]:
    """Load DB dataset, fallback to synthetic series when DB is unavailable."""
    if db_config is None:
        db_config = DbConfig.from_env()
    repo = TimesFmDatasetRepository(db_config)
    try:
        y_df = repo.load_target_series(limit=limit)
        source = "postgres"
        error = None
    except Exception as exc:  # noqa: BLE001
        ds = pd.date_range("2021-01-01", periods=fallback_rows, freq="D")
        y = np.sin(np.arange(fallback_rows) / 8.0) + (np.arange(fallback_rows) / 500.0)
        y_df = pd.DataFrame({"unique_id": "synthetic_001", "ds": ds, "y": y})
        source = "synthetic_fallback"
        error = f"{type(exc).__name__}: {exc}"
    y_df = y_df.copy()
    y_df["ds"] = pd.to_datetime(y_df["ds"])
    y_df = y_df.sort_values(["unique_id", "ds"]).reset_index(drop=True)
    return {"status": "ok", "source": source, "error": error, "y_df": y_df}


def generate_features(y_df: pd.DataFrame) -> pd.DataFrame:
    """Generate time-based features for exploratory covariates."""
    df = y_df.copy()
    ds = pd.to_datetime(df["ds"])
    df["year"] = ds.dt.year
    df["month"] = ds.dt.month
    df["day"] = ds.dt.day
    df["dayofweek"] = ds.dt.dayofweek
    df["dayofyear"] = ds.dt.dayofyear
    df["weekofyear"] = ds.dt.isocalendar().week.astype(int)
    df["is_month_start"] = ds.dt.is_month_start.astype(int)
    df["is_month_end"] = ds.dt.is_month_end.astype(int)
    return df


def create_timesfm_model(runtime: TimesFmRuntimeConfig) -> Dict[str, Any]:
    """
    Create and initialize a TimesFM model.

    Requires either checkpoint_path or huggingface_repo_id.
    """
    import timesfm

    if not runtime.checkpoint_path and not runtime.huggingface_repo_id:
        return {
            "status": "error",
            "error": "checkpoint_path or huggingface_repo_id is required.",
            "model": None,
            "hparams": None,
            "checkpoint": None,
        }

    hparams = timesfm.TimesFmHparams(
        context_len=runtime.context_len,
        horizon_len=runtime.horizon_len,
        input_patch_len=runtime.input_patch_len,
        output_patch_len=runtime.output_patch_len,
        num_layers=runtime.num_layers,
        num_heads=runtime.num_heads,
        model_dims=runtime.model_dims,
        per_core_batch_size=runtime.per_core_batch_size,
        backend=runtime.backend,  # type: ignore[arg-type]
        point_forecast_mode=runtime.point_forecast_mode,  # type: ignore[arg-type]
    )
    ckpt = timesfm.TimesFmCheckpoint(
        version=runtime.checkpoint_version,
        path=runtime.checkpoint_path,
        huggingface_repo_id=runtime.huggingface_repo_id,
        local_dir=runtime.checkpoint_local_dir,
    )
    try:
        model = timesfm.TimesFm(hparams=hparams, checkpoint=ckpt)
        return {"status": "ok", "model": model, "hparams": hparams, "checkpoint": ckpt, "error": None}
    except Exception as exc:  # noqa: BLE001
        return {
            "status": "error",
            "model": None,
            "hparams": hparams,
            "checkpoint": ckpt,
            "error": f"{type(exc).__name__}: {exc}",
        }


def run_forecast(model: Any, y_df: pd.DataFrame, freq: str = "D", value_name: str = "y") -> Dict[str, Any]:
    """Run forecast_on_df and return prediction dataframe."""
    try:
        pred_df = model.forecast_on_df(y_df, freq=freq, value_name=value_name, num_jobs=1)
        return {"status": "ok", "pred_df": pred_df, "error": None}
    except Exception as exc:  # noqa: BLE001
        return {"status": "error", "pred_df": None, "error": f"{type(exc).__name__}: {exc}"}


def analyze_predictions(pred_df: pd.DataFrame, y_df: Optional[pd.DataFrame] = None) -> Dict[str, Any]:
    """Basic analysis summary for generated forecasts."""
    out: Dict[str, Any] = {
        "pred_rows": int(len(pred_df)),
        "pred_columns": list(pred_df.columns),
        "pred_head": pred_df.head(5).to_dict(orient="records"),
    }
    numeric_cols = pred_df.select_dtypes(include=["number"]).columns.tolist()
    if numeric_cols:
        out["numeric_summary"] = pred_df[numeric_cols].describe().to_dict()
    if y_df is not None:
        out["input_rows"] = int(len(y_df))
        out["input_unique_ids"] = int(y_df["unique_id"].nunique()) if "unique_id" in y_df.columns else None
    return out


def save_runtime_artifacts(
    output_dir: str | Path,
    runtime: TimesFmRuntimeConfig,
    y_df: pd.DataFrame,
    features_df: pd.DataFrame,
    pred_df: Optional[pd.DataFrame],
    analysis: Dict[str, Any],
    model_result: Dict[str, Any],
) -> Dict[str, str]:
    """Persist runtime artifacts to disk."""
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    files: Dict[str, str] = {}

    input_path = out_dir / "timesfm_input.csv"
    feature_path = out_dir / "timesfm_features.csv"
    y_df.to_csv(input_path, index=False)
    features_df.to_csv(feature_path, index=False)
    files["input_csv"] = str(input_path)
    files["features_csv"] = str(feature_path)

    if pred_df is not None:
        pred_path = out_dir / "timesfm_predictions.csv"
        pred_df.to_csv(pred_path, index=False)
        files["predictions_csv"] = str(pred_path)

    runtime_path = out_dir / "timesfm_runtime_config.json"
    runtime_path.write_text(json.dumps(asdict(runtime), ensure_ascii=False, indent=2), encoding="utf-8")
    files["runtime_config_json"] = str(runtime_path)

    model_meta = {
        "status": model_result.get("status"),
        "error": model_result.get("error"),
        "checkpoint": str(model_result.get("checkpoint")),
        "hparams": str(model_result.get("hparams")),
    }
    model_meta_path = out_dir / "timesfm_model_meta.json"
    model_meta_path.write_text(json.dumps(model_meta, ensure_ascii=False, indent=2), encoding="utf-8")
    files["model_meta_json"] = str(model_meta_path)

    analysis_path = out_dir / "timesfm_analysis.json"
    analysis_path.write_text(json.dumps(analysis, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    files["analysis_json"] = str(analysis_path)
    return files
