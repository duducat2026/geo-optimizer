# -*- coding: utf-8 -*-
"""按平台生成 Skill / MCP 发布变体包。

支持平台（platform ∈ SUPPORTED_PLATFORMS）:
    modelscope  — SKILL.md 原样 + scripts/；MCP 为 streamableHttp 配置 + readme
    qianwen     — 千问AI 合规 frontmatter（description ≤1024 且无尖括号）
    bailian     — 阿里云百炼，与千问同后台规范，复用千问变体内容
    workbuddy   — Skill frontmatter 追加 description_zh/en 等字段；
                  MCP 为连接器五件套（connector-meta/mcp/icon/token-schema/skills/）

安全约定: 平台变体包一律不含明文密钥——Skill 包不含 config.json，
MCP 配置使用 ${GEO_API_KEY} 占位符（用户在实际配置时填入自己的密钥）。

命名规范: Skill 与 MCP 包共用 geoskill-{platform}-{YYYYMMDD}.zip 格式。
"""
from __future__ import annotations

import io
import re
import zipfile
from datetime import datetime
from pathlib import Path

import yaml

SUPPORTED_PLATFORMS = ("modelscope", "qianwen", "bailian", "workbuddy")

# 对外公开的云端平台地址（变体包内固定使用，不随导出来源变化）
PUBLIC_BASE_URL = "https://geo.tool.jiuchongju.com"
MCP_ENDPOINT = f"{PUBLIC_BASE_URL}/mcp"

# 开源仓库地址：所有对外发布物（SKILL.md / 平台 readme / connector-meta）统一引用
REPO_URL = "https://github.com/duducat2026/geo-optimizer"

_ROOT = Path(__file__).resolve().parents[5]
SKILL_SRC = _ROOT / "docs" / "geo-skill"
PLATFORM_ASSETS = SKILL_SRC / "platforms"
SCRIPT_FILES = ("geo_skill_client.py", "geo_skill_api.py", "geo_skill_common.py")

# ── 千问AI/百炼版: 精简后的 description（无尖括号, <=1024 字符） ──────────
QIANWEN_DESCRIPTION = """Submit GEO (Generative Engine Optimization) analysis tasks to the GEO-Optimizer
platform, check progress on demand, and fetch optimization reports. Use this skill
whenever users ask to evaluate, analyze or score a website in natural language
— e.g. "请评估网站 www.aliyun.com", "evaluate website example.com" — or want
AI search visibility checks, GEO scores across 11 AI engines, optimization plans,
or content packages. Tasks default to full analysis (evaluation + plan).
Workflow — (1) Submit: run the client with --url SITE; it returns immediately
with the site, task id and estimated wait minutes — relay those to the user and
STOP; never poll on a timer. (2) On progress requests: run --recent to list
recent task ids and sites, ask which one to check (skip if only one), then run
--progress TASK_ID for current status and execution logs so far. (3) When
completed, --progress returns final scores and the no-login download link (or
pass --output FILE.ZIP to download). All client output is in Chinese; surface
it as-is."""

# ── WorkBuddy 版: frontmatter 追加字段 ─────────────────────────────────
WORKBUDDY_FIELDS = {
    "description_zh": ("GEO（生成式引擎优化）分析工具，评估网站在 AI 搜索引擎中的可见性，"
                       "提供优化建议和改进方案"),
    "description_en": ("GEO (Generative Engine Optimization) analysis tool that evaluates "
                       "website visibility in AI search engines and provides optimization "
                       "recommendations"),
    "version": "1.8.4",
    "author": "GEO-Optimizer",
    "category": "development",
}


# ─── frontmatter 变换 ──────────────────────────────────────────────────────

def _split_frontmatter(text: str):
    """拆分 (frontmatter_raw, body)。"""
    m = re.match(r"^---\n(.*?)\n---\n?(.*)$", text, re.DOTALL)
    if not m:
        raise ValueError("SKILL.md 缺少 YAML frontmatter")
    return m.group(1), m.group(2)


def _fold_block(text: str, indent: int = 2) -> str:
    """把多行描述折成 YAML `>-` 块（每行前加缩进）。"""
    pad = " " * indent
    return "\n".join(pad + line for line in text.strip().splitlines())


def _qianwen_skill_text(base_text: str) -> str:
    """替换 frontmatter 中的 description 为千问合规版本，其余保持不变。"""
    fm_raw, _ = _split_frontmatter(base_text)
    new_block = "description: >-\n" + _fold_block(QIANWEN_DESCRIPTION) + "\n"
    updated_fm = re.sub(
        r"^description: >-\n(?:[ \t]+.*\n)+",
        lambda _: new_block,
        fm_raw,
        count=1,
        flags=re.MULTILINE,
    )
    if updated_fm == fm_raw:
        raise ValueError("未能替换 description 块（正则未匹配）")
    return base_text.replace(fm_raw, updated_fm, 1)


