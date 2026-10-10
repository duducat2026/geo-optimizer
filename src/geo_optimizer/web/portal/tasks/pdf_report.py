# -*- coding: utf-8 -*-
"""Markdown 评估报告 → PDF（fpdf2 + 系统 CJK 字体）。"""
import logging
import re
from pathlib import Path

logger = logging.getLogger(__name__)

# CJK 字体搜索路径（macOS / Linux 常见位置）
_FONT_SEARCH = [
    "/Library/Fonts/Arial Unicode.ttf",
    "/System/Library/Fonts/STHeiti Medium.ttc",
    "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/noto-cjk/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
    "/usr/share/fonts/google-noto-cjk/NotoSansCJK-Regular.ttc",
]


def _find_cjk_font() -> str | None:
    for path in _FONT_SEARCH:
        if Path(path).is_file():
            return path
    return None


def generate_pdf(markdown_text: str, output_path: str | Path) -> bool:
    """将 markdown 报告渲染为 PDF。成功返回 True，失败仅告警返回 False。"""
    try:
        from fpdf import FPDF
        from fpdf.enums import XPos
    except ImportError:
        logger.warning("fpdf2 未安装，跳过 PDF 生成")
        return False

    try:
        pdf = FPDF()
        pdf.set_auto_page_break(auto=True, margin=20)
        pdf.add_page()

        # 注册 CJK 字体
        font_path = _find_cjk_font()
        if font_path:
            pdf.add_font("CJK", "", font_path)
            pdf.add_font("CJK", "B", font_path)
            base_font = "CJK"
        else:
            base_font = "Helvetica"
            logger.warning("未找到 CJK 字体，PDF 中文可能无法显示")

        # fpdf2 新版 multi_cell 默认 x 停在右边界，需显式回到左边距
        NX = XPos.LMARGIN

        pdf.set_font(base_font, size=10)
        lines = markdown_text.split("\n")
        i = 0
        while i < len(lines):
            line = lines[i]
            i += 1

            # 空行
            if not line.strip():
                pdf.ln(3)
                continue

            # 标题
            if line.startswith("# "):
                pdf.set_font(base_font, "B", 16)
                pdf.multi_cell(0, 8, _clean(line[2:]), new_x=NX)
                pdf.ln(3)
                pdf.set_font(base_font, size=10)
            elif line.startswith("## "):
                pdf.ln(2)
                pdf.set_font(base_font, "B", 13)
                pdf.multi_cell(0, 7, _clean(line[3:]), new_x=NX)
                pdf.ln(2)
                pdf.set_font(base_font, size=10)
            elif line.startswith("### "):
                pdf.set_font(base_font, "B", 11)
                pdf.multi_cell(0, 6, _clean(line[4:]), new_x=NX)
                pdf.ln(1)
                pdf.set_font(base_font, size=10)
            # 表格行
            elif line.startswith("|"):
                _render_table_row(pdf, line, base_font)
            # 无序列表
            elif line.startswith("- "):
                pdf.multi_cell(0, 5.5, f"  •  {_clean(line[2:])}", new_x=NX)
            # 有序列表
            elif re.match(r"^\d+\.\s", line):
                pdf.multi_cell(0, 5.5, f"  {_clean(line)}", new_x=NX)
            # 普通段落（含粗体标记清理）
            else:
                pdf.multi_cell(0, 5.5, _clean(line), new_x=NX)

        pdf.output(str(output_path))
        return True
    except Exception as exc:  # noqa: BLE001
        logger.warning("PDF 生成失败: %s", exc)
        return False


def _clean(text: str) -> str:
    """移除 markdown 粗体/斜体标记。"""
    text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)
    text = re.sub(r"\*(.+?)\*", r"\1", text)
    return text.strip()


def _render_table_row(pdf, line: str, font: str) -> None:
    """简单渲染表格行（跳过分隔行）。"""
    cells = [c.strip() for c in line.strip("|").split("|")]
    if all(re.match(r"^[-:]+$", c) for c in cells):
        return  # 分隔行
    pdf.set_font(font, size=9)
    usable = pdf.w - pdf.l_margin - pdf.r_margin
    col_w = max(usable / max(len(cells), 1), 20)
    for cell in cells:
        txt = _clean(cell)[:30]
        pdf.cell(col_w, 5.5, txt, border=1)
    pdf.ln()
    pdf.set_font(font, size=10)
