from lib_ana.io_piplist import parse_pip_list_columns

def test_parse_pip_list_columns_basic():
    txt = '''Package    Version
----------  -------
pip        24.0
setuptools 69.0.3
'''
    res = parse_pip_list_columns(txt, snapshot_id="s1")
    assert "empty_input" not in res.errors
    assert len(res.df) == 2
    assert res.df.iloc[0]["package"] == "pip"
