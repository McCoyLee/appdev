"""
项目大纲提取：从仓库文件树 + 文件内容抽出符号表（函数/类/导出名）。

用 Python stdlib `ast` 处理 .py（准）；其他语言用启发式正则（够用）。
没引入 tree-sitter 因为它要装系统依赖；后续如需更准的多语言符号可再换。
"""

from __future__ import annotations

import ast
import re
from dataclasses import dataclass

CODE_EXTS = {
    ".py", ".js", ".mjs", ".cjs", ".ts", ".jsx", ".tsx",
    ".vue", ".html", ".htm", ".css",
    ".go", ".rs", ".java", ".rb", ".c", ".h", ".cpp", ".hpp",
    ".md", ".yml", ".yaml", ".json", ".toml",
}

# 大概率不需要列入大纲的目录
SKIP_DIR_PARTS = {
    "node_modules", "dist", "build", ".venv", "venv", "__pycache__",
    ".git", ".pytest_cache", ".ruff_cache", ".mypy_cache",
}


@dataclass
class Symbol:
    kind: str  # function / class / var / title / section
    name: str
    line: int

    def to_dict(self) -> dict:
        return {"kind": self.kind, "name": self.name, "line": self.line}


def _ext(path: str) -> str:
    return path[path.rfind("."):].lower() if "." in path else ""


def _skip(path: str) -> bool:
    return any(p in SKIP_DIR_PARTS for p in path.split("/"))


# ---------------- 各语言提取器 ----------------

def _extract_python(content: str) -> list[Symbol]:
    try:
        tree = ast.parse(content)
    except SyntaxError:
        return []
    syms: list[Symbol] = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            syms.append(Symbol("function", node.name, node.lineno))
        elif isinstance(node, ast.ClassDef):
            syms.append(Symbol("class", node.name, node.lineno))
    return syms


_JS_FUNC = re.compile(
    r"^\s*(?:export\s+(?:default\s+)?)?(?:async\s+)?function\s+(\w+)",
    re.MULTILINE,
)
_JS_CLASS = re.compile(
    r"^\s*(?:export\s+(?:default\s+)?)?class\s+(\w+)",
    re.MULTILINE,
)
_JS_ARROW = re.compile(
    r"^\s*(?:export\s+)?(?:const|let|var)\s+(\w+)\s*=\s*(?:async\s+)?(?:\([^)]*\)\s*=>|function)",
    re.MULTILINE,
)


def _extract_js(content: str) -> list[Symbol]:
    syms: list[Symbol] = []
    for kind, pattern in (("function", _JS_FUNC), ("class", _JS_CLASS), ("function", _JS_ARROW)):
        for m in pattern.finditer(content):
            line = content.count("\n", 0, m.start()) + 1
            syms.append(Symbol(kind, m.group(1), line))
    return sorted(syms, key=lambda s: s.line)


def _extract_vue(content: str) -> list[Symbol]:
    """从 Vue SFC 抽 <script> 块当 JS 处理。"""
    m = re.search(r"<script[^>]*>(.*?)</script>", content, re.DOTALL)
    return _extract_js(m.group(1)) if m else []


def _extract_html(content: str) -> list[Symbol]:
    syms: list[Symbol] = []
    m = re.search(r"<title>([^<]+)</title>", content)
    if m:
        line = content.count("\n", 0, m.start()) + 1
        syms.append(Symbol("title", m.group(1).strip(), line))
    for m in re.finditer(r"<(section|main|nav|header|footer|article)\b([^>]*)>", content):
        line = content.count("\n", 0, m.start()) + 1
        attrs = m.group(2)
        id_m = re.search(r'id\s*=\s*"([^"]+)"', attrs)
        cls_m = re.search(r'class\s*=\s*"([^"]+)"', attrs)
        name = id_m.group(1) if id_m else (cls_m.group(1) if cls_m else m.group(1))
        syms.append(Symbol("section", f"<{m.group(1)} {name}>", line))
    return syms


def _extract_md(content: str) -> list[Symbol]:
    """从 Markdown 抽标题层级。"""
    syms: list[Symbol] = []
    for i, line in enumerate(content.splitlines(), 1):
        m = re.match(r"^(#{1,4})\s+(.+)$", line)
        if m:
            level = len(m.group(1))
            syms.append(Symbol(f"h{level}", m.group(2).strip(), i))
    return syms


def extract_symbols(path: str, content: str) -> list[Symbol]:
    """根据扩展名分发到对应提取器。"""
    ext = _ext(path)
    if ext == ".py":
        return _extract_python(content)
    if ext in (".js", ".mjs", ".cjs", ".ts", ".jsx", ".tsx"):
        return _extract_js(content)
    if ext == ".vue":
        return _extract_vue(content)
    if ext in (".html", ".htm"):
        return _extract_html(content)
    if ext == ".md":
        return _extract_md(content)
    return []


def is_code_file(path: str) -> bool:
    return (not _skip(path)) and _ext(path) in CODE_EXTS


def format_outline_markdown(outline: dict) -> str:
    """把 outline dict 渲染成给 AI 看的 markdown（节省 token）。"""
    lines = [f"# 项目结构（{outline['total_files']} 代码文件 / {outline['total_paths']} 总文件）", ""]
    for f in outline["files"]:
        if not f["symbols"]:
            lines.append(f"- **{f['path']}** ({f.get('size', '?')}b)")
            continue
        lines.append(f"- **{f['path']}** ({f.get('size', '?')}b)")
        for s in f["symbols"]:
            lines.append(f"  - `{s['kind']}` {s['name']} :{s['line']}")
    if outline.get("other_paths"):
        lines.append("")
        lines.append("**其他文件**：")
        lines.append(", ".join(outline["other_paths"][:30]))
    return "\n".join(lines)
