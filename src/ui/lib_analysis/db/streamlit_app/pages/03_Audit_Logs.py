from __future__ import annotations

import json
import sys
from pathlib import Path

import streamlit as st

APP_DIR = Path(__file__).resolve().parents[1]  # .../streamlit_app
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from bootstrap import ensure_import_path
ensure_import_path()

APP_ROOT = Path(__file__).resolve().parents[2]
LOG_DIR = APP_ROOT / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)

st.set_page_config(page_title="Audit Logs", layout="wide")
st.title("Audit Logs")
st.caption("操作ログ（JSONL）を閲覧します。")

logs = sorted(LOG_DIR.glob("db_admin_*.jsonl"), reverse=True)
if not logs:
    st.info(f"ログがありません: {LOG_DIR}")
    st.stop()

log_path = st.selectbox("ログファイル", [str(p) for p in logs], index=0)
limit = st.slider("表示件数", 50, 5000, 300, 50)

status_filter = st.multiselect("status フィルタ", ["ok", "ng"], default=["ok", "ng"])
action_q = st.text_input("action 部分一致（任意）", "")
target_q = st.text_input("target 部分一致（任意）", "")

rows = []
with open(log_path, "r", encoding="utf-8") as f:
    for line in f:
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except Exception:
            continue

rows = rows[-limit:]

def _ok(r):
    if r.get("status") not in status_filter:
        return False
    if action_q and action_q not in str(r.get("action", "")):
        return False
    if target_q and target_q not in str(r.get("target", "")):
        return False
    return True

rows = [r for r in rows if _ok(r)]
st.write(f"表示件数: {len(rows)}")

try:
    import pandas as pd  # type: ignore
    df = pd.DataFrame(rows)
    prefer = ["ts", "status", "action", "target", "profile", "elapsed_ms", "error"]
    cols = [c for c in prefer if c in df.columns] + [c for c in df.columns if c not in prefer]
    st.dataframe(df[cols], use_container_width=True)
except Exception:
    st.json(rows)

if st.checkbox("各レコードのSQLを表示（最大50件）", value=False):
    for r in rows[-50:]:
        st.markdown(f"**{r.get('ts')}** | {r.get('status')} | {r.get('action')} | {r.get('target')}")
        st.code(r.get("sql", ""), language="sql")
