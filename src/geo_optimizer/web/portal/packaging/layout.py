# -*- coding: utf-8 -*-
"""双语包布局：把任务产物归档为包内 zh/ 与 en/ 两套文件 + 根目录双语 README。

磁盘上的产物目录保持扁平（单文件下载、产出物预览等既有行为不变），
只在打 ZIP 时重排归档名，因此两个下载入口共用本模块的规则：

- packaging/bundler.bundle_task —— 任务主 ZIP（评估报告 + 方案 + 站点派生内容）
- planitems/routes.bundle_download —— 改进方案打包下载

平台发布稿只归档到其**目标平台语言**侧（知乎/公众号/头条进 zh/，
Medium/Quora/Wikipedia 进 en/），不生成无法直接发布的译文稿。
"""
from pathlib import Path

LANGS = ("zh", "en")

# 报告与 Schema 的中英文件名（磁盘名 → 包内名）
REPORT_MD_ZH = "geo_analysis_report.md"
REPORT_MD_EN = "geo_analysis_report.en.md"
REPORT_PDF_ZH = "geo_analysis_report.pdf"
REPORT_PDF_EN = "geo_analysis_report.en.pdf"
SCHEMA_ZH = "schema.jsonld.html"
SCHEMA_EN = "schema.jsonld.en.html"
# 双语 FAQ 拆分后的包内文件名（两侧同名，各自单语）
FAQ_MD_NAME = "faq.md"

# 磁盘扁平名 → 包内名（英文侧沿用中文文件名，靠目录区分语言）
_DISK_TO_PKG = {
    REPORT_MD_ZH: f"zh/{REPORT_MD_ZH}",
    REPORT_MD_EN: f"en/{REPORT_MD_ZH}",
    REPORT_PDF_ZH: f"zh/{REPORT_PDF_ZH}",
    REPORT_PDF_EN: f"en/{REPORT_PDF_ZH}",
    SCHEMA_ZH: f"zh/{SCHEMA_ZH}",
    SCHEMA_EN: f"en/{SCHEMA_ZH}",
}

# 国内平台草稿前缀（进 zh/）
ZH_PLATFORM_PREFIXES = ("wechat_", "zhihu_", "toutiao_", "baijiahao_")
# 国外平台草稿前缀（进 en/）
EN_PLATFORM_PREFIXES = ("medium_", "quora_", "reddit_")

# FAQ Markdown 中的英文段落起始标记（faq_generator.format_faqs_to_markdown）
_FAQ_EN_MARK = "## English FAQ"
_FAQ_ZH_MARK = "## 中文 FAQ"


def report_names(lang: str) -> tuple[str, str]:
    """返回 (markdown 文件名, pdf 文件名)，lang 为 zh 时沿用既有命名。"""
    if lang == "en":
        return REPORT_MD_EN, REPORT_PDF_EN
    return REPORT_MD_ZH, REPORT_PDF_ZH


def schema_name(lang: str) -> str:
    return SCHEMA_EN if lang == "en" else SCHEMA_ZH


def report_arcnames(lang: str) -> tuple[str, str]:
    """报告在包内的归档名 (markdown, pdf)，同侧目录内统一用中文名。"""
    return (_DISK_TO_PKG[report_names(lang)[0]], _DISK_TO_PKG[report_names(lang)[1]])


def pkg_name_of(disk_name: str) -> str:
    """磁盘扁平名对应的包内规范名（含语言目录前缀）。"""
    return _DISK_TO_PKG.get(disk_name, disk_name)


def plan_item_name(stem: str, lang: str) -> str:
    """方案条目磁盘名：中文沿用 `<priority>_<code>.md`，英文加 `.en` 段。"""
    return f"{stem}.en.md" if lang == "en" else f"{stem}.md"


def artifact_lang(kind: str) -> str:
    """产出物规格的目标语言（规则类为中性 neutral）。"""
    from geo_optimizer.web.portal.planitems import artifact_catalog

    spec = artifact_catalog.get_spec_by_kind(kind)
    if spec is None:
        return "neutral"
    return spec.get("lang", "neutral")


def arcname_for(rel: str) -> str:
    """把产物目录内的相对路径映射为 ZIP 归档名；中性文件留在根目录。"""
    pure = Path(rel)
    name, parts = pure.name, pure.parts

    if name in _DISK_TO_PKG:
        return _DISK_TO_PKG[name]

    if parts and parts[0] == "plan_items":
        if name.endswith(".en.md"):
            return f"en/plan_items/{name[:-len('.en.md')]}.md"
        return f"zh/plan_items/{name}"

    if name.endswith("_faq.md"):
        return "faq.md"          # 调用方按语言拆分后写入 zh/ en/

    if name.startswith(ZH_PLATFORM_PREFIXES):
        return f"zh/{name}"
    if name.startswith(EN_PLATFORM_PREFIXES):
        return f"en/{name}"

    return pure.as_posix()


def artifact_arcname(kind: str, filename: str) -> str:
    """改进方案产出物的归档名。"""
    lang = artifact_lang(kind)
    prefix = f"{lang}/" if lang in LANGS else ""
    return f"{prefix}artifacts/{filename}"


def plan_item_arcname(item) -> tuple[str, str]:
    """方案条目的中英归档名 (zh, en)。"""
    stem = f"{item.priority}_{item.code}"
    return (f"zh/plan_items/{stem}.md", f"en/plan_items/{stem}.md")


