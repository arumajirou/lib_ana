# ds/src/base/loto_y_ts_etl.py

import argparse
import time
import sys
import tempfile
import os
import subprocess # subprocessのインポートはloto_commonで行われているが、念のため再度確認
from pathlib import Path
from datetime import datetime
from typing import List, Tuple, Dict
import pandas as pd
from sqlalchemy import text, Table, MetaData
import sqlalchemy.types

# 同じディレクトリからの相対インポート
from loto_common import (
    get_db_engine,
    get_sqlite_engine,
    get_env_conn,
    ensure_database_exists,
    ensure_schema_exists,
    logger,
    qident,
    run_psql,
)
from loto_extractor import LotoExtractor
from loto_transformer import LotoTransformer


def create_output_table(engine, schema, table_name, df: pd.DataFrame, key_cols: List[str]):
    """出力テーブルを作成し、UNIQUE INDEXを設定する (REPLACEモード用)"""
    output_schema = qident(schema)
    output_table = qident(table_name)
    
    final_dtype_map = _build_dtype_map(df)


    # to_sqlでテーブル作成 (replaceモードと同じ動作)
    df.head(0).to_sql(table_name, engine, schema=schema, if_exists='replace', index=False, dtype=final_dtype_map)
    
    with engine.begin() as conn:
        key_cols_sql = ", ".join([qident(c) for c in key_cols])
        # 主キー: key_cols
        conn.execute(text(f"""
            CREATE UNIQUE INDEX IF NOT EXISTS uidx_{table_name}_key 
            ON {output_schema}.{output_table} ({key_cols_sql});
        """))
    logger.info(f"テーブル {schema}.{table_name} を新規作成し、UNIQUE INDEXを設定しました。キー: ({', '.join(key_cols)})")


def _build_dtype_map(df: pd.DataFrame) -> Dict[str, sqlalchemy.types.TypeEngine]:
    """出力テーブル用のdtypeマップを生成（psql/sqlalchemy 両方で使う）"""
    dtype_map: Dict[str, sqlalchemy.types.TypeEngine] = {
        'loto': sqlalchemy.types.Text,
        'unique_id': sqlalchemy.types.Text,
        'ds': sqlalchemy.types.Date,
        'ts_type': sqlalchemy.types.Text,
        'y': sqlalchemy.types.Float,
        'exec_ts': sqlalchemy.types.DateTime,
        'updated_ts': sqlalchemy.types.DateTime,
        'proc_seconds': sqlalchemy.types.Float,
    }
    for c in [c for c in df.columns if str(c).startswith('hist_')]:
        dtype_map[c] = sqlalchemy.types.Float
    # dfに含まれる全列を埋める（未知列はFloat）
    return {c: dtype_map.get(c, sqlalchemy.types.Float) for c in df.columns}


def ensure_output_table(engine, schema: str, table_name: str, df: pd.DataFrame, key_cols: List[str]) -> None:
    """appendモードでも、ターゲットテーブルが無ければ作成してからUPSERTできるようにする"""
    final_dtype_map = _build_dtype_map(df)
    df.head(0).to_sql(table_name, engine, schema=schema, if_exists='append', index=False, dtype=final_dtype_map)
    with engine.begin() as conn:
        key_cols_sql = ", ".join([qident(c) for c in key_cols])
        conn.execute(text(f"""
            CREATE UNIQUE INDEX IF NOT EXISTS uidx_{table_name}_key
            ON {qident(schema)}.{qident(table_name)} ({key_cols_sql});
        """))
    logger.info(f"テーブル {schema}.{table_name} を確認/作成しました（append対応）。キー: ({', '.join(key_cols)})")

