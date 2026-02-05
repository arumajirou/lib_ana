# ファイルパス: C:\lib_ana\src\v6\core\link_resolver_v6.py
from __future__ import annotations
from typing import Dict, List

PYPI_JSON = "https://pypi.org/pypi/{name}/json"

def lookup_pypi_urls(package_name: str, timeout_sec: float = 6.0) -> Dict[str, str]:
    try:
        import requests  # type: ignore
    except Exception:
        return {}
    url = PYPI_JSON.format(name=package_name)
    try:
        r = requests.get(url, timeout=timeout_sec, headers={"User-Agent": "CLE-V6/1.0"})
        if r.status_code != 200:
            return {}
        data = r.json()
    except Exception:
        return {}
    info = data.get("info", {}) or {}
    proj_urls = info.get("project_urls", {}) or {}
    out: Dict[str, str] = {}
    home = info.get("home_page")
    if isinstance(home, str) and home.startswith("http"):
        out["HomePage"] = home
    for k, v in proj_urls.items():
        if isinstance(v, str) and v.startswith("http"):
            out[str(k)] = v
    out["PyPI"] = f"https://pypi.org/project/{package_name}/"
    return out

def extract_github_urls(urls: Dict[str, str]) -> List[str]:
    return sorted({v for v in urls.values() if "github.com" in (v or "").lower()})

def guess_huggingface_search_url(package_name: str) -> str:
    return f"https://huggingface.co/search/full-text?q={package_name}"

def guess_github_search_url(package_name: str) -> str:
    return f"https://github.com/search?q={package_name}&type=repositories"
