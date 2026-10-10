#!/usr/bin/env python3
"""
GEO-Optimizer Skill Client — 面向 AI Agent 的平台调用客户端（CLI 入口）。

模块拆分（单文件不超过 300 行）:
    geo_skill_common.py  配置解析、工具函数与异常定义
    geo_skill_api.py     GeoSkillClient 类（平台开放 API 封装）
    geo_skill_client.py  CLI 入口（本文件，兼容旧版导入路径）

用法（库）:
    from geo_skill_client import GeoSkillClient

    client = GeoSkillClient.from_config()  # 自动从环境变量 / config.json 解析
    task_id = client.submit("https://www.aliyun.com")  # 默认 plan（评估+方案生成）
    result = client.wait_and_get_result(task_id, timeout=600)

CLI（智能体分步模式，每条命令立即返回不阻塞，不做定时轮询）:
    python scripts/geo_skill_client.py --url www.aliyun.com       # 提交后立即返回
    python scripts/geo_skill_client.py --recent                   # 列出最近任务供澄清
    python scripts/geo_skill_client.py --progress <task_id>       # 查询状态+已产生日志
"""
import functools
import json
import os
from typing import Optional

# 兼容旧版导入路径: from geo_skill_client import GeoSkillClient / GeoSkillError ...
from geo_skill_common import (  # noqa: F401
    DEFAULT_BASE_URL,
    DEFAULT_POLL_INTERVAL,
    ESTIMATED_MINUTES,
    GeoSkillError,
    client_log,
    format_log_entry,
    load_config,
    normalize_url,
    resolve_credentials,
    resolve_poll_interval,
)
from geo_skill_api import GeoSkillClient  # noqa: F401

# 智能体/管道环境双保险：每条 print 强制刷新，避免进度摊到进程结束才输出
print = functools.partial(print, flush=True)


def _print_result_summary(result: dict) -> None:
    """任务到达终态后，在控制台展示最终结果摘要（中文）。"""
    print(f"\n{'─'*60}")
    print(f"  GEO 综合评分: {result.get('overall_score', 'N/A')}/100")
    detail = result.get("result", {})
    if detail.get("domestic_score") is not None:
        print(f"  国内引擎评分: {detail['domestic_score']}")
    if detail.get("international_score") is not None:
        print(f"  国际引擎评分: {detail['international_score']}")
    print(f"{'─'*60}")


def _show_progress(client: GeoSkillClient, task_id: str, after_id: int,
                   output_path: Optional[str], as_json: bool) -> None:
    """查询任务进展：返回当前状态 + 已产生的云端日志后立即返回（不阻塞）。

    由使用人员发起查询（不做定时轮询）。已完成时返回结果信息，
    含“生成与改进方案”免登录下载链接；指定 --output 时直接下载压缩包。
    """
    client_log(f"查询任务进展 {task_id} (增量日志起点 after_id={after_id})")
    last_id = after_id
    # 增量拉取云端执行日志（旧版服务端无此端点时静默降级）
    try:
        log_data = client.get_logs(task_id, after_id=after_id)
        for entry in log_data.get("logs", []):
            print(format_log_entry(entry))
        last_id = log_data.get("last_id", after_id)
    except GeoSkillError:
        pass

    data = client.get_status(task_id)
    status = data.get("status")
    progress = data.get("progress", 0)

    if status == "completed":
        print(f"  [已完成] GEO 综合评分: {data.get('overall_score', 'N/A')}")
        result = client.get_result(task_id)
        _print_result_summary(result)
        # “生成与改进方案”下载：优先免登录分享链接；--output 时直接下载压缩包
        share_url = result.get("share_download_url")
        if share_url:
            print(f"  [下载链接] 生成与改进方案（免登录，可直接分享）: {share_url}")
        download_path = None
        if result.get("download_url") and output_path:
            download_path = str(client.download(task_id, output_path))
        if as_json:
            print(json.dumps({
                "task_id": task_id, "status": status, "last_log_id": last_id,
                "overall_score": result.get("overall_score"),
                "share_download_url": share_url,
                "download_path": download_path,
            }, ensure_ascii=False, indent=2))
    elif status == "failed":
        print(f"  [失败] 任务执行失败: {data.get('error') or data.get('message', '')}")
    elif status == "cancelled":
        print("  [已取消] 任务已被取消")
    elif status == "queued":
        print(f"  [排队中] 排队位置 #{data.get('queue_position', '?')} | 进度 {progress}%")
    else:
        print(f"  [进行中] 进度 {progress}% | {data.get('message', '')}")

    if status not in ("completed",) and as_json:
        print(json.dumps({
            "task_id": task_id, "status": status, "progress": progress,
            "last_log_id": last_id,
        }, ensure_ascii=False, indent=2))
    if status not in ("completed", "failed", "cancelled"):
        print(f"  [提示] 任务尚未结束，可稍后由使用人员再次发起查询: "
              f"--progress {task_id} --after-id {last_id}")


