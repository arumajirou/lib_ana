from __future__ import annotations
from .models import Graph

def _sanitize_id(s: str) -> str:
    return s.replace(".", "__").replace("-", "_")

def render_er_mermaid(graph: Graph, show_schema: bool = False) -> str:
    lines = ["erDiagram"]
    for node_id, node in graph.nodes.items():
        tbl = node_id if show_schema else node.label
        lines.append(f"  {_sanitize_id(node_id)} {{")
        lines.append(f'    string __name "{tbl}"')
        lines.append("  }")

    for e in graph.edges:
        if e.edge_type != "fk":
            continue
        a = _sanitize_id(e.src)
        b = _sanitize_id(e.dst)
        label = (e.label or "FK").replace('"', "'")
        lines.append(f'  {a} }}o--|| {b} : "{label}"')

    return "\n".join(lines) + "\n"

def render_dep_mermaid(graph: Graph) -> str:
    lines = ["graph TD"]
    for node_id, node in graph.nodes.items():
        nid = _sanitize_id(node_id)
        label = node.label.replace('"', "'")
        lines.append(f'{nid}["{label}"]')

    for e in graph.edges:
        a = _sanitize_id(e.src)
        b = _sanitize_id(e.dst)
        label = e.label.replace('"', "'") if e.label else ""
        if label:
            lines.append(f'{a} -->|"{label}"| {b}')
        else:
            lines.append(f"{a} --> {b}")
    return "\n".join(lines) + "\n"
