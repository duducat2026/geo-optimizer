# -*- coding: utf-8 -*-
"""改进方案条目生成：LLM 一次生成中英两段并拆分成两份内容，失败回退内置双语模板。"""
import logging
import re
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import urlparse

from geo_optimizer.web.portal.extensions import db
from geo_optimizer.web.portal.models import EvalTask, PlanItem
from geo_optimizer.web.portal.planitems.catalog import ITEMS
from geo_optimizer.web.portal.tasks.report_builder import label as audit_label

logger = logging.getLogger(__name__)

# 改进方案条目的 LLM 内容生成并发数（各条目相互独立，可并行调用 LLM）
_PLAN_MAX_WORKERS = 5

# 中英分段标记：提示词要求模型单独一行输出 ===EN===
LANG_SPLIT = "===EN==="

_SPLIT_MARKER_RE = re.compile(r"^[ \t]*=+[ \t]*EN[ \t]*[:：]?[ \t]*=+[ \t]*$", re.I | re.M)
_EN_HEADING_RE = re.compile(
    r"^[ \t]*(?:#{1,3}|##)[ \t]+(English(?:[ \t]+(?:Part|Section))?|英文部分)[ \t]*$",
    re.I | re.M)

_PROMPT = """你是资深 GEO（生成式引擎优化）顾问。请为下面的网站生成一份可直接执行的
「{title_zh}」操作文档，Markdown 格式。

输出必须严格分成两段，中间单独一行写 {split}，两段之外不要任何说明：
- 第 1 段（中文）：目标、前置准备、逐步操作步骤（编号列表）、验收标准、注意事项。
- 第 2 段（English）：同一内容的英文版，小节依次为 Objective、Preparation、
  Steps（编号列表）、Acceptance、Notes；信息须与中文段一一对应。

网站信息：
- URL: {url}
- 域名: {domain}
- GEO 综合评分: {score}/100
- 检测到的主要问题: {issues}

要求：步骤具体到可操作（含平台入口地址），结合该站点的评分与问题给出针对性提示，
中文段控制在 600 字以内，英文段与之对应，不要输出与该任务无关的内容。"""


def generate_for_task(task_id: str, config: dict, result: dict) -> list[PlanItem]:
    """为任务生成 9 项条目（LLM 个性化，逐项失败回退模板），落库并返回。"""
    task = db.session.get(EvalTask, task_id)
    if not task:
        return []

    ctx = _build_ctx(task.target_url, result)
    client, model = _make_client(config)

    # 各条目的 LLM 内容生成相互独立，先以最多 5 并发生成全部内容（纯网络调用），
    # 再在主线程串行落库（SQLAlchemy session 非线程安全）。
    contents = _generate_contents(client, model, ctx)

    items = []
    for spec in ITEMS:
        zh_content, en_content, source = contents[spec["code"]]
        item = PlanItem(
            task_id=task_id,
            user_id=task.user_id,
            code=spec["code"],
            priority=spec["priority"],
            title=spec["title"]["zh"],
            content=zh_content,
            content_en=en_content,
            source=source,
        )
        db.session.add(item)
        items.append(item)

    db.session.commit()
    return items


def _generate_contents(client, model: str, ctx: dict) -> dict:
    """并发为所有条目生成中英内容，返回 {code: (zh, en, source)}。

    无可用 LLM 客户端时全部回退模板；否则以 _PLAN_MAX_WORKERS 并发调用 LLM，
    单条目失败或返回空内容时回退该条目的内置模板（不影响其余条目）。
    """
    if client is None:
        return {spec["code"]: (*render_fallback(spec, ctx), "template") for spec in ITEMS}

    def _one(spec: dict):
        try:
            raw = _llm_generate(client, model, spec, ctx)
            if raw:
                zh, en = split_bilingual(raw)
                if zh.strip():
                    if not en.strip():
                        # 模型没给英文段时用模板英文稿兜底，保证 en/ 不混入中文
                        en = render_fallback(spec, ctx)[1]
                        logger.info("LLM 未输出英文段，%s 回退模板英文稿", spec["code"])
                    return spec["code"], zh, en, "llm"
        except Exception as exc:  # noqa: BLE001
            logger.warning("LLM 生成 %s 失败，回退模板: %s", spec["code"], exc)
        zh, en = render_fallback(spec, ctx)
        return spec["code"], zh, en, "template"

    with ThreadPoolExecutor(max_workers=_PLAN_MAX_WORKERS) as executor:
        return {code: (zh, en, source)
                for code, zh, en, source in executor.map(_one, ITEMS)}


