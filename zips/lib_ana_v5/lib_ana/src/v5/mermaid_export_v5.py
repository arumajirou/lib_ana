from __future__ import annotations

import html
from typing import Tuple

import pandas as pd

from mermaid_export_v4 import to_mermaid_flowchart


def mermaid_html_page(mmd: str, title: str = "Mermaid Diagram") -> str:
    """Mermaid 記法文字列から単体で開ける HTML を生成する."""
    escaped = html.escape(mmd)
    return f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <title>{html.escape(title)}</title>
  <script src="https://cdn.jsdelivr.net/npm/mermaid/dist/mermaid.min.js"></script>
  <style>
    body {{ font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
           margin: 0; padding: 16px; background:#0b1020; color:#f9fafb; }}
    .mermaid {{ background:#111827; border-radius: 12px; padding:16px; }}
    h2 {{ margin-top: 0; }}
  </style>
</head>
<body>
  <h2>{html.escape(title)}</h2>
  <div class="mermaid">
{escaped}
  </div>
  <script>mermaid.initialize({{startOnLoad:true}});</script>
</body>
</html>
"""


def make_mermaid_and_html(
    df_nodes: pd.DataFrame,
    df_edges: pd.DataFrame,
    lib_name: str,
    max_nodes: int = 260,
) -> Tuple[str, str]:
    """Mermaid(MMD)コードと HTML ドキュメントを同時に生成する."""
    mmd = to_mermaid_flowchart(df_nodes, df_edges, lib_name, max_nodes=max_nodes)
    html_doc = mermaid_html_page(mmd, title=f"Mermaid diagram for {lib_name}")
    return mmd, html_doc
