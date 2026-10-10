# -*- coding: utf-8 -*-
"""PDF 报告生成测试。"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from geo_optimizer.web.portal.tasks.pdf_report import (  # noqa: E402
    _clean,
    _find_cjk_font,
    generate_pdf,
)

SAMPLE_MD = """\
# GEO 适配分析报告 / GEO Analysis Report

**URL:** https://example.com
**综合得分 / Overall Score:** 46.7/100

## 页面技术体检 / Page Technical Audit

### 主要问题 / Key Issues
- [高] HTTPS 加密 / HTTPS（未启用）
- [中] 结构化数据 (JSON-LD)（缺失）

### 已有优势 / Existing Strengths
- 标题结构 (H1/H2/H3) / Heading structure

## 分引擎评估 / Per-Engine Evaluation

### 豆包（字节跳动）— 52/100

| 维度 / Dimension | 得分 / Score |
|------|------|
| technical | 40 |
| content | 60 |

改进建议 / Suggestions:
- 添加 HTTPS 加密
- 补充 JSON-LD 结构化数据
"""


class TestPdfReport:
    def test_generate_pdf_creates_valid_file(self, tmp_path):
        out = tmp_path / "report.pdf"
        ok = generate_pdf(SAMPLE_MD, out)
        assert ok, "PDF 生成应成功"
        assert out.is_file()
        header = out.read_bytes()[:5]
        assert header == b"%PDF-", "文件应为有效 PDF 格式"
        assert out.stat().st_size > 500, "PDF 文件不应过小"

    def test_generate_pdf_empty_text(self, tmp_path):
        out = tmp_path / "empty.pdf"
        ok = generate_pdf("", out)
        assert ok
        assert out.is_file()

    def test_clean_strips_markdown(self):
        assert _clean("**bold** text") == "bold text"
        assert _clean("*italic*") == "italic"
        assert _clean("no markup") == "no markup"

    def test_cjk_font_found(self):
        """当前系统应能找到 CJK 字体（macOS/Linux）。"""
        # 仅验证函数可调用，CI 无字体时返回 None 也不报错
        result = _find_cjk_font()
        # macOS 上应有 Arial Unicode 或 STHeiti
        # 不做 assert result is not None（兼容无字体环境）
        assert result is None or Path(result).is_file()
