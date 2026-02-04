# ファイルパス: C:\lib_ana\src\analyzer_v2.py
import inspect
import importlib
import pkgutil
import pandas as pd
import ast
import os


class DeepLibraryAnalyzer:
    """
    inspectモジュールとAST解析を組み合わせ、
    親子関係をフルパスで厳密に管理するライブラリ分析クラス。
    """

    def __init__(self, lib_name):
        self.lib_name = lib_name
        self.target_lib = None
        try:
            self.target_lib = importlib.import_module(lib_name)
        except ImportError as e:
            print(f"Warning: Failed to import {lib_name}. {e}")

    def get_library_summary(self):
        if not self.target_lib:
            return {}, pd.DataFrame()

        df = self.scan_structure(max_depth=5)

        summary = {
            "Name": self.lib_name,
            "Version": getattr(self.target_lib, "__version__", "unknown"),
            "File": getattr(self.target_lib, "__file__", "built-in"),
            "Doc": (inspect.getdoc(self.target_lib) or "").split("\n")[0],
            "Modules": df[df["Type"] == "module"].shape[0],
            "Classes": df[df["Type"] == "class"].shape[0],
            "Functions": df[df["Type"].isin(["function", "method"])].shape[0],
        }
        return summary, df

    def scan_structure(self, max_depth=3):
        data = []
        # スタック: (object, depth, current_full_path_list)
        stack = [(self.target_lib, 0, [self.lib_name])]
        visited = set()

        # ルートモジュール自身の登録
        self._add_entry(
            data, self.lib_name, "module", self.lib_name, "", self.target_lib
        )

        while stack:
            obj, depth, path = stack.pop()

            # 循環参照防止
            obj_id = id(obj)
            if depth > max_depth or obj_id in visited:
                continue
            visited.add(obj_id)

            path_str = ".".join(path)

            try:
                # メンバー走査
                members = inspect.getmembers(obj)
                for name, member_obj in members:
                    if name.startswith("_"):
                        continue

                    member_path = path + [name]
                    member_path_str = ".".join(member_path)

                    # 1. Module (Submodule)
                    if inspect.ismodule(member_obj):
                        # ライブラリ内部のモジュールか確認
                        if hasattr(
                            member_obj, "__name__"
                        ) and member_obj.__name__.startswith(self.lib_name):
                            # 再帰探索に追加
                            stack.append((member_obj, depth + 1, member_path))
                            self._add_entry(
                                data,
                                name,
                                "module",
                                member_path_str,
                                path_str,
                                member_obj,
                            )

                    # 2. Class
                    elif inspect.isclass(member_obj):
                        # 定義元がこのライブラリである場合のみ追加（外部ライブラリのimportを除外）
                        if (
                            hasattr(member_obj, "__module__")
                            and member_obj.__module__
                            and member_obj.__module__.startswith(self.lib_name)
                        ):
                            self._add_entry(
                                data,
                                name,
                                "class",
                                member_path_str,
                                path_str,
                                member_obj,
                            )

                            # クラス内メソッド走査
                            for m_name, m_obj in inspect.getmembers(member_obj):
                                if not m_name.startswith("_") and (
                                    inspect.isfunction(m_obj) or inspect.ismethod(m_obj)
                                ):
                                    m_path_str = member_path_str + "." + m_name
                                    self._add_entry(
                                        data,
                                        m_name,
                                        "method",
                                        m_path_str,
                                        member_path_str,
                                        m_obj,
                                    )

                    # 3. Function (Standalone)
                    elif inspect.isfunction(member_obj):
                        if (
                            hasattr(member_obj, "__module__")
                            and member_obj.__module__
                            and member_obj.__module__.startswith(self.lib_name)
                        ):
                            self._add_entry(
                                data,
                                name,
                                "function",
                                member_path_str,
                                path_str,
                                member_obj,
                            )

            except Exception:
                continue

        return pd.DataFrame(data)

    def _add_entry(self, data_list, name, type_, path, parent_path, obj):
        """データリストへの追加ヘルパー"""
        doc = (inspect.getdoc(obj) or "").split("\n\n")[0].replace("\n", " ")[:100]
        sig = ""
        try:
            sig = str(inspect.signature(obj))
        except:
            pass

        data_list.append(
            {
                "Name": name,  # 表示用短縮名 (例: Pipeline)
                "Type": type_,  # module, class, method, function
                "Path": path,  # 一意なID (例: chronos.base.Pipeline)
                "ParentPath": parent_path,  # 親のID (例: chronos.base)
                "DocSummary": doc,
                "Signature": sig,
            }
        )
