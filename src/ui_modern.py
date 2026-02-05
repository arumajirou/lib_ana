# -*- coding: utf-8 -*-
from __future__ import annotations

import argparse
import ast
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

# Optional: If these exist in C:\lib_ana\src\, we can analyze directly (V4 analyzer).
# If you want UI only for existing CSV/JSON outputs, pass --input and no imports are needed.
try:
    from analyzer_v4 import LibraryAnalyzerV4  # type: ignore
    from models_v4 import AnalysisConfig       # type: ignore
    from mermaid_export_v4 import to_mermaid_flowchart  # type: ignore
    _HAS_V4 = True
except Exception:
    _HAS_V4 = False

try:
    from taxonomy_v4 import classify_events  # type: ignore
except Exception:
    def classify_events(name: str, doc: str = "") -> List[str]:  # fallback
        return ["other"]


def _ts() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def _project_root_from_this_file() -> Path:
    # If this file is at C:\lib_ana\src\ui_modern.py, project root = C:\lib_ana
    return Path(__file__).resolve().parents[1]


def _ensure_dirs(root: Path) -> Dict[str, Path]:
    outputs = root / "outputs"
    api_tables = outputs / "api_tables"
    reports = outputs / "reports"
    logs = root / "logs"
    for p in (outputs, api_tables, reports, logs):
        p.mkdir(parents=True, exist_ok=True)
    return {"outputs": outputs, "api_tables": api_tables, "reports": reports, "logs": logs}


def _relpath(from_path: Path, to_path: Path) -> str:
    try:
        return os.path.relpath(str(to_path), start=str(from_path.parent)).replace("\\", "/")
    except Exception:
        return str(to_path).replace("\\", "/")


def _load_local_lib_paths(root: Path) -> Dict[str, Optional[str]]:
    """
    Resolve local JS/CSS assets (offline-first) based on your folder:
      C:\lib_ana\lib\vis-9.1.2\vis-network.min.js
      C:\lib_ana\lib\vis-9.1.2\vis-network.css
      C:\lib_ana\lib\tom-select\tom-select.complete.min.js
      C:\lib_ana\lib\tom-select\tom-select.css
    """
    lib_dir = root / "lib"
    vis_js = lib_dir / "vis-9.1.2" / "vis-network.min.js"
    vis_css = lib_dir / "vis-9.1.2" / "vis-network.css"
    tom_js = lib_dir / "tom-select" / "tom-select.complete.min.js"
    tom_css = lib_dir / "tom-select" / "tom-select.css"

    return {
        "vis_js": str(vis_js) if vis_js.exists() else None,
        "vis_css": str(vis_css) if vis_css.exists() else None,
        "tom_js": str(tom_js) if tom_js.exists() else None,
        "tom_css": str(tom_css) if tom_css.exists() else None,
    }


def _safe_json(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False)


def _parse_maybe_json_or_py(x: Any) -> Any:
    if x is None:
        return None
    if isinstance(x, (list, dict)):
        return x
    s = str(x).strip()
    if not s or s == "None" or s == "nan":
        return None
    # Try JSON then Python literal
    try:
        return json.loads(s)
    except Exception:
        pass
    try:
        return ast.literal_eval(s)
    except Exception:
        return s


def _coerce_param_names(row: Dict[str, Any]) -> List[str]:
    # v5: parameters is list[dict{name, annotation, default}]
    params = _parse_maybe_json_or_py(row.get("parameters"))
    if isinstance(params, list):
        out = []
        for p in params:
            if isinstance(p, dict) and p.get("name"):
                out.append(str(p["name"]))
        return out
    return []


