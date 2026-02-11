from __future__ import annotations
import streamlit.components.v1 as components

def mermaid(code: str, height: int = 600) -> None:
    """Mermaid を Streamlit 上で描画（CDN利用）。"""
    html_doc = f"""<!doctype html>
<html>
  <head>
    <meta charset="utf-8" />
    <script src="https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.min.js"></script>
  </head>
  <body>
    <div class="mermaid">{code}</div>
    <script>
      mermaid.initialize({{ startOnLoad: true, theme: "default" }});
    </script>
  </body>
</html>
"""
    components.html(html_doc, height=height, scrolling=True)
