# Cognitive Library Explorer (CLE) — Minimal Working Skeleton

This is a working starter implementation based on the design:
- pip list inventory
- V5 analyzer (runtime inspect) — **opt-in**
- ipywidgets Explorer UI + Inspector (signature/params/value candidates)
- CodeGen (with tiny sample data prelude)
- Mermaid HTML export

## Quickstart (Jupyter)

1. Open `lib.ipynb`
2. Run cells top-to-bottom
3. Set `distribution='pandas'` (or any installed library)
4. Set `enable_runtime=True` to run runtime inspection

Safety: runtime analyzer imports the package. Keep it OFF for strict static-only mode.

## Windows path compatibility

To use the design path, set:
- `LIB_ANA_ROOT=C:\lib_ana`
