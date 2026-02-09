# ds/src/base/loto_common.py

import argparse
import os
import sys
import logging
import subprocess
from typing import Dict, Any

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

# ==========================================
# ロガー設定
# ==========================================
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# --------------------------
# 設定・定数
# --------------------------
URLS: Dict[str, str] = {
    "mini": "https://loto-life.net/csv/mini",
    "loto6": "https://loto-life.net/csv/loto6",
    "loto7": "https://loto-life.net/csv/loto7",
    "bingo5": "https://loto-life.net/csv/bingo5",
    "numbers3": "https://loto-life.net/csv/numbers3",
    "numbers4": "https://loto-life.net/csv/numbers4",
}
ENCODINGS_TO_TRY = ["utf-8-sig", "cp932", "shift_jis", "utf-8"]

# --------------------------
# DB接続・ユーティリティ関数
# --------------------------
def get_db_engine(args: argparse.Namespace) -> Engine:
    """PostgreSQLエンジン取得（引数または環境変数）"""
    host = args.host or os.getenv("PGHOST", "127.0.0.1")
    port = args.port or os.getenv("PGPORT", "5432")
    db = args.db or os.getenv("PGDATABASE", "loto_db")
    user = args.user or os.getenv("PGUSER", "loto_user")
    password = args.password or os.getenv("PGPASSWORD", "z")

    url = f"postgresql://{user}:{password}@{host}:{port}/{db}"
    try:
        engine = create_engine(url)
        # 実接続テスト（create_engine自体は遅延接続のため）
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        logger.info(f"PostgreSQL接続成功: db={db} host={host}:{port}")
        return engine
    except Exception as e:
        logger.error(f"PostgreSQL接続エラー: {e}")
        raise


def get_sqlite_engine(sqlite_path: str) -> Engine:
    """SQLiteエンジン取得（ローカルファイルDB）"""
    # 例: sqlite:///C:/path/to/loto.db
    url = f"sqlite:///{sqlite_path}"
    try:
        engine = create_engine(url)
        logger.info(f"SQLite接続成功: path={sqlite_path}")
        return engine
    except Exception as e:
        logger.error(f"SQLite接続エラー: {e}")
        raise

def get_env_conn(args: argparse.Namespace) -> Dict[str, str]:
    """引数または環境変数から接続情報を構築（psqlコマンド用）"""
    host = args.host or os.getenv("PGHOST") or os.getenv("PG_HOST") or "127.0.0.1"
    port = args.port or os.getenv("PGPORT") or os.getenv("PG_PORT") or "5432"
    db = args.db or os.getenv("PGDATABASE") or os.getenv("PG_DB") or "loto_db"
    user = args.user or os.getenv("PGUSER") or os.getenv("PG_USER") or "loto_user"
    password = args.password or os.getenv("PGPASSWORD") or os.getenv("PG_PASSWORD")
    schema = args.schema or os.getenv("PGSCHEMA") or os.getenv("PG_SCHEMA") or "public"

    env = {"host": host, "port": port, "db": db, "user": user, "schema": schema}
    if password:
        env["password"] = password
    return env

def qident(name: str) -> str:
    """PostgreSQL識別子を引用符で囲む"""
    return '"' + name.replace('"', '""') + '"'


def qlit(value: str) -> str:
    """SQLリテラル（文字列）を安全に引用する（単純用途向け）"""
    return "'" + value.replace("'", "''") + "'"


def ensure_database_exists(
    env: Dict[str, str],
    target_db: str,
    psql_bin: str = "psql",
    maintenance_db: str = "postgres",
) -> None:
    """PostgreSQL: DBが無ければ作成する。

    注意:
      - 実行ユーザーに CREATEDB 権限が必要。
      - PostgreSQLは CREATE DATABASE IF NOT EXISTS を持たないため、存在確認→作成の順で行う。
    """

    env_maint = dict(env)
    env_maint["db"] = maintenance_db

    # 1) 存在確認
    check_sql = f"SELECT 1 FROM pg_database WHERE datname = {qlit(target_db)};"
    try:
        r = run_psql(check_sql + "\n", env_maint, psql_bin=psql_bin, capture=True)
        exists = (r.stdout or "").strip() == "1"
    except Exception as e:
        logger.warning(
            f"DB存在確認に失敗（maintenance_db={maintenance_db}）: {e}. DB自動作成はスキップします。"
        )
        return

    if exists:
        logger.info(f"DBは既に存在します: {target_db}")
        return

    # 2) 作成
    create_sql = f"CREATE DATABASE {qident(target_db)};"
    try:
        run_psql(create_sql + "\n", env_maint, psql_bin=psql_bin, capture=False)
        logger.info(f"DBを作成しました: {target_db}")
    except Exception as e:
        # race condition などで既に作成済みの場合がある
        msg = str(e)
        if "already exists" in msg or "exists" in msg:
            logger.info(f"DBは既に存在します（同時作成の可能性）: {target_db}")
            return
        logger.warning(f"DB作成に失敗しました: {target_db}. 権限/接続を確認してください。詳細: {e}")


def ensure_schema_exists(engine: Engine, schema: str) -> None:
    """PostgreSQL: schema が無ければ作成する（SQLiteは呼ばない想定）"""
    if not schema:
        return
    sql = f"CREATE SCHEMA IF NOT EXISTS {qident(schema)};"
    with engine.begin() as conn:
        conn.execute(text(sql))
    logger.info(f"Schemaを確認/作成しました: {schema}")

def run_psql(sql: str, env: Dict[str, str], psql_bin: str = "psql", capture: bool = False) -> subprocess.CompletedProcess:
    """psqlコマンドを実行する"""
    e = os.environ.copy()
    e["PGHOST"] = env["host"]
    e["PGPORT"] = str(env["port"])
    e["PGDATABASE"] = env["db"]
    e["PGUSER"] = env["user"]
    e["PG_SCHEMA"] = env["schema"]
    if env.get("password"):
        e["PGPASSWORD"] = env["password"]
        # 出力/メッセージの文字コードをUTF-8に寄せる（デコード事故を減らす）
        e.setdefault("PGCLIENTENCODING", "UTF8")
    else:
        e.pop("PGPASSWORD", None)

    # Windows互換（PSQLRCの無効化）
    e["PAGER"] = "cat"
    e["PSQLRC"] = "NUL" if os.name == "nt" else "/dev/null"

    import shutil

    psql_exec = psql_bin

    # psql_bin がコマンド名の場合は PATH から解決する（WinError 2 予防）

    if not os.path.isabs(psql_exec):

        found = shutil.which(psql_exec)

        if found:

            psql_exec = found

    args = [psql_exec, "-v", "ON_ERROR_STOP=1"]
    args += ["-v", f"schema={env['schema']}"]

    if capture:
        args += ["-A", "-t", "-F", ","]
    return subprocess.run(
        args,
        input=sql,
        text=True,
        env=e,
        capture_output=capture,
        check=True,  # エラー時に例外を発生させる
        encoding='utf-8',
        errors='replace',
    )