def split_faq(text: str) -> tuple[str, str]:
    """把双语 FAQ Markdown 拆成中英两段（找不到标记时整份归中文）。"""
    idx = text.find(_FAQ_EN_MARK)
    if idx < 0:
        return text, ""
    zh_part = text[:idx]
    en_part = text[idx:]
    if _FAQ_ZH_MARK in zh_part:
        zh_part = zh_part.replace(_FAQ_ZH_MARK, "# FAQ (Chinese)", 1)
    en_part = en_part.replace(_FAQ_EN_MARK, "# FAQ (English)", 1)
    return zh_part.rstrip() + "\n", en_part.rstrip() + "\n"


def new_stats() -> dict:
    """归档统计累加器（供 README 生成与两个下载入口共用）。"""
    return {"zh": 0, "en": 0, "root": 0, "entries": []}


def record(stats: dict, arcname: str) -> str:
    """记录一个已写入 ZIP 的归档名，返回原归档名。"""
    top = arcname.split("/", 1)[0]
    stats[top if top in LANGS else "root"] += 1
    stats["entries"].append(arcname)
    return arcname


def pack_artifact_dir(zf, artifact_dir) -> dict:
    """把产物目录按双语布局写入已打开的 ZipFile，返回统计信息。"""
    artifact_dir = Path(artifact_dir)
    files = sorted(
        p for p in artifact_dir.rglob("*")
        if p.is_file() and p.suffix.lower() != ".zip"
    )
    stats = new_stats()

    for f in files:
        rel = f.relative_to(artifact_dir).as_posix()
        if f.name.endswith("_faq.md"):
            zh_text, en_text = split_faq(f.read_text(encoding="utf-8", errors="ignore"))
            if zh_text.strip():
                record(stats, _write(zf, f"zh/{FAQ_MD_NAME}", zh_text))
            if en_text.strip():
                record(stats, _write(zf, f"en/{FAQ_MD_NAME}", en_text))
            continue
        record(stats, zf_write_file(zf, f, arcname_for(rel)))

    return stats


def item_texts(item) -> dict:
    """方案条目在各语言侧的正文。

    历史任务没有独立英文段落（`content_en` 为空），其中英合稿只归入 `zh/`，
    保证老包不丢内容也不产生重复文件；新任务两侧各一份。
    """
    if item.has_en:
        return {"zh": item.content or "", "en": item.content_en or ""}
    return {"zh": item.content or ""}


def _write(zf, arcname: str, text: str) -> str:
    zf.writestr(arcname, text.encode("utf-8"))
    return arcname


def zf_write_file(zf, path: Path, arcname: str) -> str:
    zf.write(path, arcname=arcname)
    return arcname


def readme_text(stats: dict, target_url: str = "") -> str:
    """生成包根目录的双语 README（中文段 + English 段）。"""
    entries = sorted(stats.get("entries") or [])
    lines = [
        "# GEO-Optimizer 方案包 / GEO Plan Package",
        "",
        f"**站点 / Site:** {target_url or '-'}",
        "",
        "本包按语言分目录存放：`zh/` 为中文，`en/` 为英文，"
        "根目录文件为语言中性的数据或代码。",
        "",
        "Files are grouped by language: `zh/` for Chinese, `en/` for English. "
        "Files at the package root are language-neutral data or code.",
        "",
        "## 目录结构 / Structure",
        "",
        "```",
        "├── README.md                    双语索引（本文件）",
        "├── zh/                          中文版报告、方案条目、FAQ 与国内平台稿",
        "├── en/                          English reports, plan items, FAQ, overseas drafts",
        "├── artifacts/                   规则类产出物（sitemap/robots，语言中性）",
        "├── page_snapshot.json           页面抓取快照（数据）",
        "├── <slug>.html                  增强后的页面（保持站点原语言）",
        "├── <slug>_schema.json           JSON-LD 数据（站点原语言）",
        "└── <slug>_authority.md          权威画像素材",
        "```",
        "",
        "## 建议处理顺序 / Suggested order",
        "",
        "1. 读 `zh/geo_analysis_report.md`（或 `en/` 同名文件）了解短板。",
        "2. 按 `zh/plan_items/` 内 high → mid → low 顺序执行。",
        "3. 嵌入 `zh/schema.jsonld.html` 与 `zh/faq.md`。",
        "4. 国内平台稿在 `zh/`，海外平台稿在 `en/`，均为可直接发布草稿。",
        "",
        "1. Read `en/geo_analysis_report.md` to see the gaps.",
        "2. Work through `en/plan_items/` from high to low priority.",
        "3. Embed `en/schema.jsonld.html` and `en/faq.md`.",
        "4. Overseas drafts live in `en/`; Chinese-platform drafts in `zh/` — "
        "both are ready to publish.",
        "",
        "> 说明 / Note: 平台发布稿只生成在其目标平台语言下，"
        "> 因此 `zh/` 含知乎/公众号/头条稿，`en/` 含 Medium/Quora/Reddit 稿。",
        "> Platform drafts are generated only in the language of their target "
        "platform, so `zh/` holds Zhihu/WeChat/Toutiao drafts while `en/` holds "
        "Medium/Quora/Reddit drafts.",
        "",
        "## 开源与自建 / Open source",
        "",
        "AGPL-3.0 · <https://github.com/duducat2026/geo-optimizer>",
        "",
        "## 包内文件清单 / File inventory",
        "",
    ]
    lines += [f"- `{e}`" for e in entries] or ["- (empty)"]
    lines += [
        "",
        f"**统计 / Totals:** 中文 {stats.get('zh', 0)} · English {stats.get('en', 0)} "
        f"· 中性 {stats.get('root', 0)}",
        "",
    ]
    return "\n".join(lines)
