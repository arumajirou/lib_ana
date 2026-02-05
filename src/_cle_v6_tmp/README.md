# CLE V6 Streamlit Package

## Windows 実行
```powershell
cd C:\lib_ana
python -m pip install -r .\cle_v6_pkg\requirements_v6.txt
cd C:\lib_ana\src
streamlit run v6\streamlit_app\app.py
```

## 重要
- app.py 冒頭で `C:\lib_ana\src` を `sys.path` に追加するため、どの作業ディレクトリから起動しても `import v6...` が通ります。
- 既存の `analyzer_v4.py / analyzer_v5.py / package_catalog_v4.py` が `C:\lib_ana\src` 直下にある前提です。
