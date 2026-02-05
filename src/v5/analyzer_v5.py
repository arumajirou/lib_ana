from __future__ import annotations

from analyzer_v4 import LibraryAnalyzerV4
from models_v4 import AnalysisConfig


class LibraryAnalyzerV5(LibraryAnalyzerV4):
    """V5 向けの薄いラッパー.

    現時点では `LibraryAnalyzerV4` と同等の挙動ですが、
    将来の V5 専用拡張のためのフックとして分離してあります。
    """

    def __init__(self, lib_name: str, cfg: AnalysisConfig | None = None) -> None:
        super().__init__(lib_name, cfg or AnalysisConfig())
