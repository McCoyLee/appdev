"""列出可用模板。"""

from __future__ import annotations

import json
from pathlib import Path

from fastapi import APIRouter, HTTPException

router = APIRouter(prefix="/api/templates", tags=["templates"])

# 模板根目录：相对仓库根
TEMPLATES_ROOT = Path(__file__).resolve().parents[3] / "templates"


def _load_metadata(template_dir: Path) -> dict | None:
    meta_file = template_dir / "template.json"
    if not meta_file.exists():
        return None
    try:
        meta = json.loads(meta_file.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    # 统计文件数 / 主要文件列表（不含 .github 内的）
    files = [p.relative_to(template_dir).as_posix() for p in template_dir.rglob("*") if p.is_file()]
    meta["file_count"] = len(files)
    meta["primary_files"] = [f for f in files if not f.startswith(".github/")][:10]
    return meta


@router.get("")
async def list_templates():
    if not TEMPLATES_ROOT.exists():
        raise HTTPException(404, "模板目录不存在")
    items: list[dict] = []
    for d in sorted(TEMPLATES_ROOT.iterdir()):
        if not d.is_dir():
            continue
        meta = _load_metadata(d)
        if meta:
            items.append(meta)
    return {"templates": items}


@router.get("/{template_id}")
async def get_template(template_id: str):
    target = TEMPLATES_ROOT / template_id
    if not target.is_dir():
        raise HTTPException(404, f"模板 {template_id} 不存在")
    meta = _load_metadata(target)
    if not meta:
        raise HTTPException(500, "模板缺少 template.json")
    return meta