def _build_nodes_edges_from_v5(df: pd.DataFrame) -> Tuple[pd.DataFrame, pd.DataFrame, Dict[str, Any]]:
    """
    Convert V5-style table (columns like qualname/object_kind/...) into V4-like node/edge tables
    so we can reuse the modern HTML renderer.

    Expected columns (subset is OK):
      - distribution, module, qualname, object_kind, is_public,
        signature_str, parameters, return_annotation,
        doc_summary, source_path, lineno
    """
    required = {"qualname", "object_kind", "module"}
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"V5 input missing columns: {missing}")

    records: List[Dict[str, Any]] = []
    edges: List[Dict[str, Any]] = []

    # Create module nodes (from module column)
    modules = sorted({str(x) for x in df["module"].dropna().tolist() if str(x).strip()})
    for mn in modules:
        records.append({
            "ID": mn,
            "Type": "module",
            "Name": mn.split(".")[-1],
            "Path": mn,
            "Parent": mn.rsplit(".", 1)[0] if "." in mn else "",
            "Module": mn,
            "OriginModule": mn,
            "OriginFile": "",
            "Line": "",
            "EndLine": "",
            "LOC": 0,
            "Signature": "",
            "DocSummary": "",
            "ParamNames": [],
            "ParamTypes": [],
            "ReturnType": "",
            "Events": ["other"],
            "Flags": {"module": mn, "analysis_mode": "v5_imported"},
        })
        if "." in mn:
            edges.append({"Src": mn.rsplit(".", 1)[0], "Dst": mn, "Rel": "contains", "Weight": 1.0})

    for _, r in df.iterrows():
        row = r.to_dict()
        qn = str(row.get("qualname", "")).strip()
        if not qn:
            continue
        kind = str(row.get("object_kind", "")).strip() or "other"
        module = str(row.get("module", "")).strip()

        parent = ""
        if "." in qn:
            parent = qn.rsplit(".", 1)[0]
        else:
            parent = module

        # normalize kind names (keep as-is but align to v4-style types)
        kmap = {
            "class": "class",
            "function": "function",
            "method": "method",
            "property": "property",
            "module": "module",
        }
        ntype = kmap.get(kind, kind)

        name = qn.split(".")[-1]
        sig = row.get("signature_str") or ""
        doc_summary = row.get("doc_summary") or (row.get("docstring") or "")
        doc_summary = str(doc_summary).replace("\n", " ").strip()
        events = classify_events(name, doc_summary)

        param_names = _coerce_param_names(row)
        return_type = str(row.get("return_annotation") or "").strip()

        origin_file = str(row.get("source_path") or "")
        origin_module = module

        records.append({
            "ID": qn,
            "Type": ntype,
            "Name": name,
            "Path": qn,
            "Parent": parent,
            "Module": module,
            "OriginModule": origin_module,
            "OriginFile": origin_file,
            "Line": row.get("lineno") or "",
            "EndLine": "",
            "LOC": 0,
            "Signature": str(sig) if sig is not None else "",
            "DocSummary": doc_summary[:800],
            "ParamNames": param_names,
            "ParamTypes": [],
            "ReturnType": return_type,
            "Events": events,
            "Flags": {
                "module": module,
                "distribution": row.get("distribution"),
                "is_public": bool(row.get("is_public")) if row.get("is_public") is not None else None,
                "analysis_mode": "v5_imported",
                "extraction_method": row.get("extraction_method"),
            },
        })

        # containment edges
        if module:
            # ensure module node exists (if missing in list due to NaN)
            if module not in {rec["ID"] for rec in records if rec.get("Type") == "module"}:
                records.append({
                    "ID": module,
                    "Type": "module",
                    "Name": module.split(".")[-1],
                    "Path": module,
                    "Parent": module.rsplit(".", 1)[0] if "." in module else "",
                    "Module": module,
                    "OriginModule": module,
                    "OriginFile": "",
                    "Line": "",
                    "EndLine": "",
                    "LOC": 0,
                    "Signature": "",
                    "DocSummary": "",
                    "ParamNames": [],
                    "ParamTypes": [],
                    "ReturnType": "",
                    "Events": ["other"],
                    "Flags": {"module": module, "analysis_mode": "v5_imported"},
                })
            # connect module->node if parent isn't already a class, etc.
            if parent == module:
                edges.append({"Src": module, "Dst": qn, "Rel": "contains", "Weight": 1.0})
            else:
                # parent could be class or module; create edge parent->child
                edges.append({"Src": parent, "Dst": qn, "Rel": "contains", "Weight": 1.0})

    # Dedupe nodes by ID (keep first)
    seen = set()
    uniq_records = []
    for rec in records:
        i = rec.get("ID")
        if not i or i in seen:
            continue
        seen.add(i)
        uniq_records.append(rec)

    df_nodes = pd.DataFrame(uniq_records)
    df_edges = pd.DataFrame(edges).drop_duplicates()

    summary = {
        "Name": "imported_table",
        "Modules": int((df_nodes["Type"] == "module").sum()) if not df_nodes.empty else 0,
        "Classes": int((df_nodes["Type"] == "class").sum()) if not df_nodes.empty else 0,
        "Functions": int((df_nodes["Type"] == "function").sum()) if not df_nodes.empty else 0,
        "Methods/Props": int(df_nodes["Type"].isin(["method", "property"]).sum()) if not df_nodes.empty else 0,
        "External": int((df_nodes["Type"] == "external").sum()) if not df_nodes.empty else 0,
        "UniqueParamNames": int(len({p for ps in df_nodes.get("ParamNames", []) if isinstance(ps, list) for p in ps})) if not df_nodes.empty else 0,
        "UniqueReturnTypes": int(len({str(x) for x in df_nodes.get("ReturnType", []).tolist() if str(x).strip()})) if not df_nodes.empty else 0,
        "Errors": 0,
        "ApiSurface": "imported",
    }
    return df_nodes, df_edges, summary