def copy_from_csv_with_upsert(
    schema: str, 
    table: str, 
    cols: List[str], 
    csv_path: Path, 
    env: Dict[str, str], 
    psql_bin: str,
    key_cols: List[str] # ★ キーカラムを引数で受け取るように変更
):
    """psqlの\copyとON CONFLICT DO UPDATEを使用してデータを投入する"""
    
    stg = f"_{table}_stg"
    
    # UPDATEする非キー列
    nonkey_cols = [c for c in cols if c not in key_cols]
    set_sql = ", ".join([f"{qident(c)} = EXCLUDED.{qident(c)}" for c in nonkey_cols])
    
    # 衝突時の更新処理。y, hist_*, タイムスタンプを更新対象とする。
    on_conflict = f"DO UPDATE SET {set_sql}"
    
    keys_sql = ", ".join([qident(c) for c in key_cols])
    cols_sql = ", ".join([qident(c) for c in cols])
    tgt = f"{qident(schema)}.{qident(table)}"
    
    # 一時テーブルにCSVをCOPYし、そこからターゲットテーブルにマージ (UPSERT)
    # csv_path が絶対パスであることを前提とする（tempfile.mkdtempを使っているため）
    cmd = f"""
    DROP TABLE IF EXISTS {qident(stg)};
    CREATE TEMP TABLE {qident(stg)} (LIKE {tgt});
    \\copy {qident(stg)} ({cols_sql}) FROM '{csv_path}' WITH (FORMAT csv, NULL '\\N');
    
    INSERT INTO {tgt} ({cols_sql})
    SELECT {cols_sql}
    FROM {qident(stg)}
    ON CONFLICT ({keys_sql}) {on_conflict};
    """
    try:
        run_psql(cmd + "\n", env, psql_bin=psql_bin)
        logger.info(f"[OK] {table} にデータを投入・更新しました。キー: ({', '.join(key_cols)})")
    except subprocess.CalledProcessError as e:
        logger.error(f"PostgreSQLでのデータ投入エラー: {e.stderr}")
        raise


def _is_sqlite(engine) -> bool:
    return getattr(engine.dialect, "name", "") == "sqlite"


def _qual_name(engine, schema: str | None, table: str) -> str:
    """方言に合わせたテーブル名（スキーマ）"""
    if _is_sqlite(engine) or not schema:
        return qident(table)
    return f"{qident(schema)}.{qident(table)}"


def create_unique_index(engine, schema: str | None, table: str, key_cols: List[str]):
    """UNIQUE INDEX を作成（SQLite/PostgreSQL両対応）"""
    idx_name = f"uidx_{table}_key"
    cols_sql = ", ".join([qident(c) for c in key_cols])
    tgt = _qual_name(engine, schema, table)
    # SQLiteもPostgreSQLも IF NOT EXISTS をサポート
    sql = f"CREATE UNIQUE INDEX IF NOT EXISTS {qident(idx_name)} ON {tgt} ({cols_sql});"
    with engine.begin() as conn:
        conn.execute(text(sql))


def upsert_df_sqlalchemy(
    engine,
    schema: str | None,
    table_name: str,
    df: pd.DataFrame,
    key_cols: List[str],
    mode: str,
):
    """SQLAlchemyでUPSERT（SQLite/PostgreSQL両対応）。psqlが無い環境でも動く。"""
    if df.empty:
        logger.warning(f"[SKIP] {table_name}: データが空です")
        return

    # SQLiteはスキーマ無し
    if _is_sqlite(engine):
        schema = None

    # テーブル作成
    if mode == "replace":
        df.head(0).to_sql(table_name, engine, schema=schema, if_exists="replace", index=False)
    else:
        # appendならテーブルが無ければ作る
        df.head(0).to_sql(table_name, engine, schema=schema, if_exists="append", index=False)

    # UNIQUE INDEX
    create_unique_index(engine, schema, table_name, key_cols)

    # 反射してTableを得る
    meta = MetaData()
    tbl = Table(table_name, meta, autoload_with=engine, schema=schema)

    nonkey_cols = [c for c in df.columns if c not in key_cols]

    dialect = getattr(engine.dialect, "name", "")
    if dialect == "postgresql":
        from sqlalchemy.dialects.postgresql import insert as _insert
    elif dialect == "sqlite":
        from sqlalchemy.dialects.sqlite import insert as _insert
    else:
        # 想定外方言はappendのみ（重複は許容）
        df.to_sql(table_name, engine, schema=schema, if_exists="append", index=False)
        logger.warning(f"[WARN] 未対応dialect={dialect}. appendのみ実行しました: {table_name}")
        return

    # チャンクでUPSERT
    records = df.to_dict(orient="records")
    chunk_size = 5000
    with engine.begin() as conn:
        for i in range(0, len(records), chunk_size):
            chunk = records[i : i + chunk_size]
            stmt = _insert(tbl).values(chunk)
            set_dict = {c: getattr(stmt.excluded, c) for c in nonkey_cols}
            stmt = stmt.on_conflict_do_update(index_elements=key_cols, set_=set_dict)
            conn.execute(stmt)
    logger.info(f"[OK] {table_name}: UPSERT完了（rows={len(df)}）")

