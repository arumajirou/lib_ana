from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Dict, List

@dataclass(frozen=True)
class Edge:
    src: str
    dst: str
    edge_type: str  # "fk" | "dep" | etc
    label: str = ""
    meta: Dict[str, Any] = field(default_factory=dict)

@dataclass(frozen=True)
class Node:
    node_id: str
    label: str
    node_type: str  # "table" | "view" | "schema" | etc
    meta: Dict[str, Any] = field(default_factory=dict)

@dataclass
class Graph:
    nodes: Dict[str, Node] = field(default_factory=dict)
    edges: List[Edge] = field(default_factory=list)

    def add_node(self, node: Node) -> None:
        self.nodes[node.node_id] = node

    def add_edge(self, edge: Edge) -> None:
        self.edges.append(edge)