def split_bilingual(text: str) -> tuple[str, str]:
    """把一次 LLM 输出拆成中英两段。

    依次尝试：显式 ===EN=== 标记 → 英文小节标题（如 `## English Part`）→
    判定为纯中文稿。拆不出英文段时返回空英文，由打包环节回退使用中文稿。
    """
    text = text.strip()
    m = _SPLIT_MARKER_RE.search(text)
    if m:
        return text[:m.start()].strip(), text[m.end():].strip()

    m = _EN_HEADING_RE.search(text)
    if m and m.start() > 0:
        return text[:m.start()].strip(), text[m.start():].strip()

    return text, ""


def render_fallback(spec: dict, ctx: dict) -> tuple[str, str]:
    """内置双语模板渲染，返回 (中文稿, 英文稿)。"""
    zh_lines = [
        f"# {spec['title']['zh']}",
        "",
        f"**站点:** {ctx['url']}（{ctx['domain']}）",
        f"**当前 GEO 评分:** {ctx['score']}/100",
        f"**检测到的问题:** {ctx['issues'] or '-'}",
        "",
        "## 目标",
        f"- {spec['goal']['zh']}",
        "",
        "## 操作步骤",
    ]
    for i, step in enumerate(spec["steps"], 1):
        zh_lines.append(f"{i}. {step['zh']}")
    zh_lines += [
        "",
        "## 验收标准",
        "- 完成上述步骤后，在对应平台确认站点/内容状态为已收录或已发布。",
    ]

    en_lines = [
        f"# {spec['title']['en']}",
        "",
        f"**Site:** {ctx['url']} ({ctx['domain']})",
        f"**Current GEO score:** {ctx['score']}/100",
        f"**Detected issues:** {ctx['issues'] or '-'}",
        "",
        "## Goal",
        f"- {spec['goal']['en']}",
        "",
        "## Steps",
    ]
    for i, step in enumerate(spec["steps"], 1):
        en_lines.append(f"{i}. {step['en']}")
    en_lines += [
        "",
        "## Acceptance",
        "- After finishing the steps, confirm the site/content is indexed or published.",
    ]
    return "\n".join(zh_lines), "\n".join(en_lines)


def write_to_dir(items: list[PlanItem], target_dir: Path) -> None:
    """将条目初版写入产物目录（进入主 ZIP）：中文稿 + `.en` 英文稿。

    没有独立英文稿（历史数据）时不写 `.en` 文件，避免把中文稿放进包内 en/ 目录。
    """
    from geo_optimizer.web.portal.packaging.layout import plan_item_name

    target_dir = Path(target_dir)
    target_dir.mkdir(parents=True, exist_ok=True)
    for item in items:
        stem = f"{item.priority}_{item.code}"
        (target_dir / plan_item_name(stem, "zh")).write_text(item.content, encoding="utf-8")
        if item.has_en:
            (target_dir / plan_item_name(stem, "en")).write_text(
                item.content_en, encoding="utf-8")


def _build_ctx(url: str, result: dict) -> dict:
    audit = result.get("page_audit") or {}
    issues = ", ".join(audit_label(k) for k in audit.get("issues", []))
    return {
        "url": url,
        "domain": urlparse(url).netloc or url,
        "score": result.get("overall_score", 0),
        "issues": issues,
    }


def _make_client(config: dict):
    """构造 OpenAI 兼容客户端；无 key 时返回 (None, "")。

    显式设置超时与重试次数，避免端点无响应时单次调用挂起数十分钟
    导致任务被卡死巡检误杀（openai SDK 默认 600s + 2 次重试）。
    """
    llm = config.get("llm", {})
    api_key, base_url = llm.get("api_key", ""), llm.get("base_url", "")
    if not api_key or not base_url:
        return None, ""
    try:
        from openai import OpenAI

        return (OpenAI(api_key=api_key, base_url=base_url, timeout=60, max_retries=1),
                llm.get("model", "qwen-plus"))
    except Exception as exc:  # noqa: BLE001
        logger.warning("LLM 客户端初始化失败: %s", exc)
        return None, ""


def _is_connection_error(exc: Exception) -> bool:
    """连接/超时类错误：端点不可达时应快速降级，避免逐条重复等待。"""
    try:
        from openai import APIConnectionError

        return isinstance(exc, APIConnectionError)
    except ImportError:
        return False


def _llm_generate(client, model: str, spec: dict, ctx: dict) -> str:
    prompt = _PROMPT.format(title_zh=spec["title"]["zh"], split=LANG_SPLIT, **ctx)
    resp = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.5,
        max_tokens=2000,
    )
    content = (resp.choices[0].message.content or "").strip()
    # 去掉可能的 ```markdown 包裹
    content = re.sub(r"^```(?:markdown)?\s*|\s*```$", "", content)
    return content.strip()