def main(args: argparse.Namespace) -> int:
    
    t0 = time.time()
    exec_ts = datetime.now()
    
    backend = getattr(args, "backend", "psql")
    schema = args.schema
    ts_table = args.output_table # 時系列テーブル
    hist_table = args.hist_table # 横持ち特徴量テーブル
    lotos = [x.strip() for x in args.lotos.split(",") if x.strip()]

    # 1. 接続 & 環境設定
    env = None
    if backend == "psql":
        # psqlバックエンド: db/schema/table を指定でき、未指定(=デフォルト)でも自動作成を試みる
        env = get_env_conn(args)
        maintenance_db = getattr(args, "maintenance_db", "postgres")
        ensure_database_exists(env, target_db=env["db"], psql_bin=args.psql_bin, maintenance_db=maintenance_db)

        engine = get_db_engine(args)
        # schemaが無いと to_sql / COPY が落ちるので、先に作る
        ensure_schema_exists(engine, schema)
    elif backend == "sqlite":
        engine = get_sqlite_engine(args.sqlite_path)
        # SQLiteはスキーマ概念が弱いので無視（テーブル名で管理）
        if schema not in (None, "", "public"):
            logger.warning(f"SQLiteでは schema={schema} を無視します")
        schema = None
    elif backend == "spark":
        engine = None
        schema = None
    else:
        raise RuntimeError(f"未知のbackend: {backend}")

    logger.info(f"Start ETL backend={backend} mode={args.mode} ts_table={ts_table} hist_table={hist_table}")

    # 2. データ取得・整形・縦持ち化 (loto_base相当のDataFrameをメモリ上に生成)
    extractor = LotoExtractor()
    df_long_base = extractor.extract_and_transform(lotos)
    if df_long_base.empty:
        logger.error("抽出データが空です。処理を中止します。")
        return 1

    # 3. 特徴量変換
    transformer = LotoTransformer()
    df_transformed = transformer.transform_and_melt(df_long_base)

    # 4. メタ情報付与
    proc_seconds = float(time.time() - t0)
    df_transformed["exec_ts"] = exec_ts
    df_transformed["updated_ts"] = exec_ts 
    df_transformed["proc_seconds"] = proc_seconds
    
    # Float型のデータ列を最終調整
    df_transformed['y'] = pd.to_numeric(df_transformed['y'], errors='coerce').astype('float64')
    hist_cols = [c for c in df_transformed.columns if c.startswith('hist_')]
    for c in hist_cols:
         df_transformed[c] = pd.to_numeric(df_transformed[c], errors='coerce').astype('float64')
    
    logger.info(f"最終データフレーム: {df_transformed.shape}. {len(transformer.TRANSFORMS)}種類の時系列を生成。")

    
    # 5. DB操作: 2つのテーブルにデータを分割
    
    ts_key_cols = ['loto', 'ds', 'unique_id', 'ts_type'] # 時系列テーブルのキー
    hist_key_cols = ['loto', 'ds', 'unique_id'] # 横持ち特徴量テーブルのキー (ts_typeなし)
    ts_cols = ['exec_ts', 'updated_ts', 'proc_seconds']
    
    
    # --- 5-A. 時系列データ (loto_y_ts) の準備 ---
    ts_all_cols = ts_key_cols + ['y'] + ts_cols
    df_ts_output = df_transformed[ts_all_cols].copy()
    
    # --- 5-B. 横持ち特徴量データ (loto_hist_feat) の準備 ---
    # 横持ち特徴量はts_typeに関わらず同じ値を持つため、ts_type='raw'の行を代表として抽出し、重複を削除
    hist_all_cols = hist_key_cols + hist_cols + ts_cols
    df_hist_output = df_transformed[df_transformed['ts_type'] == 'raw'][hist_all_cols]
    df_hist_output = df_hist_output.drop_duplicates(subset=hist_key_cols).copy()
    
    logger.info(f"時系列テーブルデータ行数: {len(df_ts_output)}")
    logger.info(f"横持ち特徴量テーブルデータ行数: {len(df_hist_output)}")

    # ------------------------------
    # backendごとの書き込み
    # ------------------------------
    if backend == "sqlite":
        try:
            upsert_df_sqlalchemy(engine, schema, ts_table, df_ts_output, key_cols=ts_key_cols, mode=args.mode)
            upsert_df_sqlalchemy(engine, schema, hist_table, df_hist_output, key_cols=hist_key_cols, mode=args.mode)
        except Exception as e:
            logger.error(f"SQLite書き込みエラー: {e}")
            return 1

        elapsed = time.time() - t0
        logger.info(f"処理完了（SQLite）。所要時間: {elapsed:.2f}秒。")
        return 0

    if backend == "spark":
        try:
            from pyspark.sql import SparkSession
        except Exception as e:
            logger.error("PySparkが見つかりません。backend=spark を使うには pyspark をインストールしてください。")
            logger.error(str(e))
            return 1

        out_dir = Path(args.spark_out).expanduser().resolve()
        out_dir.mkdir(parents=True, exist_ok=True)
        spark = (
            SparkSession.builder
            .appName("loto_etl")
            .master(args.spark_master if args.spark_master else "local[*]")
            .config("spark.driver.extraJavaOptions", "-Djava.security.manager=allow")
            .config("spark.executor.extraJavaOptions", "-Djava.security.manager=allow")
            .getOrCreate()
        )


        def _write_parquet(df_pd: pd.DataFrame, name: str, key_cols_: List[str]):
            p = out_dir / name
            sdf = spark.createDataFrame(df_pd)
            if args.mode == "replace" or not p.exists():
                sdf.write.mode("overwrite").parquet(str(p))
            else:
                old = spark.read.parquet(str(p))
                merged = old.unionByName(sdf, allowMissingColumns=True)
                merged = merged.dropDuplicates(key_cols_)
                merged.write.mode("overwrite").parquet(str(p))

        _write_parquet(df_ts_output, ts_table, ts_key_cols)
        _write_parquet(df_hist_output, hist_table, hist_key_cols)
        spark.stop()

        elapsed = time.time() - t0
        logger.info(f"処理完了（Spark/Parquet）。所要時間: {elapsed:.2f}秒。 out={out_dir}")
        return 0


    # 6. 一時ファイルに書き出し
    tmp_dir = Path(args.tmp_dir) if args.tmp_dir else Path(tempfile.mkdtemp(prefix="loto_ts_pg_"))
    tmp_dir.mkdir(parents=True, exist_ok=True)
    
    # CSV書き出し (時系列)
    ts_csv = tmp_dir / f"{ts_table}.csv"
    df_ts_output.to_csv(ts_csv, index=False, header=False, na_rep="\\N")
    logger.info(f"時系列データ ({len(df_ts_output)}行) を一時ファイルに書き出し: {ts_csv}")
    
    # CSV書き出し (横持ち特徴量)
    hist_csv = tmp_dir / f"{hist_table}.csv"
    df_hist_output.to_csv(hist_csv, index=False, header=False, na_rep="\\N")
    logger.info(f"横持ち特徴量データ ({len(df_hist_output)}行) を一時ファイルに書き出し: {hist_csv}")


    # 7. DB書き込み実行
    try:
        # --- 7-A. 時系列データ (loto_y_ts) の書き込み ---
        logger.info(f"テーブル {schema}.{ts_table} への書き込みを開始します。")
        if args.mode == "replace":
            # df_ts_output を使用してテーブル作成とUNIQUE INDEX設定
            create_output_table(engine, schema, ts_table, df_ts_output, key_cols=ts_key_cols)
        else:
            # appendでも、テーブルが無ければ作る
            ensure_output_table(engine, schema, ts_table, df_ts_output, key_cols=ts_key_cols)
        
        # UPSERT実行 (時系列テーブル)
        copy_from_csv_with_upsert(schema, ts_table, ts_all_cols, ts_csv, env, args.psql_bin, key_cols=ts_key_cols)

        # --- 7-B. 横持ち特徴量データ (loto_hist_feat) の書き込み ---
        logger.info(f"テーブル {schema}.{hist_table} への書き込みを開始します。")
        if args.mode == "replace":
            # df_hist_output を使用してテーブル作成とUNIQUE INDEX設定
            create_output_table(engine, schema, hist_table, df_hist_output, key_cols=hist_key_cols)
        else:
            # appendでも、テーブルが無ければ作る
            ensure_output_table(engine, schema, hist_table, df_hist_output, key_cols=hist_key_cols)

        # UPSERT実行 (横持ち特徴量テーブル)
        copy_from_csv_with_upsert(schema, hist_table, hist_all_cols, hist_csv, env, args.psql_bin, key_cols=hist_key_cols)

    except Exception as e:
        logger.error(f"DB書き込みエラーが発生しました: {e}")
        return 1
        
    finally:
        # 一時ディレクトリのクリーンアップ
        if not args.tmp_dir:
            import shutil
            shutil.rmtree(tmp_dir, ignore_errors=True)
            logger.info(f"一時ディレクトリを削除しました: {tmp_dir}")
        
    
    elapsed = time.time() - t0
    logger.info(f"処理完了。所要時間: {elapsed:.2f}秒。")
    logger.info(f"作成日時: {exec_ts.isoformat(sep=' ')}")
    logger.info(f"更新日時: {exec_ts.isoformat(sep=' ')}")
    return 0

