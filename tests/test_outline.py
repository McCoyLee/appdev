"""outline.py 符号提取器的离线单测（纯函数，无网络）。

覆盖 get_project_outline 工具底层的多语言符号抽取 + markdown 渲染。
运行（项目根）：conda run -n appdev python -m pytest tests/ -q
"""

from backend.app.ai.outline import (
    extract_symbols,
    format_outline_markdown,
    is_code_file,
    _ext,
    _skip,
)


# ----------------------------- 工具函数 -----------------------------

def test_ext_basic():
    assert _ext("a/b/c.py") == ".py"
    assert _ext("FOO.MD") == ".md"
    assert _ext("noext") == ""


def test_skip_dirs():
    assert _skip("node_modules/x/y.js") is True
    assert _skip("frontend/src/main.js") is False
    assert _skip("a/__pycache__/b.py") is True


def test_is_code_file():
    assert is_code_file("backend/app/main.py") is True
    assert is_code_file("node_modules/foo/index.js") is False  # 被 skip
    assert is_code_file("image.png") is False                  # 非代码扩展
    assert is_code_file("README.md") is True


# ----------------------------- Python -----------------------------

def test_python_functions_and_classes():
    src = "def foo():\n    pass\n\nasync def bar():\n    pass\n\nclass Baz:\n    def method(self):\n        pass\n"
    syms = {(s.kind, s.name) for s in extract_symbols("x.py", src)}
    assert ("function", "foo") in syms
    assert ("function", "bar") in syms      # async 也算
    assert ("class", "Baz") in syms
    assert ("function", "method") in syms   # 嵌套方法也被 ast.walk 抓到


def test_python_lineno():
    src = "x = 1\n\ndef foo():\n    pass\n"
    syms = extract_symbols("x.py", src)
    foo = next(s for s in syms if s.name == "foo")
    assert foo.line == 3


def test_python_syntax_error_returns_empty():
    assert extract_symbols("x.py", "def (:\n  bad") == []


# ----------------------------- JS / TS -----------------------------

def test_js_function_class_arrow():
    src = (
        "export function alpha() {}\n"
        "class Beta {}\n"
        "const gamma = () => {}\n"
        "export const delta = async (x) => x\n"
    )
    syms = {(s.kind, s.name) for s in extract_symbols("x.js", src)}
    assert ("function", "alpha") in syms
    assert ("class", "Beta") in syms
    assert ("function", "gamma") in syms
    assert ("function", "delta") in syms


def test_js_sorted_by_line():
    src = "class A {}\nfunction b() {}\n"
    syms = extract_symbols("x.ts", src)
    assert [s.line for s in syms] == sorted(s.line for s in syms)


# ----------------------------- Vue -----------------------------

def test_vue_extracts_script_block():
    src = "<template><div/></template>\n<script setup>\nfunction useThing() {}\n</script>\n"
    names = {s.name for s in extract_symbols("C.vue", src)}
    assert "useThing" in names


# ----------------------------- HTML -----------------------------

def test_html_title_and_sections():
    src = '<title>Hi</title>\n<nav id="top"></nav>\n<section class="hero"></section>\n'
    syms = extract_symbols("i.html", src)
    kinds = {s.kind for s in syms}
    assert "title" in kinds and "section" in kinds
    title = next(s for s in syms if s.kind == "title")
    assert title.name == "Hi"
    assert any("top" in s.name for s in syms if s.kind == "section")


# ----------------------------- Markdown -----------------------------

def test_md_heading_levels():
    src = "# H1\n## H2\nnormal\n#### H4\n"
    syms = extract_symbols("d.md", src)
    by_kind = {(s.kind, s.name) for s in syms}
    assert ("h1", "H1") in by_kind
    assert ("h2", "H2") in by_kind
    assert ("h4", "H4") in by_kind
    assert all(s.kind != "h3" for s in syms)


# ----------------------------- 未知扩展 -----------------------------

def test_unknown_ext_returns_empty():
    assert extract_symbols("x.go", "func main() {}") == []  # go 没专门提取器


# ----------------------------- markdown 渲染 -----------------------------

def test_format_outline_markdown():
    outline = {
        "total_files": 2,
        "total_paths": 5,
        "files": [
            {"path": "a.py", "size": 100, "symbols": [{"kind": "function", "name": "f", "line": 3}]},
            {"path": "empty.txt", "size": 0, "symbols": []},
        ],
        "other_paths": ["x.png", "y.ico"],
    }
    md = format_outline_markdown(outline)
    assert "2 代码文件 / 5 总文件" in md
    assert "**a.py**" in md
    assert "`function` f :3" in md
    assert "其他文件" in md
