from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass(frozen=True)
class MermaidExportOptions:
    title: str = "Cognitive Library Explorer - Diagram"
    use_cdn: bool = True


def mermaid_html(diagram_code: str, options: Optional[MermaidExportOptions] = None) -> str:
    options = options or MermaidExportOptions()
    cdn = "https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.min.js"
    script_tag = f'<script src="{cdn}"></script>' if options.use_cdn else "<!-- mermaid js not included -->"

    escaped = (
        diagram_code.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )

    # Use triple-single-quotes to avoid conflicts when this file is generated.
    return f'''<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>{options.title}</title>
  {script_tag}
  <style>
    body {{ font-family: system-ui, -apple-system, Segoe UI, Roboto, Helvetica, Arial; margin: 16px; }}
    .mermaid {{ background: #fff; padding: 12px; border: 1px solid #ddd; border-radius: 8px; }}
    pre {{ background: #f6f8fa; padding: 12px; border-radius: 8px; overflow-x: auto; }}
  </style>
</head>
<body>
  <h2>{options.title}</h2>
  <div class="mermaid">
{diagram_code}
  </div>
  <h3>Mermaid source</h3>
  <pre><code>{escaped}</code></pre>
  <script>
    if (window.mermaid) {{
      mermaid.initialize({{ startOnLoad: true }});
    }}
  </script>
</body>
</html>
'''


def export_mermaid_html(diagram_code: str, out_path: Path, options: Optional[MermaidExportOptions] = None) -> Path:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(mermaid_html(diagram_code, options), encoding="utf-8")
    return out_path
