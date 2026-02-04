# ファイルパス: C:\lib_ana\src\analyzer_v2.py
import inspect
import importlib
import pkgutil
import pandas as pd
import ast
import os


class DeepLibraryAnalyzer:
    """
    inspectモジュールとAST(抽象構文木)解析を組み合わせた
    深層ライブラリ分析クラス。
    """

    def __init__(self, lib_name):
        self.lib_name = lib_name
        self.target_lib = None
        try:
            self.target_lib = importlib.import_module(lib_name)
        except ImportError as e:
            print(
                f"Warning: Failed to import {lib_name}. Analysis might be limited. {e}"
            )

    def get_library_summary(self):
        """ライブラリ全体の健康診断（統計情報）を取得"""
        if not self.target_lib:
            return {}, pd.DataFrame()

        # 構造スキャン実行
        df = self.scan_structure(max_depth=5)

        summary = {
            "Name": self.lib_name,
            "Version": getattr(self.target_lib, "__version__", "unknown"),
            "File": getattr(self.target_lib, "__file__", "built-in"),
            "Doc": (
                inspect.getdoc(self.target_lib) or "No description available."
            ).split("\n")[0],
            "Modules": df[df["Type"] == "module"].shape[0] if not df.empty else 0,
            "Classes": df[df["Type"] == "class"].shape[0] if not df.empty else 0,
            "Functions": (
                df[df["Type"].isin(["function", "method"])].shape[0]
                if not df.empty
                else 0
            ),
        }

        return summary, df

    def scan_structure(self, max_depth=3):
        """再帰的探索により構造を解析しDataFrame化"""
        data = []
        # スタック: (object, depth, path_list)
        stack = [(self.target_lib, 0, [self.lib_name])]
        visited = set()

        while stack:
            obj, depth, path = stack.pop()

            # 循環参照防止と深さ制限
            obj_id = id(obj)
            if depth > max_depth or obj_id in visited:
                continue
            visited.add(obj_id)

            try:
                # ソースコード行数(LOC)の概算
                loc = 0
                try:
                    source = inspect.getsource(obj)
                    loc = len(source.split("\n"))
                except:
                    pass

                # Docstringの要約
                raw_doc = inspect.getdoc(obj) or ""
                doc_summary = raw_doc.split("\n\n")[0].replace("\n", " ")[:100]

                # オブジェクト種別の判定
                kind = "unknown"

                # 1. Module
                if inspect.ismodule(obj):
                    kind = "module"
                    if hasattr(obj, "__path__"):
                        for _, name, _ in pkgutil.iter_modules(
                            obj.__path__, prefix=f"{obj.__name__}."
                        ):
                            # ライブラリ内部のみ探索
                            if name.startswith(self.lib_name):
                                try:
                                    sub_mod = importlib.import_module(name)
                                    stack.append(
                                        (
                                            sub_mod,
                                            depth + 1,
                                            path + [name.split(".")[-1]],
                                        )
                                    )
                                except:
                                    pass

                # 2. Class
                elif inspect.isclass(obj):
                    kind = "class"
                    # クラス内メソッドも走査
                    for m_name, m_obj in inspect.getmembers(obj):
                        if not m_name.startswith("_") and (
                            inspect.isfunction(m_obj) or inspect.ismethod(m_obj)
                        ):
                            m_sig = ""
                            try:
                                m_sig = str(inspect.signature(m_obj))
                            except:
                                pass

                            data.append(
                                {
                                    "Path": ".".join(path + [m_name]),
                                    "Name": m_name,
                                    "Type": "method",
                                    "Parent": path[-1],
                                    "LOC": 0,
                                    "DocSummary": (inspect.getdoc(m_obj) or "")[:80],
                                    "Signature": m_sig,
                                }
                            )

                # 3. Function
                elif inspect.isfunction(obj):
                    kind = "function"

                # データ登録 (メソッド以外)
                if kind in ["module", "class", "function"]:
                    data.append(
                        {
                            "Path": ".".join(path),
                            "Name": path[-1],
                            "Type": kind,
                            "Parent": path[-2] if len(path) > 1 else self.lib_name,
                            "LOC": loc,
                            "DocSummary": doc_summary,
                            "Signature": "",
                        }
                    )

            except Exception as e:
                # 解析エラーはスキップして続行
                continue

        return pd.DataFrame(data)
