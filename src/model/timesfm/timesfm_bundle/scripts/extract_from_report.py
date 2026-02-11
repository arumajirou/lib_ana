#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""CLE V6 のフルレポート（HTML）から主要テーブルを抽出して CSV/JSON として保存します。

想定入力:
  ../site/cle_report.html

出力:
  ../extracted/summary.json
  ../extracted/tables_*.csv
  ../extracted/nodes.csv
  ../extracted/edges.csv

依存:
  - pandas

実行:
  python scripts/extract_from_report.py
"""

from __future__ import annotations

import json
from pathlib import Path
from io import StringIO

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
REPORT_HTML = ROOT / "site" / "cle_report.html"
OUTDIR = ROOT / "extracted"


def main() -> None:
    if not REPORT_HTML.exists():
        raise FileNotFoundError(f"report not found: {REPORT_HTML}")

    OUTDIR.mkdir(parents=True, exist_ok=True)

    html = REPORT_HTML.read_text(encoding="utf-8", errors="ignore")

    # pandas.read_html は将来、文字列直渡しが非推奨になるため StringIO 経由にする
    tables = pd.read_html(StringIO(html))

    if len(tables) < 10:
        raise RuntimeError(f"unexpected tables count: {len(tables)}")

    summary_df = tables[0]
    modules_df = tables[1]
    classes_df = tables[2]
    functions_df = tables[3]
    methods_df = tables[4]
    external_df = tables[5]
    nodes_df = tables[8]
    edges_df = tables[9]

    modules_df.to_csv(OUTDIR / "tables_modules.csv", index=False)
    classes_df.to_csv(OUTDIR / "tables_classes.csv", index=False)
    functions_df.to_csv(OUTDIR / "tables_functions.csv", index=False)
    methods_df.to_csv(OUTDIR / "tables_methods.csv", index=False)
    external_df.to_csv(OUTDIR / "tables_external.csv", index=False)
    nodes_df.to_csv(OUTDIR / "nodes.csv", index=False)
    edges_df.to_csv(OUTDIR / "edges.csv", index=False)

    summary = {row["Metric"]: row["Value"] for _, row in summary_df.iterrows()}
    (OUTDIR / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print("ok: extracted tables ->", OUTDIR)


if __name__ == "__main__":
    main()
