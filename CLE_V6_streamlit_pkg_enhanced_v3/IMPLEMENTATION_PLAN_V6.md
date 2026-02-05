# CLE V6 改修実装計画書（Explorer拡張）

対象: `src/v6/streamlit_app/app.py` / `src/v6/streamlit_app/ui_explorer_v6.py` / `src/v6/core/*`

目的: **ライブラリ構造・関係性・処理フローを「探索 → コード化 → 可視化」できるUI**へ拡張する。

---

## 1. 背景と現状課題
- V6 UI は「モジュール→class/function→member」まで探索できるが、
  - 階層が浅く推定されることがあり（例: `timesfm`）、**段階的（カスケード）に深掘りしづらい**
  - 選択スコープ直下の **分類別一覧（Modules / Classes / Functions / Methods/Props / External / Errors）** が一括で見えない
  - 関係性（依存/呼び出し）を **Mermaid(mmd) や可視化（Sunburst/Network/Sequence）** として外部に出せない
  - 選択した関数を「引数全部入り」で呼び出す**テンプレコード生成**が無い
  - 表示形式（タブ/縦1枚）の切替が無い

---

## 2. ゴール（要件）
### 2.1 UI/UX
1. **カスケード階層**: `timesfm → timesfm.flax → timesfm.flax.dense ...` のように段階的に深掘りできる
2. **選択スコープ直下の一覧表**: 選択したモジュールの下に、以下を展開表示
   - Modules / Classes / Functions / Methods/Props / External / UniqueParamNames / UniqueReturnTypes / Errors
3. **可視化タブ**
   - Mermaid(flowchart) を mmd として出力 + 画面内レンダリング
   - Mermaid(sequenceDiagram) を出力 + 画面内レンダリング
   - Sunburst（階層俯瞰）
   - Network（依存/呼び出し）
4. **Codegen**: 選択 Function/Class/Method について、`inspect.signature` 由来の Params を使い
   - 引数「全部入り」の呼び出しテンプレを生成し、ダウンロード可能にする
5. **表示切替**: タブ表示 / シングルページ表示の切替
6. **複数ライブラリ比較（Atlas）**: 複数ライブラリをまとめて走査し、メトリクス比較と共通引数傾向を可視化

### 2.2 データ/設計
- 既存の `analysis = {nodes, edges, errors, tables, param_tables}` を中心に拡張
- edges 列名の揺れ（Source/Target, From/To ...）を吸収して可視化側で推定
- 大規模グラフで UI が死なないよう **max_nodes / max_edges** を設ける

---

## 3. アーキテクチャ（基本設計）
### 3.1 新規/改修モジュール
- `src/v6/core/mermaid_v6.py`
  - Mermaid(flowchart / sequenceDiagram) の生成
- `src/v6/core/viz_v6.py`
  - Sunburst 用データ生成、UniqueParam/ReturnType 集計、エラー絞り込み
  - Network 用の scoped graph 生成（networkx を lazy import）
- `src/v6/core/codegen_v6.py`
  - 選択ノードの呼び出しテンプレを生成
- `src/v6/core/hierarchy_v6.py`
  - `auto_depth` を「条件を満たす範囲でできるだけ深く」に変更 + `min_depth` 導入
- `src/v6/core/analyzer_service_v6.py`
  - analyzer 出力の DataFrame 変換を安全化（dictスカラー等で落ちない）
  - v4/v5 互換のため `sys.path` を補助（`models_v4` などトップレベル import を吸収）

### 3.2 UI（画面設計）
- `src/v6/streamlit_app/ui_explorer_v6.py`
  - Navigator: カスケード + Inspector + 一覧表 + Codegen
  - Visualize: Mermaid / Sunburst / Network / Sequence
  - Summary / Param Reverse / Tables / Links
  - Atlas: 複数ライブラリ比較（軽量版）

---

## 4. 実装ステップ（段階的）
### Sprint 1（最優先: 体験が変わる）
1. `hierarchy_v6.auto_depth` 改修（min_depth, 深い方優先）
2. Navigator にカスケード UI を実装
3. 選択スコープ直下の一覧表（8カテゴリ）を実装
4. Codegen（呼び出しテンプレ生成 + download_button）

### Sprint 2（可視化の核）
5. Mermaid(flowchart) 出力 + 画面内レンダリング
6. Mermaid(sequenceDiagram) 出力 + 画面内レンダリング
7. Sunburst（Plotly）
8. Network（networkx + Plotly）

### Sprint 3（全体探索・比較）
9. Atlas（複数ライブラリ）
   - メトリクス比較表
   - 共有されやすい ParamName の可視化

---

## 5. テスト観点（最低限）
- `timesfm` のような小〜中規模ライブラリで
  - `timesfm → flax → dense` のように深掘りできる
  - スコープ一覧表が空/過多で崩れない（max_items で制限）
  - Mermaid が文字化け/レンダリング失敗しない（特殊文字を最小限エスケープ）
  - edges 列名が違っても推定できる
- analyzer 出力が以下でも落ちない
  - `errors` が dict スカラー / 文字列
  - `nodes/edges` が list[dict] / dict / DataFrame

---

## 6. リスクと対策
- **巨大ライブラリで重い** → max_nodes/max_edges/max_items を UI で制御、cache_data を活用
- **edges の意味が曖昧** → 可視化は「作業仮説」として提示（関係推定の限界をUI上で明示）
- **Mermaid の仕様差/描画崩れ** → flowchart/sequence のみをまず確実に

---

## 7. 受け入れ基準（Done定義）
- Navigator でカスケード選択ができ、選択スコープ直下に 8カテゴリ一覧表が出る
- Visualize で Mermaid/Sunburst/Network/Sequence が表示・DLできる
- 選択関数の call stub を生成・DLできる
- タブ/シングルページ切替ができる
