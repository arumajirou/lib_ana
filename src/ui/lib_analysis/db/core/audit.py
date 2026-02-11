from __future__ import annotations
import json, time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional

@dataclass
class AuditLogger:
    log_path: Path

    def __post_init__(self) -> None:
        self.log_path.parent.mkdir(parents=True, exist_ok=True)

    def log(
        self,
        action: str,
        target: str,
        sql: str,
        status: str,
        profile: Optional[str] = None,
        error: Optional[str] = None,
        elapsed_ms: Optional[int] = None,
        meta: Optional[Dict[str, Any]] = None,
    ) -> None:
        rec = {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
            "action": action,
            "target": target,
            "sql": sql,
            "status": status,
            "profile": profile,
            "elapsed_ms": elapsed_ms,
            "error": error,
            "meta": meta or {},
        }
        with self.log_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
