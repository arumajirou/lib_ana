# ファイルパス: C:\lib_ana\src\v6\link_resolver.py
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional
import requests

@dataclass(frozen=True)
class LinkHit:
    site: str
    title: str
    url: str
    confidence: float  # 0..1

def _safe_get_json(url: str, timeout: float = 8.0) -> Optional[dict]:
    try:
        r = requests.get(url, timeout=timeout, headers={"User-Agent": "CLE-V6/1.0"})
        if r.status_code == 200:
            return r.json()
    except Exception:
        return None
    return None

def resolve_pypi(dist_name: str) -> List[LinkHit]:
    # PyPI JSON API
    hits: List[LinkHit] = []
    if not dist_name:
        return hits
    data = _safe_get_json(f"https://pypi.org/pypi/{dist_name}/json")
    if not data:
        return hits
    info = data.get("info", {}) or {}
    project_url = info.get("project_url") or f"https://pypi.org/project/{dist_name}/"
    hits.append(LinkHit("PyPI", info.get("name", dist_name), project_url, 0.95))
    home = info.get("home_page")
    if home:
        hits.append(LinkHit("Homepage", "home_page", home, 0.6))
    proj_urls = info.get("project_urls") or {}
    for k, v in proj_urls.items():
        if isinstance(v, str) and v.startswith("http"):
            hits.append(LinkHit("ProjectURLs", str(k), v, 0.7))
    return hits

def resolve_github_from_pypi(hits: List[LinkHit]) -> List[LinkHit]:
    out = list(hits)
    for h in hits:
        if "github.com" in (h.url or "").lower():
            out.append(LinkHit("GitHub", h.title, h.url, max(0.8, h.confidence)))
    return _dedup(out)

def search_github(repo_query: str, max_hits: int = 5) -> List[LinkHit]:
    # GitHub Search API (unauth / rate-limited)
    if not repo_query:
        return []
    url = "https://api.github.com/search/repositories"
    try:
        r = requests.get(url, params={"q": repo_query, "per_page": max_hits},
                         timeout=8.0, headers={"User-Agent": "CLE-V6/1.0"})
        if r.status_code != 200:
            return []
        data = r.json()
        items = data.get("items") or []
        hits = []
        for it in items:
            hits.append(LinkHit("GitHub", it.get("full_name","repo"), it.get("html_url",""), 0.55))
        return _dedup(hits)
    except Exception:
        return []

def search_huggingface(query: str, max_hits: int = 5) -> List[LinkHit]:
    # Hugging Face Hub search
    if not query:
        return []
    url = "https://huggingface.co/api/models"
    try:
        r = requests.get(url, params={"search": query, "limit": max_hits},
                         timeout=8.0, headers={"User-Agent": "CLE-V6/1.0"})
        if r.status_code != 200:
            return []
        data = r.json()
        hits = []
        for it in data[:max_hits]:
            mid = it.get("modelId") or it.get("id") or "model"
            hits.append(LinkHit("HuggingFace", mid, f"https://huggingface.co/{mid}", 0.45))
        return _dedup(hits)
    except Exception:
        return []

def _dedup(hits: List[LinkHit]) -> List[LinkHit]:
    seen = set()
    out = []
    for h in hits:
        key = (h.site, h.url)
        if key in seen:
            continue
        seen.add(key)
        out.append(h)
    return out