def _workbuddy_skill_text(base_text: str) -> str:
    """在 frontmatter 中追加 WorkBuddy 字段，并将 version 加引号。"""
    fm_raw, _ = _split_frontmatter(base_text)
    lines = fm_raw.splitlines()
    for i, line in enumerate(lines):
        if re.match(r"^version:\s*[\d.]+\s*$", line):
            lines[i] = f'version: "{line.split(":", 1)[1].strip()}"'
            break
    insert_at = next((i for i, ln in enumerate(lines) if ln.startswith("metadata:")),
                     len(lines))
    additions = [
        f'description_zh: "{WORKBUDDY_FIELDS["description_zh"]}"',
        f'description_en: "{WORKBUDDY_FIELDS["description_en"]}"',
        f'author: "{WORKBUDDY_FIELDS["author"]}"',
        f'category: "{WORKBUDDY_FIELDS["category"]}"',
    ]
    lines[insert_at:insert_at] = additions
    return base_text.replace(fm_raw, "\n".join(lines), 1)


def normalize_platform(platform: str | None) -> str:
    """校验并归一化平台名；非法值抛 ValueError（路由层转 400）。"""
    p = (platform or "").strip().lower()
    if p not in SUPPORTED_PLATFORMS:
        raise ValueError(f"不支持的导出平台: {platform!r}（可选 {SUPPORTED_PLATFORMS}）")
    return p


def zip_name(platform: str) -> str:
    """按命名规范生成包名: geoskill-{platform}-{YYYYMMDD}.zip"""
    return f"geoskill-{normalize_platform(platform)}-{datetime.now().strftime('%Y%m%d')}.zip"


def skill_md_text(platform: str) -> str:
    """按平台返回变体 SKILL.md 全文。"""
    base = (SKILL_SRC / "SKILL.md").read_text(encoding="utf-8")
    p = normalize_platform(platform)
    if p in ("qianwen", "bailian"):
        return _qianwen_skill_text(base)
    if p == "workbuddy":
        return _workbuddy_skill_text(base)
    return base


# ─── Skill 变体包 ─────────────────────────────────────────────────────────

def build_skill_zip(platform: str) -> bytes:
    """生成平台 Skill 变体 ZIP（根目录直接包含 SKILL.md 与 scripts/，不含密钥）。"""
    normalize_platform(platform)
    text = skill_md_text(platform)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        info = zipfile.ZipInfo("SKILL.md")
        info.external_attr = 0o644 << 16
        zf.writestr(info, text.encode("utf-8"))
        for name in SCRIPT_FILES:
            info = zipfile.ZipInfo(f"scripts/{name}")
            info.create_system = 3  # Unix
            info.external_attr = 0o755 << 16  # 保留可执行权限
            zf.writestr(info, (SKILL_SRC / "scripts" / name).read_bytes())
    return buf.getvalue()


# ─── MCP 变体包 ───────────────────────────────────────────────────────────

def _ms_mcp_config_json() -> str:
    cfg = {
        "mcpServers": {
            "geo-optimizer": {
                "type": "streamableHttp",
                "url": MCP_ENDPOINT,
                "headers": {"Authorization": "Bearer ${GEO_API_KEY}"},
            }
        }
    }
    import json
    return json.dumps(cfg, ensure_ascii=False, indent=2) + "\n"


def _qw_mcp_config_json() -> str:
    cfg = {
        "mcpServers": {
            "geo-optimizer": {
                "type": "streamableHttp",
                "url": MCP_ENDPOINT,
                "env": {"GEO_API_KEY": "${GEO_API_KEY}"},
            }
        }
    }
    import json
    return json.dumps(cfg, ensure_ascii=False, indent=2) + "\n"


def _wb_mcp_json() -> str:
    return (PLATFORM_ASSETS / "workbuddy" / "mcp.json").read_text(encoding="utf-8")


def build_mcp_zip(platform: str) -> bytes:
    """生成平台 MCP 配置/连接器 ZIP（密钥一律 ${GEO_API_KEY} 占位符）。"""
    p = normalize_platform(platform)
    wb = PLATFORM_ASSETS / "workbuddy"
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        if p == "modelscope":
            zf.writestr("config.json", _ms_mcp_config_json())
            zf.writestr("readme.md",
                        (PLATFORM_ASSETS / "modelscope" / "readme.md").read_bytes())
            zf.writestr("icon.svg", (_ROOT / "docs" / "assets" / "icon.svg").read_bytes())
        elif p in ("qianwen", "bailian"):
            zf.writestr("config.json", _qw_mcp_config_json())
        elif p == "workbuddy":
            zf.writestr("connector-meta.json", (wb / "connector-meta.json").read_bytes())
            zf.writestr("mcp.json", _wb_mcp_json())
            zf.writestr("icon.svg", (_ROOT / "docs" / "assets" / "icon.svg").read_bytes())
            zf.writestr("token-schema.json", (wb / "token-schema.json").read_bytes())
            zf.writestr("skills/geo-optimizer/SKILL.md",
                        skill_md_text("workbuddy").encode("utf-8"))
            for name in SCRIPT_FILES:
                zf.writestr(f"skills/geo-optimizer/scripts/{name}",
                            (SKILL_SRC / "scripts" / name).read_bytes())
    return buf.getvalue()


def frontmatter_of(text: str) -> dict:
    """解析 SKILL.md 文本的 frontmatter（供校验与测试）。"""
    fm_raw, _ = _split_frontmatter(text)
    return yaml.safe_load(fm_raw)
