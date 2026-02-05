# Cognitive Library Explorer V6 (Streamlit)

## 実行手順（Windows）
```powershell
cd C:\lib_ana
python -m pip install -r .\cle_v6_streamlit_src\requirements_v6.txt
streamlit run C:\lib_ana\src\v6\streamlit_app.py
```

## 依存関係
- 既存の解析器（analyzer_v4.py / models_v4.py / package_catalog_v4.py）が `C:\lib_ana\src\` 直下にある前提。
- v5 の codegen/mermaid/value-candidate 生成がある場合は自動で利用（無い場合も最低限動作）。
