import streamlit as st
import os
import ast
import pandas as pd
import glob
import json
from typing import List, Dict, Optional, Any, Tuple

# --- Streamlit Page Configuration ---
st.set_page_config(
    layout="wide",
    page_title="TimesFM Deep Dive Explorer",
    page_icon="⚡",
    initial_sidebar_state="expanded"
)

# --- CSS Styling for Modern Look ---
st.markdown("""
<style>
    .stApp {
        background-color: #0e1117;
    }
    .main-header {
        font-size: 2.5rem;
        font-weight: 700;
        color: #f0f2f6;
        margin-bottom: 1rem;
    }
    .sub-header {
        font-size: 1.5rem;
        font-weight: 600;
        color: #4da6ff;
        margin-top: 2rem;
    }
    .card {
        background-color: #262730;
        padding: 1.5rem;
        border-radius: 0.5rem;
        margin-bottom: 1rem;
        border: 1px solid #41444e;
    }
    .metric-container {
        display: flex;
        justify-content: space-between;
        margin-bottom: 2rem;
    }
    .stCodeBlock {
        border-radius: 0.5rem;
    }
</style>
""", unsafe_allow_html=True)

# --- AST Analysis Logic ---

class CodeAnalyzer:
    """Enhanced AST Analyzer for extracting rich metadata including type hints and source code."""
    
    def __init__(self, root_dir: str):
        self.root_dir = root_dir
        self.data = []

    def parse_directory(self) -> pd.DataFrame:
        files = glob.glob(os.path.join(self.root_dir, "**", "*.py"), recursive=True)
        progress_bar = st.progress(0)
        
        for i, file_path in enumerate(files):
            self._parse_file(file_path)
            progress_bar.progress((i + 1) / len(files))
        
        progress_bar.empty()
        return pd.DataFrame(self.data)

    def _get_source_segment(self, content_lines: List[str], node: ast.AST) -> str:
        """Extract exact source code segment using line numbers."""
        try:
            start = node.lineno - 1
            end = node.end_lineno
            # インデントの調整は表示側で行うか、そのまま表示する
            return "\n".join(content_lines[start:end])
        except (AttributeError, IndexError):
            return ""

    def _parse_annotation(self, annotation: ast.AST) -> str:
        """Recursively parse type annotations."""
        if annotation is None:
            return "Any"
        try:
            return ast.unparse(annotation)
        except Exception:
            return "ComplexType"

    def _extract_args(self, node: ast.FunctionDef) -> List[Dict[str, Any]]:
        """Extract detailed argument information including types and defaults."""
        args_list = []
        
        # Handle arguments
        defaults_offset = len(node.args.args) - len(node.args.defaults)
        
        for i, arg in enumerate(node.args.args):
            default_val = None
            if i >= defaults_offset:
                try:
                    default_val = ast.unparse(node.args.defaults[i - defaults_offset])
                except:
                    default_val = "value"
            
            args_list.append({
                "name": arg.arg,
                "type": self._parse_annotation(arg.annotation),
                "default": default_val,
                "kind": "Positional/Keyword"
            })
            
        # Handle *args
        if node.args.vararg:
            args_list.append({
                "name": f"*{node.args.vararg.arg}",
                "type": self._parse_annotation(node.args.vararg.annotation),
                "default": None,
                "kind": "VarArg"
            })

        # Handle **kwargs
        if node.args.kwarg:
            args_list.append({
                "name": f"**{node.args.kwarg.arg}",
                "type": self._parse_annotation(node.args.kwarg.annotation),
                "default": None,
                "kind": "KwArg"
            })
            
        return args_list

    def _parse_file(self, file_path: str):
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
                content_lines = content.splitlines()
                
            tree = ast.parse(content)
            rel_path = os.path.relpath(file_path, self.root_dir)
            module_name = rel_path.replace(os.sep, ".").replace(".py", "")

            # Module Docstring
            module_doc = ast.get_docstring(tree)
            self.data.append({
                "id": module_name,
                "type": "Module",
                "name": module_name,
                "path": rel_path,
                "docstring": module_doc,
                "parent": None,
                "args": [],
                "return_type": None,
                "source": "",
                "line": 1
            })

            for node in tree.body:
                if isinstance(node, ast.ClassDef):
                    self._process_class(node, module_name, rel_path, content_lines)
                elif isinstance(node, ast.FunctionDef):
                    self._process_function(node, module_name, rel_path, module_name, content_lines)

        except Exception as e:
            # print(f"Error parsing {file_path}: {e}")
            pass

    def _process_class(self, node: ast.ClassDef, module_name: str, file_path: str, content_lines: List[str]):
        class_id = f"{module_name}.{node.name}"
        self.data.append({
            "id": class_id,
            "type": "Class",
            "name": node.name,
            "path": file_path,
            "docstring": ast.get_docstring(node),
            "parent": module_name,
            "args": [], # Classes can have bases, but we simplify here
            "return_type": None,
            "source": self._get_source_segment(content_lines, node),
            "line": node.lineno
        })

        for item in node.body:
            if isinstance(item, ast.FunctionDef):
                self._process_function(item, module_name, file_path, class_id, content_lines)

    def _process_function(self, node: ast.FunctionDef, module_name: str, file_path: str, parent_id: str, content_lines: List[str]):
        func_id = f"{parent_id}.{node.name}"
        args = self._extract_args(node)
        return_type = self._parse_annotation(node.returns)
        
        self.data.append({
            "id": func_id,
            "type": "Method" if ".Class" in str(parent_id) or "Class" in str(parent_id) else "Function", # Simplified logic
            "name": node.name,
            "path": file_path,
            "docstring": ast.get_docstring(node),
            "parent": parent_id,
            "args": args,
            "return_type": return_type,
            "source": self._get_source_segment(content_lines, node),
            "line": node.lineno
        })