if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Loto Data (loto_base equivalent) to Transformed Time Series (loto_y_ts) ETL.")

    # 出力先（backend選択）
    ap.add_argument(
        "--backend",
        choices=["psql", "sqlite", "spark"],
        default="psql",
        help="Output backend: psql(PostgreSQL+psql), sqlite(SQLite file), spark(Parquet via PySpark).",
    )
    ap.add_argument(
        "--sqlite-path",
        default="loto.sqlite3",
        help="SQLite file path (used when --backend sqlite).",
    )
    ap.add_argument(
        "--spark-out",
        default="spark_out",
        help="Output directory for Parquet (used when --backend spark).",
    )
    ap.add_argument(
        "--spark-master",
        default=None,
        help="Spark master (e.g. local[*]) (used when --backend spark).",
    )
    
    # 接続設定
    ap.add_argument("--host", default=None)
    ap.add_argument("--port", default=None)
    ap.add_argument("--db", default=None)
    ap.add_argument("--user", default=None)
    ap.add_argument("--password", default=None)
    ap.add_argument("--schema", default="public")
    ap.add_argument(
        "--maintenance-db",
        default="postgres",
        help="Database name used only for auto-creating the target DB (psql backend).",
    )
    
    # テーブル設定
    ap.add_argument("--output-table", default="loto_y_ts", help="Output table for transformed series (default: loto_y_ts).")
    ap.add_argument("--hist-table", default="loto_hist_feat", help="Output table for history features (hist_* columns).") # ★ 追加
    ap.add_argument("--mode", choices=["replace", "append"], default="append", help="DB write mode: 'replace' drops table, 'append' inserts/updates.")
    ap.add_argument("--lotos", default="mini,loto6,loto7,bingo5,numbers3,numbers4", help="Comma-separated list of lotteries to process.")
    ap.add_argument("--psql-bin", default="psql", help="Path to psql binary.")
    ap.add_argument("--tmp-dir", default=None, help="Temporary directory path (leave None to use system default and auto-delete).")

    args = ap.parse_args()
    sys.exit(main(args))
