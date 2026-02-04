# ファイルパス: C:\lib_ana\src\analyzer_v3.py
import inspect
import importlib
import pkgutil
import pandas as pd
import ast
import os
import sys
import importlib.metadata


class DeepLibraryAnalyzer:
    """
    高度な解析、カテゴリ分類、Mermaid生成機能を持つライブラリアナライザー
    """

    def __init__(self, lib_name):
        self.lib_name = lib_name
        self.target_lib = None
        try:
            self.target_lib = importlib.import_module(lib_name)
        except Exception as e:
            print(f"Warning: Failed to import {lib_name}. {e}")

    @staticmethod
    def get_installed_libraries():
        """インストールされているライブラリのリストを取得"""
        packages = []
        try:
            # importlib.metadata (Python 3.8+)
            dists = importlib.metadata.distributions()
            for dist in dists:
                name = dist.metadata["Name"]
                packages.append(name)
        except Exception:
            pass
        return sorted(list(set(packages)))

    def get_library_summary(self):
        if not self.target_lib:
            return {}, pd.DataFrame()

        df = self.scan_structure(max_depth=5)

        # 統計データの作成
        summary = {
            "Name": self.lib_name,
            "Version": getattr(self.target_lib, "__version__", "unknown"),
            "File": getattr(self.target_lib, "__file__", "built-in"),
            "Doc": (inspect.getdoc(self.target_lib) or "").split("\n")[0],
            "Modules": df[df["Type"] == "module"].shape[0],
            "Classes": df[df["Type"] == "class"].shape[0],
            "Functions": df[df["Type"].isin(["function", "method"])].shape[0],
            "Total_Args": df["ArgCount"].sum(),
        }
        return summary, df

    def scan_structure(self, max_depth=3):
        data = []
        stack = [(self.target_lib, 0, [self.lib_name])]
        visited = set()

        # ルート追加
        self._add_entry(
            data, self.lib_name, "module", self.lib_name, "", self.target_lib
        )

        while stack:
            obj, depth, path = stack.pop()
            obj_id = id(obj)
            if depth > max_depth or obj_id in visited:
                continue
            visited.add(obj_id)

            path_str = ".".join(path)

            try:
                members = inspect.getmembers(obj)
                for name, member_obj in members:
                    # Privateメンバーの扱いはUI側でフィルタリングするため、一旦取得するが
                    # ここでは明らかに内部用とわかるものはスキップも可能。
                    # 今回はユーザーが「使用できる機能」に絞りたい要望があるため
                    # _で始まるものは除外フラグを立てるか、デフォルトで収集してUIで弾く。
                    # ここでは収集し、IsPublicフラグを付ける。

                    is_public = not name.startswith("_")
                    member_path = path + [name]
                    member_path_str = ".".join(member_path)

                    # 1. Module
                    if inspect.ismodule(member_obj):
                        if hasattr(
                            member_obj, "__name__"
                        ) and member_obj.__name__.startswith(self.lib_name):
                            stack.append((member_obj, depth + 1, member_path))
                            self._add_entry(
                                data,
                                name,
                                "module",
                                member_path_str,
                                path_str,
                                member_obj,
                                is_public,
                            )

                    # 2. Class
                    elif inspect.isclass(member_obj):
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
                                is_public,
                            )

                            # Methods
                            for m_name, m_obj in inspect.getmembers(member_obj):
                                m_is_public = not m_name.startswith("_")
                                if inspect.isfunction(m_obj) or inspect.ismethod(m_obj):
                                    m_path_str = member_path_str + "." + m_name
                                    self._add_entry(
                                        data,
                                        m_name,
                                        "method",
                                        m_path_str,
                                        member_path_str,
                                        m_obj,
                                        m_is_public,
                                    )

                    # 3. Function
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
                                is_public,
                            )

            except Exception:
                continue

        return pd.DataFrame(data)

    def _add_entry(
        self, data_list, name, type_, path, parent_path, obj, is_public=True
    ):
        doc = (inspect.getdoc(obj) or "").split("\n\n")[0].replace("\n", " ")[:100]

        # シグネチャ解析
        sig_str = ""
        args_list = []
        return_annotation = ""
        try:
            sig = inspect.signature(obj)
            sig_str = str(sig)
            args_list = list(sig.parameters.keys())
            if sig.return_annotation is not inspect.Signature.empty:
                return_annotation = str(sig.return_annotation).replace("typing.", "")
        except:
            pass

        # カテゴリ分類（簡易ヒューリスティクス）
        category = "Other"
        if type_ in ["method", "function"]:
            if name.startswith("test_"):
                category = "Test"
            elif name.startswith("get_") or name.startswith("set_"):
                category = "Getter/Setter"
            elif name.startswith("is_") or name.startswith("has_"):
                category = "Check"
            elif name.startswith("to_") or name.startswith("as_"):
                category = "Conversion"
            elif (
                name.startswith("load")
                or name.startswith("save")
                or name.startswith("read")
                or name.startswith("write")
            ):
                category = "I/O"
            elif name in ["fit", "predict", "transform", "train", "evaluate"]:
                category = "ML/Action"
            elif name.startswith("on_"):
                category = "Event/Hook"
            elif name == "__init__":
                category = "Constructor"
            else:
                category = "Operation"
        elif type_ == "class":
            if "Error" in name or "Exception" in name:
                category = "Exception"
            elif "Config" in name or "Settings" in name:
                category = "Configuration"
            else:
                category = "Component"
        elif type_ == "module":
            category = "Package"

        data_list.append(
            {
                "Name": name,
                "Type": type_,
                "Path": path,
                "ParentPath": parent_path,
                "IsPublic": is_public,
                "Category": category,
                "ArgCount": len(args_list),
                "Args": ", ".join(args_list),  # 検索用
                "Return": return_annotation,
                "Signature": sig_str,
                "DocSummary": doc,
            }
        )

    def generate_mermaid_code(self, df):
        """解析結果からMermaidクラス図を生成"""
        if df.empty:
            return ""

        # クラスのみ抽出
        classes = df[df["Type"] == "class"]
        if classes.empty:
            return "graph TD;\nMessage[No classes found]"

        mmd = ["classDiagram"]

        # クラス定義
        for _, row in classes.iterrows():
            # 特殊文字除去
            safe_name = row["Name"].replace(".", "_").replace("-", "_")
            mmd.append(f"    class {safe_name}")

        # 親子関係 (簡易的にParentPathから推測、実際はinspect.__bases__が必要だが今回はDataFrame構造から簡易表示)
        # より正確には scan_structure で継承関係リストを作っておくのがベストだが、
        # ここではモジュール包含関係をパッケージ図っぽく表現する

        return "\n".join(mmd)
