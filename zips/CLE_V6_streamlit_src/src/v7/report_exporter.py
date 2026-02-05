# ファイルパス: C:\lib_ana\src\v6\report_exporter.py
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

import pandas as pd

DEFAULT_OUT_DIR = Path(r"C:\lib_ana\outputs\reports_v6")

@dataclass
class ReportBundle:
    library: str
    created_at: str
    summary: Dict[str, Any]
    tables: Dict[str, pd.DataFrame]
    notes: str = ""
    links: Optional[list] = None
    mermaid_mmd: str = ""
    sample_code: str = ""

def export_single_html(bundle: ReportBundle, out_dir: Path = DEFAULT_OUT_DIR) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = out_dir / f"cle_v6_{bundle.library}_{ts}.html"
    html_parts = []
    html_parts.append("<html><head><meta charset='utf-8'>")
    html_parts.append("<style>body{font-family:system-ui,Segoe UI,Arial;margin:24px} table{border-collapse:collapse} td,th{border:1px solid #ddd;padding:6px} th{background:#f5f5f5} code,pre{background:#f8fafc;padding:8px;border-radius:8px}</style>")
    html_parts.append(f"<title>CLE V6 Report - {bundle.library}</title></head><body>")
    html_parts.append(f"<h1>CLE V6 Report — {bundle.library}</h1>")
    html_parts.append(f"<div style='color:#666'>Created: {bundle.created_at}</div>")

    # summary
    html_parts.append("<h2>Summary</h2>")
    html_parts.append("<pre>" + json.dumps(bundle.summary, ensure_ascii=False, indent=2) + "</pre>")

    # links
    if bundle.links:
        html_parts.append("<h2>Links</h2><ul>")
        for it in bundle.links:
            url = (it.get("url") if isinstance(it, dict) else str(it))
            label = (it.get("title") if isinstance(it, dict) else url)
            html_parts.append(f"<li><a href='{url}' target='_blank' rel='noreferrer'>{label}</a></li>")
        html_parts.append("</ul>")

    # tables
    html_parts.append("<h2>Tables</h2>")
    for name, df in (bundle.tables or {}).items():
        html_parts.append(f"<h3>{name}</h3>")
        try:
            html_parts.append(df.to_html(index=False, escape=True))
        except Exception:
            html_parts.append("<pre>(table render failed)</pre>")

    # mermaid
    if bundle.mermaid_mmd:
        html_parts.append("<h2>Mermaid</h2>")
        # mermaid runtime
        html_parts.append("""
        <script src="https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.min.js"></script>
        <script>mermaid.initialize({startOnLoad:true});</script>
        """)
        html_parts.append(f"<pre class='mermaid'>{bundle.mermaid_mmd}</pre>")

    # sample code
    if bundle.sample_code:
        html_parts.append("<h2>Sample Code</h2>")
        html_parts.append("<pre><code>" + bundle.sample_code.replace("<","&lt;").replace(">","&gt;") + "</code></pre>")

    if bundle.notes:
        html_parts.append("<h2>Notes</h2>")
        html_parts.append("<pre>" + bundle.notes.replace("<","&lt;").replace(">","&gt;") + "</pre>")

    html_parts.append("</body></html>")
    out_path.write_text("\n".join(html_parts), encoding="utf-8")
    return out_path
