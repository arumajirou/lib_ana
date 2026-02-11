from __future__ import annotations
import os, sys, platform, re, shutil
from pathlib import Path
from dataclasses import dataclass

def detect_runtime() -> str:
    """windows / wsl / linux を推定する（軽量）。"""
    if sys.platform.startswith("win"):
        return "windows"
    rel = platform.release().lower()
    if ("microsoft" in rel) or os.environ.get("WSL_DISTRO_NAME") or os.environ.get("WSL_INTEROP"):
        return "wsl"
    return "linux"

def win_to_wsl_candidates(path_win: str) -> list[str]:
    """Windows パスから WSL の典型マウント候補へ変換する。"""
    m = re.match(r"^([A-Za-z]):\\(.*)$", path_win)
    if not m:
        return [path_win.replace("\\", "/")]
    drive = m.group(1).lower()
    rest = m.group(2).replace("\\", "/")
    return [
        f"/mnt/{drive}/{rest}",
        f"/mnt/host/{drive}/{rest}",
        f"/run/desktop/mnt/host/{drive}/{rest}",
        f"/{drive}/{rest}",
    ]

@dataclass(frozen=True)
class PgBinaries:
    psql: str | None
    pg_dump: str | None

def find_pg_binaries(psql_win: str | None = None, pg_dump_win: str | None = None) -> PgBinaries:
    """psql / pg_dump のパスを（可能な範囲で）自動解決する。"""
    runtime = detect_runtime()

    if runtime == "windows":
        psql = psql_win if psql_win and Path(psql_win).exists() else shutil.which("psql")
        pg_dump = pg_dump_win if pg_dump_win and Path(pg_dump_win).exists() else shutil.which("pg_dump")
        return PgBinaries(psql=psql, pg_dump=pg_dump)

    # linux / wsl
    psql = shutil.which("psql")
    pg_dump = shutil.which("pg_dump")

    if not psql and psql_win:
        for cand in win_to_wsl_candidates(psql_win):
            if Path(cand).exists():
                psql = cand
                break
    if not pg_dump and pg_dump_win:
        for cand in win_to_wsl_candidates(pg_dump_win):
            if Path(cand).exists():
                pg_dump = cand
                break

    return PgBinaries(psql=psql, pg_dump=pg_dump)