def _list_recent(client: GeoSkillClient, as_json: bool, limit: int = 10,
                 page: int = 1, start: str = None, end: str = None) -> None:
    """列出当前 API-KEY 用户最近提交的任务（总数 + 分页 + 日期范围）。"""
    data = client.list_tasks(limit=limit, page=page, start=start, end=end)
    tasks = data.get("tasks", [])
    total = data.get("total", len(tasks))
    cur, pages = data.get("page", page), data.get("pages", 1)
    rng = (f"（日期 {start or '不限'} ~ {end or '不限'}）"
           if (start or end) else "")
    if not tasks:
        print(f"  当前账号在该条件下暂无提交记录{rng}")
    else:
        print(f"  当前账号共 {total} 个任务{rng}，第 {cur}/{pages} 页，本页 "
              f"{len(tasks)} 条（任务 ID 完整展示，可直接用于查询）:")
        for i, t in enumerate(tasks, 1):
            created = (t.get("created_at") or "")[:19].replace("T", " ")
            print(f"  {(cur - 1) * limit + i}. 任务 ID: {t['task_id']}")
            print(f"     评估网站: {t['target_url']} | 状态: {t['status']}"
                  f" | 进度 {t.get('progress', 0)}% | 提交时间: {created}")
        print("  [提示] 翻页用 --recent --page <页码>；可加 --start/--end 限定日期；"
              "再用 --progress <完整任务ID> 查询进展或获取结果")
    if as_json:
        print(json.dumps(data, ensure_ascii=False, indent=2))


def _run_blocking(client: GeoSkillClient, args) -> None:
    """阻塞式完整流程（--wait）: 提交 → 等待完成 → 摘要 → 下载，仅适合交互终端。"""
    print(f"\n{'='*60}")
    print(f"GEO-Optimizer 网站分析: {args.url}")
    print(f"任务类型: {args.type} | 最大等待: {args.timeout} 秒")
    print(f"{'='*60}\n")

    task_id = client.submit(args.url, task_type=args.type)
    result = client.wait_and_get_result(task_id, timeout=args.timeout)
    _print_result_summary(result)

    download_path = None
    if result.get("download_url") and args.output:
        download_path = str(client.download(task_id, args.output))
    elif result.get("download_url"):
        print("  [提示] 有可下载的报告包，但未指定 --output")

    if args.json:
        print(json.dumps({
            "task_id": task_id,
            "overall_score": result.get("overall_score"),
            "download_path": download_path,
        }, ensure_ascii=False, indent=2))

    usage = client.get_usage()
    print(f"\n  [统计] API 累计调用次数: {usage.get('total_calls', 0)}")
    print("\n分析完成！")


