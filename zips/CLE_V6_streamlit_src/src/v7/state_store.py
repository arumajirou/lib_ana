# ファイルパス: C:\lib_ana\src\v6\state_store.py
from __future__ import annotations

import json
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Dict, List, Optional

DEFAULT_STATE_PATH = Path(r"C:\lib_ana\configs\cle_v6_state.json")

@dataclass
class PersistedState:
    # 直近の選択（5列/6列ナビの“現在地”）
    last_library: Optional[str] = None
    last_group: Optional[str] = None
    last_module: Optional[str] = None
    last_item: Optional[str] = None
    last_member: Optional[str] = None
    last_param: Optional[str] = None

    # 履歴（label と node_id の対応）
    history_labels: List[str] = None
    history_node_ids: List[str] = None

    # UI フラグ
    open_links_new_tab: bool = True
    color_tables: bool = False
    module_group_depth: int = 2
    max_list_items: int = 500

    def __post_init__(self) -> None:
        if self.history_labels is None:
            self.history_labels = []
        if self.history_node_ids is None:
            self.history_node_ids = []

def load_state(path: Path = DEFAULT_STATE_PATH) -> PersistedState:
    try:
        if path.exists():
            data = json.loads(path.read_text(encoding="utf-8"))
            return PersistedState(**data)
    except Exception:
        # 破損していても落ちない
        pass
    return PersistedState()

def save_state(state: PersistedState, path: Path = DEFAULT_STATE_PATH) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(asdict(state), ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        # 書き込み失敗でも落ちない
        pass

def push_history(state: PersistedState, label: str, node_id: str, limit: int = 200) -> PersistedState:
    # 先頭に入れて重複は除去
    pairs = [(label, node_id)] + [
        (l, n) for (l, n) in zip(state.history_labels, state.history_node_ids)
        if not (l == label and n == node_id)
    ]
    pairs = pairs[:limit]
    state.history_labels = [p[0] for p in pairs]
    state.history_node_ids = [p[1] for p in pairs]
    return state
