# src/analyzer_v2.py
import inspect
import importlib
import ast
import pandas as pd
import pkgutil
import sys
from collections import defaultdict

class DeepLibraryAnalyzer:
    """
    inspectとAST(抽象構文木)を組み合わせた深層解析クラス。
    """
    def __init__(self, lib_name):
        self.lib_name = lib_name
        self.target_lib = None
        try:
            self.target_lib = importlib.import_module(lib_name)
        except ImportError as e:
            print(f"Failed to import {lib_name}: {e}")
            
    def get_library_summary(self):
        """ライブラリ全体の統計情報を取得"""
        if not self.target_lib: return {}
        
        summary = {
            "Name": self.lib_name,
            "Version": getattr(self.target_lib, '__version__', 'unknown'),
            "File": getattr(self.target_lib, '__file__', 'built-in'),
            "Doc": (inspect.getdoc(self.target_lib) or "").split('\n')[0],
            "Modules": 0,
            "Classes": 0,
            "Functions": 0
        }
        
        # 簡易カウント
        df = self.scan_structure(max_depth=5)
        if not df.empty:
            summary["Modules"] = df[df['Type'] == 'module'].shape[0]
            summary["Classes"] = df[df['Type'] == 'class'].shape[0]
            summary["Functions"] = df[df['Type'].isin(['function', 'method'])].shape[0]
            
        return summary, df

    def scan_structure(self, max_depth=3):
        """再帰的に構造をスキャンしDataFrame化"""
        data = []
        stack = [(self.target_lib, 0, [self.lib_name])]
        visited = set()

        while stack:
            obj, depth, path = stack.pop()
            if depth > max_depth or obj in visited: continue
            visited.add(obj)

            try:
                # AST解析用にソースコード取得を試みる
                try:
                    source = inspect.getsource(obj)
                    loc = len(source.split('\n'))
                except:
                    loc = 0
                
                # Docstringの要約（最初の空行まで）
                raw_doc = inspect.getdoc(obj) or ""
                doc_summary = raw_doc.split('\n\n')[0].replace('\n', ' ')[:150] + "..." if len(raw_doc) > 150 else raw_doc.split('\n\n')[0]

                # 種別判定とデータ格納
                kind = "unknown"
                if inspect.ismodule(obj):
                    kind = "module"
                    if hasattr(obj, '__path__'):
                        # サブモジュールの探索
                        for _, name, _ in pkgutil.iter_modules(obj.__path__, prefix=f"{obj.__name__}."):
                            # ライブラリ内部のみ
                            if name.startswith(self.lib_name):
                                try:
                                    sub_mod = importlib.import_module(name)
                                    stack.append((sub_mod, depth + 1, path + [name.split('.')[-1]]))
                                except: pass
                
                elif inspect.isclass(obj):
                    kind = "class"
                    # クラス内メソッド探索
                    for m_name, m_obj in inspect.getmembers(obj):
                        if not m_name.startswith("_") and (inspect.isfunction(m_obj) or inspect.ismethod(m_obj)):
                            # メソッドも追加
                            m_sig = str(inspect.signature(m_obj)) rescue ''
                            data.append({
                                "Path": ".".join(path + [m_name]),
                                "Name": m_name,
                                "Type": "method",
                                "Parent": path[-1],
                                "LOC": 0, # メソッド単位のLOCは重いので省略
                                "DocSummary": (inspect.getdoc(m_obj) or "")[:50]
                            })
                            
                elif inspect.isfunction(obj):
                    kind = "function"

                # 現在のオブジェクトを登録 (メソッド以外)
                if kind in ['module', 'class', 'function']:
                    data.append({
                        "Path": ".".join(path),
                        "Name": path[-1],
                        "Type": kind,
                        "Parent": path[-2] if len(path) > 1 else self.lib_name,
                        "LOC": loc,
                        "DocSummary": doc_summary
                    })

            except Exception as e:
                pass # 解析エラーは無視して続行
        
        return pd.DataFrame(data)

    def get_class_hierarchy(self, class_name):
        """特定のクラスの継承ツリー（Mermaid用）を取得"""
        # 実装略（前回と同様のロジックで特定のクラス周辺のみ抽出）
        pass