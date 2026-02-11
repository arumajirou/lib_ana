from __future__ import annotations
from typing import Any, Dict, List, Optional, Tuple

from .models import Graph, Node, Edge

def _table_id(schema: str, table: str) -> str:
    return f"{schema}.{table}"

class GraphBuilder:
    def build_er_graph_from_fk_rows(self, fk_rows: List[Dict[str, Any]], schema_filter: Optional[str] = None) -> Graph:
        g = Graph()
        for r in fk_rows:
            cs, ct = r["child_schema"], r["child_table"]
            ps, pt = r["parent_schema"], r["parent_table"]
            if schema_filter and (cs != schema_filter and ps != schema_filter):
                continue

            child_id = _table_id(cs, ct)
            parent_id = _table_id(ps, pt)

            if child_id not in g.nodes:
                g.add_node(Node(node_id=child_id, label=ct, node_type="table", meta={"schema": cs}))
            if parent_id not in g.nodes:
                g.add_node(Node(node_id=parent_id, label=pt, node_type="table", meta={"schema": ps}))

            g.add_edge(Edge(src=child_id, dst=parent_id, edge_type="fk", label=r.get("fk_name", "")))
        return g

    def build_table_graph(self, schema: str, tables: List[str]) -> Graph:
        g = Graph()
        for t in tables:
            node_id = _table_id(schema, t)
            if node_id not in g.nodes:
                g.add_node(Node(node_id=node_id, label=t, node_type="table", meta={"schema": schema}))
        return g

    def build_dep_graph_simple(self, edges: List[Tuple[str, str, str]]) -> Graph:
        g = Graph()
        for src, dst, label in edges:
            if src not in g.nodes:
                g.add_node(Node(node_id=src, label=src.split(".")[-1], node_type="obj"))
            if dst not in g.nodes:
                g.add_node(Node(node_id=dst, label=dst.split(".")[-1], node_type="obj"))
            g.add_edge(Edge(src=src, dst=dst, edge_type="dep", label=label))
        return g