def main():
    """命令行入口。默认提交后立即返回（不阻塞），由调用方分步轮询。"""
    import argparse

    parser = argparse.ArgumentParser(
        description="GEO-Optimizer Skill Client — AI 搜索引擎 GEO 评估",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
凭据可省略: 自动从环境变量 GEO_API_KEY/GEO_BASE_URL 或技能根目录 config.json 读取。

示例（智能体分步模式，默认每条命令立即返回，不做定时轮询）:
  提交:   python scripts/geo_skill_client.py --url www.aliyun.com
  列最近: python scripts/geo_skill_client.py --recent
  查进展: python scripts/geo_skill_client.py --progress <task_id> --after-id 0
  查状态: python scripts/geo_skill_client.py --status <task_id>
  终止:   python scripts/geo_skill_client.py --cancel <task_id>
  下载:   python scripts/geo_skill_client.py --progress <task_id> --output report.zip
  交互阻塞(智能体勿用): python scripts/geo_skill_client.py --url www.aliyun.com --wait
        """,
    )
    parser.add_argument("--base-url", default=None,
                        help="平台服务地址（默认从 GEO_BASE_URL/config.json 解析）")
    parser.add_argument("--api-key", default=None,
                        help="API 密钥 geo_ 开头（默认从 GEO_API_KEY/config.json 解析）")
    parser.add_argument("--url", help="目标网站 URL（裸域名自动补全 https:// 前缀）")
    parser.add_argument("--type", default="plan", choices=["eval", "plan"],
                        help="任务类型: eval=仅评分, plan=评估+方案生成 (默认 plan)")
    parser.add_argument("--output", help="报告 ZIP 保存路径")
    parser.add_argument("--timeout", type=int, default=600,
                        help="--wait 阻塞模式的最大等待秒数 (default: 600)")
    parser.add_argument("--poll-interval", type=float, default=None,
                        help="轮询间隔秒数（默认从 GEO_POLL_INTERVAL/config.json 解析，未配置时 6 秒）")
    parser.add_argument("--wait", action="store_true",
                        help="阻塞等待任务完成（仅交互终端使用；智能体环境勿用，默认提交后立即返回）")
    parser.add_argument("--submit-only", action="store_true",
                        help="[兼容保留] 仅提交任务后立即返回（现已是默认行为）")
    parser.add_argument("--recent", action="store_true",
                        help="列出当前账号最近提交的任务（总数+分页），供澄清查询哪个任务")
    parser.add_argument("--limit", type=int, default=10,
                        help="--recent 每页条数（1-50，默认 10）")
    parser.add_argument("--page", type=int, default=1,
                        help="--recent 页码（从 1 开始）")
    parser.add_argument("--start",
                        help="--recent 起始日期/时间过滤（如 2026-07-01 或 2026-07-01T00:00）")
    parser.add_argument("--end",
                        help="--recent 结束日期/时间过滤（纯日期含当天，如 2026-07-31）")
    parser.add_argument("--progress", metavar="TASK_ID",
                        help="查询指定任务进展：返回状态与已产生日志；已完成时返回结果与下载链接")
    parser.add_argument("--poll", metavar="TASK_ID",
                        help="[兼容保留] 等同 --progress")
    parser.add_argument("--after-id", type=int, default=0,
                        help="配合 --progress: 只拉取 id 大于此值的新日志（用上次输出的 last_id）")
    parser.add_argument("--status", metavar="TASK_ID",
                        help="查询指定任务状态（不提交新任务）")
    parser.add_argument("--cancel", metavar="TASK_ID",
                        help="终止指定任务（排队中/运行中均可；已结束的任务无法终止）")
    parser.add_argument("--json", action="store_true",
                        help="以 JSON 格式输出结果")
    args = parser.parse_args()

    # CLI 显式指定轮询间隔时注入环境变量，统一生效到提交提示/轮询/下次查询提示
    if args.poll_interval:
        os.environ["GEO_POLL_INTERVAL"] = str(args.poll_interval)

    base_url, api_key = resolve_credentials(args.base_url, args.api_key)
    if not api_key or api_key.startswith("<"):
        parser.error(
            "未找到 API 密钥: 请传入 --api-key、设置环境变量 GEO_API_KEY，"
            "或在技能根目录提供 config.json"
        )
    # 密钥仅展示前缀，避免明文落入智能体控制台
    client_log(f"凭据解析完成: 平台 {base_url} | 密钥 {api_key[:8]}***")

    with GeoSkillClient(base_url, api_key) as client:
        # 最近任务列表（供使用人员澄清查询哪个任务）
        if args.recent:
            _list_recent(client, args.json, limit=args.limit, page=args.page,
                         start=args.start, end=args.end)
            return

        # 任务终止（排队中/运行中均可；运行中为协作式取消，到下个检查点生效）
        if args.cancel:
            try:
                data = client.cancel(args.cancel)
            except GeoSkillError as exc:
                # 已完成/失败/已取消等终态无法终止（409），以及不存在/越权
                print(f"  [终止失败] {exc.message or exc.error}")
                return
            print(f"  [终止] 任务 {data.get('task_id')} 状态: {data.get('status')}"
                  f" | {data.get('message', '')}")
            if args.json:
                print(json.dumps(data, ensure_ascii=False, indent=2))
            return

        # 查询模式
        if args.status:
            data = client.get_status(args.status)
            if args.json:
                print(json.dumps(data, ensure_ascii=False, indent=2))
            else:
                print(f"任务 ID: {data.get('task_id')}")
                print(f"状态: {data.get('status')}")
                print(f"进度: {data.get('progress')}%")
                print(f"评分: {data.get('overall_score', 'N/A')}")
                print(f"消息: {data.get('message', '')}")
            return

        # 任务进展查询（由使用人员发起，进程立即返回不阻塞；--poll 为兼容别名）
        progress_id = args.progress or args.poll
        if progress_id:
            _show_progress(client, progress_id, args.after_id, args.output, args.json)
            return

        # 提交模式
        if not args.url:
            parser.error("提交新任务时必须提供 --url")

        # 显式 --wait 才阻塞等待；默认提交后立即返回，避免智能体环境卡在“处理中”
        if args.wait:
            _run_blocking(client, args)
            return

        task_id = client.submit(args.url, task_type=args.type)
        # 不做定时轮询；进展查询由使用人员发起（--recent / --progress）
        if args.json:
            print(json.dumps({"task_id": task_id}, ensure_ascii=False))


if __name__ == "__main__":
    main()
