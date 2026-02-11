# TimesFM 解析バンドル（オフライン閲覧 + 再抽出）

このフォルダは、アップロード済みの **CLE V6 レポート**と可視化画像を「そのまま閲覧」できるようにしつつ、  
HTMLから **機能一覧（modules/classes/functions/methods）をCSVとして再抽出**できるようにまとめたものです。

## すぐ見る（最短）
- ブラウザで開く: `/mnt/data/timesfm_bundle/site/index.html`
- フルレポート: `/mnt/data/timesfm_bundle/site/cle_report.html`
- Mermaid 図: `/mnt/data/timesfm_bundle/site/mermaid/graph_preview.html`（※CDN利用）

## 抽出データ
`/mnt/data/timesfm_bundle/extracted` にCSV/JSONが入っています。
- `tables_modules.csv`
- `tables_classes.csv`
- `tables_functions.csv`
- `tables_methods.csv`
- `tables_external.csv`
- `nodes.csv` / `edges.csv`
- `summary.json`

## 再抽出（レポートを差し替えた時など）
```bash
python /mnt/data/timesfm_bundle/scripts/extract_from_report.py
```

## TimesFM 実データ疎通（テンプレ）
`/mnt/data/timesfm_bundle/notebooks/timesfm_smoketest_template.ipynb` は、
あなたのDB（PostgreSQL）上の `dataset.loto_y_ts / dataset.loto_hist_feat` を使う想定の **スモークテスト用テンプレ**です。


## 依存（このバンドル自体の再抽出）
```bash
pip install -r requirements.txt
```

## 依存（TimesFM実行）
このバンドルは **TimesFMそのものは同梱しません**（あなたの環境でインストールしてある前提）。
例:
```bash
pip install timesfm
```
