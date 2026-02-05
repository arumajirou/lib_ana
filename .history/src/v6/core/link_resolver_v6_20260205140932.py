# C:\lib_ana\src\v6\core\link_resolver_v6.py
from __future__ import annotations

from typing import Dict, List, Optional
import re
import requests


PYPI_JSON = "https://pypi.org/pypi/{name}/json"


def lookup_pypi_urls(package_name: str, timeout_sec: float = 5.0) -> Dict[str, str]:
    """
    PyPI JSON API から Project URLs を回収（公式）。:contentReference[oaicite:5]{index=5}
    """
    url = PYPI_JSON.format(name=package_name)
    r = requests.get(url, timeout=timeout_sec)
    if r.status_code != 200:
        return {}
    data = r.json()
    info = data.get("info", {}) or {}
    proj_urls = info.get("project_urls", {}) or {}
    out = {}
    # homepage は古いフィールドの場合もある
    if info.get("home_page"):
        out["HomePage"] = info["home_page"]
    for k, v in proj_urls.items():
        if isinstance(v, str) and v.startswith("http"):
            out[str(k)] = v
    # PyPI 自身
    out["PyPI"] = f"https://pypi.org/project/{package_name}/"
    return out


def extract_github_urls(urls: Dict[str, str]) -> List[str]:
    gh = []
    for v in urls.values():
        if "github.com" in v.lower():
            gh.append(v)
    # 重複排除
    return sorted(set(gh))


def guess_huggingface_search_url(package_name: str) -> str:
    # HFは検索ページを提示（APIでの検索は huggingface_hub でも可能。:contentReference[oaicite:6]{index=6}）
    return f"https://huggingface.co/search/full-text?q={package_name}"


def guess_github_search_url(package_name: str) -> str:
    return f"https://github.com/search?q={package_name}&type=repositories"