def _build_report_html(
    lib_name: str,
    summary: Dict[str, Any],
    nodes_records: List[Dict[str, Any]],
    edges_records: List[Dict[str, Any]],
    mmd: str,
    asset_hrefs: Dict[str, Optional[str]],
    out_html_path: Path,
    downloads: Dict[str, str],
    graph_max_nodes: int,
) -> str:
    # Convert absolute asset paths to href relative to report html
    resolved_assets: Dict[str, Optional[str]] = {}
    for k, p in asset_hrefs.items():
        if p is None:
            resolved_assets[k] = None
        else:
            resolved_assets[k] = _relpath(out_html_path, Path(p))

    nodes_json = _safe_json(nodes_records)
    edges_json = _safe_json(edges_records)
    mmd_json = _safe_json(mmd)

    dl_nodes_csv = downloads.get("nodes_csv", "")
    dl_nodes_json = downloads.get("nodes_json", "")
    dl_edges_json = downloads.get("edges_json", "")
    dl_mmd = downloads.get("mmd", "")
    dl_summary = downloads.get("summary_json", "")

    return f"""<!doctype html>
<html lang="ja">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>CLE Modern Explorer — {lib_name}</title>

  {'<link rel="stylesheet" href="'+resolved_assets["vis_css"]+'"/>' if resolved_assets.get("vis_css") else ''}
  {'<link rel="stylesheet" href="'+resolved_assets["tom_css"]+'"/>' if resolved_assets.get("tom_css") else ''}

  <style>
    :root {{
      --bg: #0b1220;
      --panel: rgba(255,255,255,0.06);
      --text: rgba(255,255,255,0.92);
      --muted: rgba(255,255,255,0.68);
      --border: rgba(255,255,255,0.14);
      --shadow: 0 12px 30px rgba(0,0,0,0.35);
      --r: 14px;
      --mono: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace;
      --sans: ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, Helvetica, Arial, "Apple Color Emoji","Segoe UI Emoji";
    }}
    body {{
      margin: 0; background: radial-gradient(1200px 800px at 20% 0%, #14203a, var(--bg));
      color: var(--text); font-family: var(--sans);
    }}
    .topbar {{
      position: sticky; top: 0; z-index: 10;
      display:flex; gap: 12px; align-items:center; justify-content:space-between;
      padding: 14px 16px; border-bottom: 1px solid var(--border);
      background: rgba(8, 12, 22, 0.72); backdrop-filter: blur(12px);
    }}
    .brand {{ display:flex; align-items:center; gap:10px; }}
    .logo {{
      width: 36px; height: 36px; border-radius: 12px;
      background: linear-gradient(135deg, #7c3aed, #06b6d4);
      box-shadow: 0 8px 24px rgba(124,58,237,0.25);
    }}
    .title {{ font-weight: 800; letter-spacing: .2px; }}
    .subtitle {{ color: var(--muted); font-size: 12px; margin-top: 2px; }}
    .right {{ display:flex; gap: 10px; align-items:center; flex-wrap: wrap; justify-content:flex-end; }}
    .chip {{
      display:inline-flex; align-items:center; gap: 8px;
      padding: 8px 10px; border-radius: 12px;
      border: 1px solid var(--border); background: rgba(255,255,255,0.05);
      font-size: 12px; color: var(--muted);
    }}
    .chip b {{ color: var(--text); font-weight: 700; }}
    .btn {{
      cursor:pointer; user-select:none;
      padding: 9px 12px; border-radius: 12px;
      border: 1px solid var(--border); background: rgba(255,255,255,0.07);
      color: var(--text); font-weight: 700; font-size: 12px;
      transition: transform .06s ease, background .12s ease;
    }}
    .btn:hover {{ background: rgba(255,255,255,0.12); }}
    .btn:active {{ transform: translateY(1px); }}

    .layout {{
      display: grid;
      grid-template-columns: 360px 1.6fr 1.2fr;
      gap: 12px;
      padding: 12px;
      min-height: calc(100vh - 68px);
    }}
    @media (max-width: 1200px) {{
      .layout {{ grid-template-columns: 1fr; }}
      .panel {{ min-height: 420px; }}
    }}
    .panel {{
      border: 1px solid var(--border);
      background: var(--panel);
      border-radius: var(--r);
      box-shadow: var(--shadow);
      overflow: hidden;
      display:flex; flex-direction:column;
      min-height: 520px;
    }}
    .panel-header {{
      padding: 12px 12px 10px 12px;
      border-bottom: 1px solid var(--border);
      background: rgba(255,255,255,0.04);
      display:flex; align-items:center; justify-content:space-between; gap: 12px;
    }}
    .panel-title {{ font-weight: 800; }}
    .panel-body {{ padding: 10px 12px; flex: 1; overflow:auto; }}
    .input {{
      width: 100%;
      padding: 10px 12px;
      border-radius: 12px;
      border: 1px solid var(--border);
      background: rgba(0,0,0,0.25);
      color: var(--text);
      outline: none;
    }}
    .row {{ display:flex; gap: 10px; align-items:center; }}
    .muted {{ color: var(--muted); }}
    .small {{ font-size: 12px; }}

    .list {{ display:flex; flex-direction:column; gap: 6px; }}
    .item {{
      border: 1px solid var(--border);
      background: rgba(255,255,255,0.04);
      border-radius: 12px;
      padding: 10px 10px;
      cursor:pointer;
      transition: background .12s ease, transform .06s ease;
    }}
    .item:hover {{ background: rgba(255,255,255,0.08); }}
    .item:active {{ transform: translateY(1px); }}
    .item .path {{ font-family: var(--mono); font-size: 12px; color: var(--text); }}
    .item .meta {{ color: var(--muted); font-size: 12px; margin-top: 4px; display:flex; gap: 10px; flex-wrap:wrap; }}
    .badge {{
      font-size: 11px; padding: 2px 8px; border-radius: 999px;
      border: 1px solid var(--border); background: rgba(0,0,0,0.22);
      color: var(--muted);
    }}
    pre {{
      margin: 8px 0 0 0;
      padding: 10px 12px;
      border-radius: 12px;
      border: 1px solid var(--border);
      background: rgba(0,0,0,0.35);
      overflow:auto;
      font-family: var(--mono);
      font-size: 12px;
      line-height: 1.45;
    }}
    .split {{ display:grid; grid-template-columns: 1fr 1fr; gap: 10px; }}
    @media (max-width: 1200px) {{ .split {{ grid-template-columns: 1fr; }} }}

    .tabs {{ display:flex; gap: 8px; align-items:center; }}
    .tab {{
      padding: 8px 10px; border-radius: 12px; border: 1px solid var(--border);
      background: rgba(255,255,255,0.04); cursor:pointer; font-weight: 800; font-size: 12px;
    }}
    .tab.active {{ background: rgba(255,255,255,0.10); }}

    #graph {{
      width: 100%;
      height: 100%;
      min-height: 520px;
      border-radius: 12px;
      border: 1px solid var(--border);
      background: rgba(0,0,0,0.22);
    }}
    .footer-note {{
      padding: 10px 12px;
      border-top: 1px solid var(--border);
      background: rgba(255,255,255,0.03);
      color: var(--muted);
      font-size: 12px;
    }}
    a {{ color: #8be9fd; text-decoration: none; }}
    a:hover {{ text-decoration: underline; }}
  </style>
</head>
<body>

  <div class="topbar">
    <div class="brand">
      <div class="logo"></div>
      <div>
        <div class="title">CLE Modern Explorer</div>
        <div class="subtitle">{lib_name} / offline report / graph max nodes={graph_max_nodes}</div>
      </div>
    </div>
    <div class="right">
      <a class="btn" href="{dl_nodes_csv}">Nodes CSV</a>
      <a class="btn" href="{dl_nodes_json}">Nodes JSON</a>
      <a class="btn" href="{dl_edges_json}">Edges JSON</a>
      <a class="btn" href="{dl_mmd}">Mermaid .mmd</a>
      <a class="btn" href="{dl_summary}">Summary JSON</a>
    </div>
  </div>

  <div class="layout">
    <div class="panel">
      <div class="panel-header">
        <div class="panel-title">検索 / フィルター</div>
        <div class="muted small">クリックで詳細</div>
      </div>
      <div class="panel-body">
        <div class="row">
          <input id="q" class="input" placeholder="Search (path / signature / doc) e.g. forecast, load, config" />
        </div>
        <div style="height: 10px;"></div>
        <div class="split">
          <div>
            <div class="muted small">Type</div>
            <select id="type" multiple></select>
          </div>
          <div>
            <div class="muted small">Event</div>
            <select id="event" multiple></select>
          </div>
        </div>
        <div style="height: 10px;"></div>
        <div class="split">
          <div>
            <div class="muted small">Arg name contains</div>
            <input id="arg" class="input" placeholder="e.g. path, df, horizon" />
          </div>
          <div>
            <div class="muted small">Return type contains</div>
            <input id="ret" class="input" placeholder="e.g. tuple, DataFrame" />
          </div>
        </div>

        <div style="height: 12px;"></div>
        <div class="row">
          <button id="apply" class="btn">Apply</button>
          <button id="reset" class="btn">Reset</button>
          <div class="chip"><b id="count">0</b> matches</div>
        </div>

        <div style="height: 12px;"></div>
        <div class="muted small">Results</div>
        <div id="list" class="list" style="margin-top: 8px;"></div>
      </div>
      <div class="footer-note">
        Tip: graph is limited to top nodes by (LOC + params*3). Use filters to narrow.
      </div>
    </div>

    <div class="panel">
      <div class="panel-header">
        <div class="panel-title">Graph</div>
        <div class="tabs">
          <div id="tabGraph" class="tab active">Network</div>
          <div id="tabMmd" class="tab">Mermaid</div>
        </div>
      </div>
      <div class="panel-body">
        <div id="graph"></div>
        <pre id="mmd" style="display:none;"></pre>
      </div>
      <div class="footer-note">
        Graph: click node → details. Drag to pan. Wheel to zoom.
      </div>
    </div>

    <div class="panel">
      <div class="panel-header">
        <div class="panel-title">Inspector</div>
        <div class="tabs">
          <div id="tabInfo" class="tab active">Info</div>
          <div id="tabCode" class="tab">CodeGen</div>
        </div>
      </div>
      <div class="panel-body">
        <div id="info"></div>
        <div id="code" style="display:none;"></div>
      </div>
      <div class="footer-note">
        Offline report: no network calls. Assets loaded from C:\lib_ana\lib\ if available.
      </div>
    </div>
  </div>

  <script id="data-nodes" type="application/json">{nodes_json}</script>
  <script id="data-edges" type="application/json">{edges_json}</script>
  <script id="data-mmd" type="application/json">{mmd_json}</script>

  {'<script src="'+resolved_assets["tom_js"]+'"></script>' if resolved_assets.get("tom_js") else ''}
  {'<script src="'+resolved_assets["vis_js"]+'"></script>' if resolved_assets.get("vis_js") else ''}

  <script>
    const nodes = JSON.parse(document.getElementById('data-nodes').textContent);
    const edges = JSON.parse(document.getElementById('data-edges').textContent);
    const mmd = JSON.parse(document.getElementById('data-mmd').textContent);
    const byId = new Map(nodes.map(n => [n.ID, n]));

    const escapeHtml = (s) => (s ?? '').toString()
      .replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;').replaceAll('"','&quot;');
    const norm = (s) => (s ?? '').toString().toLowerCase();
    const uniq = (arr) => Array.from(new Set(arr)).filter(Boolean).sort();

    function scoreNode(n) {{
      const loc = Number(n.LOC ?? 0);
      const pc = Array.isArray(n.ParamNames) ? n.ParamNames.length : 0;
      return loc + pc * 3;
    }}

    const qEl = document.getElementById('q');
    const typeEl = document.getElementById('type');
    const eventEl = document.getElementById('event');
    const argEl = document.getElementById('arg');
    const retEl = document.getElementById('ret');
    const listEl = document.getElementById('list');
    const countEl = document.getElementById('count');

    const typeOptions = uniq(nodes.map(n => n.Type));
    const eventOptions = uniq(nodes.flatMap(n => Array.isArray(n.Events) ? n.Events : []));

    function fillSelect(sel, items) {{
      sel.innerHTML = '';
      for (const it of items) {{
        const opt = document.createElement('option');
        opt.value = it;
        opt.textContent = it;
        sel.appendChild(opt);
      }}
    }}
    fillSelect(typeEl, typeOptions);
    fillSelect(eventEl, eventOptions);

    function enhanceMultiSelect(sel) {{
      if (window.TomSelect) {{
        // eslint-disable-next-line no-new
        new TomSelect(sel, {{ plugins: ['remove_button'], maxItems: null, create: false }});
      }}
    }}
    enhanceMultiSelect(typeEl);
    enhanceMultiSelect(eventEl);

    function currentMultiValues(selId) {{
      const sel = document.getElementById(selId);
      return Array.from(sel.selectedOptions).map(o => o.value);
    }}

    function matches(n) {{
      const q = norm(qEl.value);
      const types = currentMultiValues('type');
      const evs = currentMultiValues('event');
      const arg = norm(argEl.value);
      const ret = norm(retEl.value);

      if (types.length && !types.includes(n.Type)) return false;
      if (evs.length) {{
        const nodeEvs = Array.isArray(n.Events) ? n.Events : [];
        if (!evs.some(e => nodeEvs.includes(e))) return false;
      }}
      if (arg) {{
        const ps = Array.isArray(n.ParamNames) ? n.ParamNames.map(norm) : [];
        if (!ps.some(p => p.includes(arg))) return false;
      }}
      if (ret) {{
        if (!norm(n.ReturnType).includes(ret)) return false;
      }}
      if (q) {{
        const hay = [n.Path, n.Signature, n.DocSummary, n.OriginModule, n.OriginFile].map(norm).join(' | ');
        if (!hay.includes(q)) return false;
      }}
      return true;
    }}

    function buildResults() {{
      const filtered = nodes.filter(n => n.Type !== 'module').filter(matches);
      filtered.sort((a,b) => scoreNode(b) - scoreNode(a));
      return filtered.slice(0, 600);
    }}

    function renderList(items) {{
      listEl.innerHTML = '';
      countEl.textContent = items.length.toString();
      for (const n of items) {{
        const div = document.createElement('div');
        div.className = 'item';
        div.innerHTML = `
          <div class="path">${{escapeHtml(n.Path)}}</div>
          <div class="meta">
            <span class="badge">${{escapeHtml(n.Type)}}</span>
            <span class="muted">Params: ${{Array.isArray(n.ParamNames) ? n.ParamNames.length : 0}}</span>
            <span class="muted">${{escapeHtml(n.ReturnType ?? '')}}</span>
          </div>
        `;
        div.addEventListener('click', () => selectNode(n.ID));
        listEl.appendChild(div);
      }}
    }}

    const infoEl = document.getElementById('info');
    const codeEl = document.getElementById('code');

    function codegen(n) {{
      const top = (n.Path ?? '').split('.')[0] || '{lib}';
      const args = Array.isArray(n.ParamNames) ? n.ParamNames.filter(x => x && x !== 'self' && x !== 'cls') : [];
      const kv = args.slice(0, 12).map(a => `${{a}}=...`).join(', ');
      return [
        `# Generated by CLE Modern Explorer (offline)`,
        `import ${{top}}`,
        ``,
        `# Target: ${{n.Path}}`,
        `result = ${{n.Path}}(${{kv}})`,
        `print(result)`,
      ].join('\n');
    }}

    function renderInspector(n) {{
      const evs = Array.isArray(n.Events) ? n.Events : [];
      const params = Array.isArray(n.ParamNames) ? n.ParamNames : [];
      const sig = n.Signature ? `${{n.Name}}${{n.Signature}}` : '';
      const doc = n.DocSummary ?? '';
      const file = n.OriginFile ?? '';
      const mod = n.OriginModule ?? '';

      const badges = [
        `<span class="badge">${{escapeHtml(n.Type)}}</span>`,
        evs.map(e => `<span class="badge">${{escapeHtml(e)}}</span>`).join(' '),
      ].join(' ');

      infoEl.innerHTML = `
        <div class="muted small">Path</div>
        <pre>${{escapeHtml(n.Path)}}</pre>

        ${{badges ? `<div style="display:flex; gap:6px; flex-wrap:wrap; margin-top: 8px;">${{badges}}</div>` : ''}}
        ${{sig ? `<div style="margin-top: 10px;" class="muted small">Signature</div><pre>${{escapeHtml(sig)}}</pre>` : ''}}
        ${{params.length ? `<div style="margin-top: 10px;" class="muted small">Params</div><pre>${{escapeHtml(params.join(', '))}}</pre>` : ''}}
        ${{n.ReturnType ? `<div style="margin-top: 10px;" class="muted small">Return</div><pre>${{escapeHtml(n.ReturnType)}}</pre>` : ''}}
        ${{doc ? `<div style="margin-top: 10px;" class="muted small">Doc</div><pre>${{escapeHtml(doc)}}</pre>` : ''}}
        ${{(mod || file) ? `<div style="margin-top: 10px;" class="muted small">Origin</div><pre>${{escapeHtml(mod)}}\n${{escapeHtml(file)}}</pre>` : ''}}
      `;

      const cg = codegen(n);
      codeEl.innerHTML = `
        <div class="row">
          <button class="btn" id="copy">Copy</button>
          <span class="muted small">Paste and fill args.</span>
        </div>
        <pre id="cg">${{escapeHtml(cg)}}</pre>
      `;
      document.getElementById('copy').addEventListener('click', async () => {{
        try {{
          await navigator.clipboard.writeText(cg);
          alert('Copied!');
        }} catch (e) {{
          alert('Copy failed (browser permissions).');
        }}
      }});
    }}

    let network = null;

    function buildGraphData(items) {{
      const scored = items.slice().sort((a,b) => scoreNode(b) - scoreNode(a));
      const keep = scored.slice(0, {graph_max_nodes});
      const keepIds = new Set(keep.map(n => n.ID));

      const visNodes = keep.map(n => ({{ id: n.ID, label: n.Name, title: escapeHtml(n.Path), value: Math.max(1, Number(n.LOC ?? 1)), group: n.Type }}));
      const visEdges = edges
        .filter(e => keepIds.has(e.Src) && keepIds.has(e.Dst))
        .map(e => ({{ from: e.Src, to: e.Dst, arrows: 'to' }}));

      return {{ visNodes, visEdges }};
    }}

    function renderGraph(items) {{
      const graphEl = document.getElementById('graph');
      if (!window.vis) {{
        graphEl.innerHTML = '<div style="padding:12px;color:rgba(255,255,255,0.75)">vis-network が見つかりません。C:\\lib_ana\\lib\\vis-9.1.2 を確認してください。</div>';
        return;
      }}
      const {{ visNodes, visEdges }} = buildGraphData(items);
      const data = {{ nodes: new vis.DataSet(visNodes), edges: new vis.DataSet(visEdges) }};
      const options = {{
        nodes: {{ shape: 'dot', font: {{ color: 'rgba(255,255,255,0.92)' }} }},
        edges: {{ color: {{ color: 'rgba(255,255,255,0.25)' }}, smooth: {{ type: 'dynamic' }} }},
        physics: {{ stabilization: {{ iterations: 180 }} }},
        interaction: {{ hover: true, multiselect: false }}
      }};

      network = new vis.Network(graphEl, data, options);
      network.on('click', (params) => {{
        const id = params.nodes && params.nodes[0];
        if (id) selectNode(id);
      }});
    }}

    function selectNode(id) {{
      const n = byId.get(id);
      if (!n) return;
      renderInspector(n);
      if (network) {{
        network.selectNodes([id]);
        network.focus(id, {{ scale: 1.2, animation: {{ duration: 250 }} }});
      }}
    }}

    const tabInfo = document.getElementById('tabInfo');
    const tabCode = document.getElementById('tabCode');
    const tabGraph = document.getElementById('tabGraph');
    const tabMmd = document.getElementById('tabMmd');
    const mmdEl = document.getElementById('mmd');

    function activateTabs(a, b, showA, showB) {{
      a.classList.add('active'); b.classList.remove('active');
      showA.style.display = '';
      showB.style.display = 'none';
    }}
    tabInfo.addEventListener('click', () => activateTabs(tabInfo, tabCode, infoEl, codeEl));
    tabCode.addEventListener('click', () => activateTabs(tabCode, tabInfo, codeEl, infoEl));
    tabGraph.addEventListener('click', () => {{
      tabGraph.classList.add('active'); tabMmd.classList.remove('active');
      document.getElementById('graph').style.display = '';
      mmdEl.style.display = 'none';
    }});
    tabMmd.addEventListener('click', () => {{
      tabMmd.classList.add('active'); tabGraph.classList.remove('active');
      document.getElementById('graph').style.display = 'none';
      mmdEl.style.display = '';
    }});

    function apply() {{
      const items = buildResults();
      renderList(items);
      renderGraph(items);
      mmdEl.textContent = mmd;
      if (items.length) selectNode(items[0].ID);
    }}

    document.getElementById('apply').addEventListener('click', apply);
    document.getElementById('reset').addEventListener('click', () => {{
      qEl.value = ''; argEl.value = ''; retEl.value = '';
      for (const o of typeEl.options) o.selected = false;
      for (const o of eventEl.options) o.selected = false;
      apply();
    }});

    apply();
  </script>
</body>
</html>
"""