# --- UI Components ---

def render_json_copy_button(data: Dict, label: str = "Copy as JSON"):
    """Renders a JSON block with a built-in copy button."""
    json_str = json.dumps(data, indent=2, ensure_ascii=False)
    st.markdown(f"**{label}**")
    st.code(json_str, language="json")

def main():
    # Sidebar: Setup
    with st.sidebar:
        st.header("⚙️ Configuration")
        default_path = "/mnt/e/env/ts/lib_ana/google-research/timesfm"
        if not os.path.exists(default_path):
            default_path = "."
        
        root_path = st.text_input("Project Root Path", value=default_path)
        
        if st.button("🚀 Analyze Codebase", use_container_width=True, type="primary"):
            if os.path.exists(root_path):
                analyzer = CodeAnalyzer(root_path)
                with st.spinner("Parsing AST structure..."):
                    df = analyzer.parse_directory()
                    st.session_state.df = df
                    st.success("Analysis Complete!")
            else:
                st.error("Invalid path.")

    # Main Area
    st.markdown('<div class="main-header">⚡ TimesFM Deep Dive Explorer</div>', unsafe_allow_html=True)

    if "df" in st.session_state:
        df = st.session_state.df
        
        # 1. Dashboard Metrics
        cols = st.columns(4)
        cols[0].metric("Modules", len(df[df['type'] == 'Module']))
        cols[1].metric("Classes", len(df[df['type'] == 'Class']))
        cols[2].metric("Functions/Methods", len(df[df['type'].isin(['Function', 'Method'])]))
        cols[3].metric("Total Lines Analyzed", df['line'].max())
        
        st.divider()

        # 2. Cascade Navigation (Drill Down)
        col_nav, col_detail = st.columns([1, 2])

        with col_nav:
            st.subheader("🔍 Navigation")
            
            # Level 1: Select Module
            modules = sorted(df[df['type'] == 'Module']['name'].unique())
            selected_module_name = st.selectbox("Select Module", modules, index=0)
            
            # Level 2: Select Class (Optional) or Function in Module
            module_items = df[(df['parent'] == selected_module_name) | (df['name'] == selected_module_name)]
            
            # Filter classes and standalone functions
            classes = sorted(df[(df['parent'] == selected_module_name) & (df['type'] == 'Class')]['name'].unique())
            
            selected_class_name = None
            if classes:
                selected_class_name = st.selectbox("Select Class (Optional)", ["(None)"] + classes)
            
            # Level 3: Select Method/Function
            if selected_class_name and selected_class_name != "(None)":
                # Methods of selected class
                class_full_id = f"{selected_module_name}.{selected_class_name}"
                methods = sorted(df[df['parent'] == class_full_id]['name'].unique())
                selected_func_name = st.selectbox("Select Method", ["(Class Definition)"] + methods)
                
                # Determine what to show
                if selected_func_name == "(Class Definition)":
                    target_id = class_full_id
                else:
                    target_id = f"{class_full_id}.{selected_func_name}"
            else:
                # Functions in module (not in class)
                funcs = sorted(df[(df['parent'] == selected_module_name) & (df['type'] == 'Function')]['name'].unique())
                if funcs:
                    selected_func_name = st.selectbox("Select Function", ["(Module Overview)"] + funcs)
                    if selected_func_name == "(Module Overview)":
                        target_id = selected_module_name
                    else:
                        target_id = f"{selected_module_name}.{selected_func_name}"
                else:
                    target_id = selected_module_name

        # 3. Detail View
        with col_detail:
            # Fetch target data
            target_rows = df[df['id'] == target_id]
            
            if not target_rows.empty:
                item = target_rows.iloc[0]
                
                # Header
                st.subheader(f"{item['type']}: {item['name']}")
                st.caption(f"Path: `{item['path']}` | Line: `{item['line']}`")
                
                # Tabs for organized view
                tab_overview, tab_code, tab_json = st.tabs(["📖 Overview & Args", "💻 Source Code", "📋 JSON Export"])
                
                with tab_overview:
                    # Docstring
                    if item['docstring']:
                        st.markdown("#### Docstring")
                        st.info(item['docstring'])
                    else:
                        st.warning("No docstring available.")

                    # Arguments Table (if applicable)
                    if item['type'] in ['Function', 'Method'] and item['args']:
                        st.markdown("#### Arguments & Types")
                        
                        args_data = pd.DataFrame(item['args'])
                        if not args_data.empty:
                            # Format for display
                            display_df = args_data[['name', 'type', 'default', 'kind']].copy()
                            display_df['default'] = display_df['default'].apply(lambda x: f"`{x}`" if x else "-")
                            display_df['type'] = display_df['type'].apply(lambda x: f"**{x}**")
                            
                            st.dataframe(
                                display_df, 
                                use_container_width=True,
                                column_config={
                                    "name": "Argument",
                                    "type": "Type Hint",
                                    "default": "Default Value",
                                    "kind": "Kind"
                                },
                                hide_index=True
                            )
                        
                        if item['return_type']:
                            st.markdown(f"**Return Type:** `{item['return_type']}`")

                with tab_code:
                    st.markdown("#### Implementation")
                    if item['source']:
                        st.code(item['source'], language='python', line_numbers=True)
                    else:
                        st.text("Source code not available.")

                with tab_json:
                    st.markdown("#### Data Export")
                    st.markdown("以下のJSONブロック右上のコピーボタンで、構造化データをクリップボードにコピーできます。")
                    
                    # Construct clean export object
                    export_obj = {
                        "name": item['name'],
                        "type": item['type'],
                        "module": selected_module_name,
                        "signature": {
                            "args": item['args'],
                            "return_type": item['return_type']
                        },
                        "docstring": item['docstring'],
                        "file_path": item['path']
                    }
                    
                    render_json_copy_button(export_obj, label="Component Metadata JSON")

            else:
                st.info("Select an item from the navigation to view details.")

    else:
        st.info("👈 サイドバーからTimesFMのディレクトリパスを入力し、'Analyze Codebase' をクリックしてください。")

if __name__ == "__main__":
    main()