def generate_modern_report(
    lib_name: str,
    cfg: Optional["AnalysisConfig"],
    project_root: Optional[Path] = None,
    graph_max_nodes: int = 260,
    input_path: Optional[str] = None,
) -> Path:
    root = project_root or _project_root_from_this_file()
    dirs = _ensure_dirs(root)

    log_path = dirs["logs"] / f"ui_modern_{lib_name}_{_ts()}.log"

    def log(msg: str) -> None:
        with log_path.open("a", encoding="utf-8") as f:
            f.write(msg + "\n")

    log(f"[start] lib={lib_name} input={input_path or '-'}")

    if input_path:
        p = Path(input_path)
        if not p.exists():
            raise FileNotFoundError(p)
        if p.suffix.lower() in [".csv"]:
            df = pd.read_csv(p)
        else:
            df = pd.read_json(p)
        # Detect schema
        if "qualname" in df.columns and "object_kind" in df.columns:
            df_nodes, df_edges, summary = _build_nodes_edges_from_v5(df)
            mmd = "flowchart TD\n  %% Mermaid export is best-effort for imported table\n"
        else:
            # assume already V4-like
            df_nodes = df.copy()
            df_edges = pd.DataFrame([], columns=["Src", "Dst", "Rel", "Weight"])
            summary = {"Name": lib_name, "ApiSurface": "imported", "Errors": 0}
            mmd = "flowchart TD\n  %% Mermaid export unavailable\n"
    else:
        if not _HAS_V4:
            raise RuntimeError("No --input provided and V4 analyzer modules not available in src/. Please use --input.")
        assert cfg is not None
        analyzer = LibraryAnalyzerV4(lib_name, cfg)
        summary, df_nodes, df_edges, _ = analyzer.analyze()
        if analyzer.errors:
            log("[errors] " + " | ".join(analyzer.errors[:20]))
        mmd = to_mermaid_flowchart(df_nodes, df_edges, lib_name, max_nodes=max(200, graph_max_nodes))

    api_tables = dirs["api_tables"]
    reports = dirs["reports"]

    nodes_csv = api_tables / f"{lib_name}_nodes.csv"
    nodes_json = api_tables / f"{lib_name}_nodes.json"
    edges_json = api_tables / f"{lib_name}_edges.json"
    summary_json = api_tables / f"{lib_name}_summary.json"
    mmd_path = api_tables / f"{lib_name}.mmd"

    df_nodes.to_csv(nodes_csv, index=False, encoding="utf-8-sig")
    df_nodes.to_json(nodes_json, orient="records", force_ascii=False)
    df_edges.to_json(edges_json, orient="records", force_ascii=False)
    with summary_json.open("w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    mmd_path.write_text(mmd, encoding="utf-8")

    out_html = reports / f"{lib_name}_explorer.html"
    assets = _load_local_lib_paths(root)
    downloads = {
        "nodes_csv": _relpath(out_html, nodes_csv),
        "nodes_json": _relpath(out_html, nodes_json),
        "edges_json": _relpath(out_html, edges_json),
        "summary_json": _relpath(out_html, summary_json),
        "mmd": _relpath(out_html, mmd_path),
    }

    nodes_records = json.loads(df_nodes.to_json(orient="records", force_ascii=False))
    edges_records = json.loads(df_edges.to_json(orient="records", force_ascii=False))

    html_text = _build_report_html(
        lib_name=lib_name,
        summary=summary,
        nodes_records=nodes_records,
        edges_records=edges_records,
        mmd=mmd,
        asset_hrefs=assets,
        out_html_path=out_html,
        downloads=downloads,
        graph_max_nodes=graph_max_nodes,
    )
    out_html.write_text(html_text, encoding="utf-8")
    log(f"[ok] report={out_html}")
    return out_html


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="CLE Modern Explorer (offline HTML report generator)")
    p.add_argument("--lib", default="library", help="label used for output file names")
    p.add_argument("--input", default="", help="CSV/JSON path of analysis results (recommended for V5)")
    # V4-only options
    p.add_argument("--api-surface", default="module_public", choices=["module_public", "top_level"])
    p.add_argument("--include-private", action="store_true")
    p.add_argument("--include-external", action="store_true")
    p.add_argument("--include-inherited", action="store_true")
    p.add_argument("--no-related", action="store_true")
    p.add_argument("--max-modules", type=int, default=5000)
    p.add_argument("--max-depth", type=int, default=30)
    p.add_argument("--graph-max-nodes", type=int, default=260)
    return p.parse_args()


def main() -> None:
    args = _parse_args()
    cfg = None
    if not args.input:
        if not _HAS_V4:
            raise RuntimeError("When --input is empty, analyzer_v4/models_v4 must exist in src/.")
        cfg = AnalysisConfig(
            api_surface=args.api_surface,
            include_private=args.include_private,
            include_external_reexports=args.include_external,
            include_inherited_members=args.include_inherited,
            add_related_edges=not args.no_related,
            max_modules=args.max_modules,
            max_depth=args.max_depth,
        )

    report = generate_modern_report(
        lib_name=args.lib,
        cfg=cfg,
        graph_max_nodes=args.graph_max_nodes,
        input_path=args.input or None,
    )
    print("OK:", report)
    print("Open in browser:", report.as_uri())


if __name__ == "__main__":
    main()
