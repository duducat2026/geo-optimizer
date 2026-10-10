"""
GEO 索引状态检测模块
- site: 查询模拟各引擎收录情况
- HTTPS 证书检测
- robots.txt 解析与 AI 爬虫规则验证
- Sitemap.xml 有效性检查
"""

import logging
import ssl
import socket
import re
from dataclasses import dataclass, field
from typing import List, Dict, Optional
from urllib.parse import urljoin, urlparse

import httpx

logger = logging.getLogger(__name__)


# AI 爬虫 User-Agent 列表
AI_BOT_AGENTS = {
    "GPTBot": "OpenAI (ChatGPT)",
    "CCBot": "Common Crawl",
    "Claude-Web": "Anthropic (Claude)",
    "ClaudeBot": "Anthropic (Claude)",
    "PerplexityBot": "Perplexity AI",
    "Google-Extended": "Google AI Overviews",
    "Applebot-Extended": "Apple AI",
    "OAI-SearchBot": "OpenAI Search",
    "anthropic-ai": "Anthropic AI",
    "Bytespider": "字节跳动",
}

# 主流搜索引擎 site: 查询 URL 模板
SITE_QUERY_TEMPLATES = {
    "google": "https://www.google.com/search?q=site%3A{domain}",
    "bing": "https://www.bing.com/search?q=site%3A{domain}",
    "baidu": "https://www.baidu.com/s?wd=site%3A{domain}",
}


@dataclass
class HTTPSResult:
    has_https: bool
    cert_valid: bool
    cert_issuer: str = ""
    cert_expiry: str = ""
    days_until_expiry: int = 0
    tls_version: str = ""
    issues: List[str] = field(default_factory=list)


@dataclass
class RobotsResult:
    exists: bool
    content: str = ""
    ai_bots_allowed: Dict[str, bool] = field(default_factory=dict)
    sitemap_urls: List[str] = field(default_factory=list)
    issues: List[str] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)


@dataclass
class SitemapResult:
    url: str
    exists: bool
    valid_xml: bool = False
    url_count: int = 0
    sample_urls: List[str] = field(default_factory=list)
    issues: List[str] = field(default_factory=list)


@dataclass
class SiteQueryResult:
    engine: str
    query_url: str
    accessible: bool = False
    estimated_results: Optional[int] = None
    raw_html: str = ""
    issues: List[str] = field(default_factory=list)


@dataclass
class IndexCheckReport:
    domain: str
    https: Optional[HTTPSResult] = None
    robots: Optional[RobotsResult] = None
    sitemaps: List[SitemapResult] = field(default_factory=list)
    site_queries: List[SiteQueryResult] = field(default_factory=list)
    overall_score: float = 0.0
    summary: str = ""


class GEOIndexChecker:
    """索引状态检测器"""

    def __init__(self, domain: str, timeout: int = 15):
        self.domain = domain
        self.base_url = f"https://{domain}"
        self.timeout = timeout
        self.client = httpx.Client(
            timeout=timeout,
            follow_redirects=True,
            headers={"User-Agent": "Mozilla/5.0 (compatible; GEO-Optimizer/1.0)"}
        )

    def check_all(self) -> IndexCheckReport:
        """执行全套索引检测"""
        report = IndexCheckReport(domain=self.domain)

        # 1. HTTPS 检查
        try:
            report.https = self.check_https()
        except Exception as e:
            logger.error(f"HTTPS 检查失败: {e}")
            report.https = HTTPSResult(
                has_https=False,
                cert_valid=False,
                issues=[f"HTTPS 检查异常: {str(e)}"]
            )

        # 2. robots.txt 检查
        try:
            report.robots = self.check_robots()
        except Exception as e:
            logger.error(f"robots.txt 检查失败: {e}")
            report.robots = RobotsResult(
                exists=False,
                issues=[f"robots.txt 检查异常: {str(e)}"]
            )

        # 3. Sitemap 检查
        try:
            sitemaps = self.check_sitemaps()
            report.sitemaps = sitemaps
        except Exception as e:
            logger.error(f"Sitemap 检查失败: {e}")
            report.sitemaps = [SitemapResult(
                url=f"{self.base_url}/sitemap.xml",
                exists=False,
                issues=[f"Sitemap 检查异常: {str(e)}"]
            )]

        # 4. site: 查询
        try:
            report.site_queries = self.check_site_queries()
        except Exception as e:
            logger.error(f"site: 查询失败: {e}")

        # 计算综合评分
        report.overall_score = self._calculate_score(report)
        report.summary = self._generate_summary(report)

        return report

    def check_https(self) -> HTTPSResult:
        """检查 HTTPS 和 SSL 证书"""
        result = HTTPSResult(has_https=False, cert_valid=False)

        # 尝试 HTTPS 连接
        try:
            resp = self.client.get(self.base_url, timeout=self.timeout)
            result.has_https = True
        except httpx.RequestError:
            result.issues.append(f"无法通过 HTTPS 访问 {self.base_url}")

        # 检查 HTTP 是否自动跳转
        try:
            http_url = f"http://{self.domain}"
            resp = httpx.get(http_url, timeout=self.timeout, follow_redirects=False)
            if resp.status_code in (301, 302, 307, 308):
                location = resp.headers.get("location", "")
                if location.startswith("https://"):
                    pass  # Good - redirects to HTTPS
                else:
                    result.issues.append("HTTP 未重定向到 HTTPS")
        except Exception:
            pass

        # SSL 证书检查
        try:
            ctx = ssl.create_default_context()
            with socket.create_connection((self.domain, 443), timeout=self.timeout) as sock:
                with ctx.wrap_socket(sock, server_hostname=self.domain) as ssock:
                    cert = ssock.getpeercert()
                    result.cert_valid = True
                    result.tls_version = ssock.version()

                    # 解析证书信息
                    subject = dict(x[0] for x in cert.get("subject", []))
                    issuer = dict(x[0] for x in cert.get("issuer", []))
                    result.cert_issuer = issuer.get("organizationName", issuer.get("commonName", "Unknown"))

                    not_after = cert.get("notAfter", "")
                    if not_after:
                        result.cert_expiry = not_after
                        # 简单计算天数（approximate）
                        import datetime
                        try:
                            expiry = datetime.datetime.strptime(not_after, "%b %d %H:%M:%S %Y %Z")
                            delta = expiry - datetime.datetime.utcnow()
                            result.days_until_expiry = delta.days
                            if delta.days < 30:
                                result.issues.append(f"SSL 证书即将过期（{delta.days} 天）")
                        except Exception:
                            pass
        except ssl.SSLError as e:
            result.issues.append(f"SSL 证书错误: {str(e)}")
        except Exception as e:
            result.issues.append(f"SSL 检查异常: {str(e)}")

        if not result.has_https:
            result.issues.append("⚠️ 网站没有 HTTPS，AI 搜索引擎可能拒绝收录")

        return result

    def check_robots(self) -> RobotsResult:
        """检查 robots.txt 和 AI 爬虫兼容性"""
        result = RobotsResult(exists=False)
        robots_url = f"{self.base_url}/robots.txt"

        try:
            resp = self.client.get(robots_url, timeout=self.timeout)
            if resp.status_code == 200:
                result.exists = True
                result.content = resp.text
            else:
                result.issues.append(f"robots.txt 返回 HTTP {resp.status_code}")
                return result
        except Exception as e:
            result.issues.append(f"无法获取 robots.txt: {str(e)}")
            return result

        # 解析内容
        lines = result.content.split("\n")
        current_agents = []
        in_sitemap = False

        for line in lines:
            line = line.strip()
            if not line or line.startswith("#"):
                continue

            if line.lower().startswith("user-agent:"):
                agent = line.split(":", 1)[1].strip().lower()
                current_agents = [agent] if agent != "*" else []
            elif line.lower().startswith("sitemap:"):
                sitemap_url = line.split(":", 1)[1].strip()
                result.sitemap_urls.append(sitemap_url)
            elif line.lower().startswith("disallow:"):
                path = line.split(":", 1)[1].strip()
                # 检查是否对所有爬虫 disallow
                for bot_name in AI_BOT_AGENTS:
                    bot_lower = bot_name.lower()
                    if any(bot_lower in a for a in current_agents) or not current_agents:
                        if path == "/" or path == "":
                            result.ai_bots_allowed[bot_name] = False
            elif line.lower().startswith("allow:"):
                path = line.split(":", 1)[1].strip()
                for bot_name in AI_BOT_AGENTS:
                    bot_lower = bot_name.lower()
                    if any(bot_lower in a for a in current_agents) or not current_agents:
                        result.ai_bots_allowed[bot_name] = True

        # 检查每个 AI 爬虫的状态
        for bot_name in AI_BOT_AGENTS:
            if bot_name not in result.ai_bots_allowed:
                # 没有明确规则，默认允许
                result.ai_bots_allowed[bot_name] = True

        # 生成建议
        disallowed_bots = [k for k, v in result.ai_bots_allowed.items() if not v]
        if disallowed_bots:
            bot_display = ", ".join(f"{b} ({AI_BOT_AGENTS[b]})" for b in disallowed_bots)
            result.recommendations.append(
                f"以下 AI 爬虫被禁止抓取: {bot_display}。建议在 robots.txt 中允许这些爬虫。"
            )

        # 检查是否有针对 AI 爬虫的专门规则
        has_ai_rules = any(bot.lower() in result.content.lower() for bot in AI_BOT_AGENTS)
        if not has_ai_rules:
            result.recommendations.append(
                "robots.txt 中没有针对 AI 爬虫的专门规则。建议添加明确的 Allow 规则。"
            )

        # 检查 sitemap 声明
        if not result.sitemap_urls:
            result.recommendations.append(
                "robots.txt 中没有声明 Sitemap。建议添加 Sitemap: https://{domain}/sitemap.xml"
            )

        return result

    def check_sitemaps(self) -> List[SitemapResult]:
        """检查 Sitemap.xml"""
        results = []

        # 常见 sitemap 路径
        candidates = [
            f"{self.base_url}/sitemap.xml",
            f"{self.base_url}/sitemap_index.xml",
            f"{self.base_url}/sitemaps/sitemap.xml",
            f"{self.base_url}/wp-sitemap.xml",
        ]

        for sitemap_url in candidates:
            result = SitemapResult(url=sitemap_url, exists=False)

            try:
                resp = self.client.get(sitemap_url, timeout=self.timeout)
                if resp.status_code == 200:
                    result.exists = True
                    content = resp.text

                    # 简单 XML 验证
                    if "<urlset" in content or "<sitemapindex" in content:
                        result.valid_xml = True

                        # 统计 URL 数量
                        url_count = len(re.findall(r"<loc>([^<]+)</loc>", content))
                        result.url_count = url_count

                        # 提取样例 URL
                        result.sample_urls = re.findall(r"<loc>([^<]+)</loc>", content)[:5]
                    else:
                        result.issues.append("Sitemap 文件格式不是有效的 XML")

                    results.append(result)
                    break  # 找到一个有效的就停止
            except Exception as e:
                result.issues.append(f"无法访问: {str(e)}")
                results.append(result)

        return results

    def check_site_queries(self) -> List[SiteQueryResult]:
        """执行 site: 查询（模拟，受反爬限制）"""
        results = []

        for engine, template in SITE_QUERY_TEMPLATES.items():
            result = SiteQueryResult(
                engine=engine,
                query_url=template.format(domain=self.domain)
            )

            try:
                # 注意：实际可能被反爬，这里只做基础检查
                resp = self.client.get(
                    result.query_url,
                    timeout=self.timeout,
                    follow_redirects=True
                )
                result.accessible = resp.status_code == 200
                result.raw_html = resp.text[:5000]

                # 尝试提取预估结果数
                if engine == "google":
                    match = re.search(r"About ([\d,]+) results", resp.text)
                    if match:
                        result.estimated_results = int(match.group(1).replace(",", ""))
                elif engine == "bing":
                    match = re.search(r"([\d,]+)\s+results", resp.text)
                    if match:
                        result.estimated_results = int(match.group(1).replace(",", ""))
                elif engine == "baidu":
                    match = re.search(r"找到相关结果约?([\d,]+)", resp.text)
                    if match:
                        result.estimated_results = int(match.group(1).replace(",", ""))
            except Exception as e:
                result.issues.append(f"查询异常（可能被反爬）: {str(e)}")

            results.append(result)

        return results

    def _calculate_score(self, report: IndexCheckReport) -> float:
        """计算索引健康度评分 (0-100)"""
        score = 0.0
        max_score = 100

        # HTTPS (30 分)
        if report.https:
            if report.https.has_https:
                score += 20
            if report.https.cert_valid:
                score += 10

        # robots.txt (25 分)
        if report.robots:
            if report.robots.exists:
                score += 10
            # AI 爬虫允许情况
            allowed_count = sum(1 for v in report.robots.ai_bots_allowed.values() if v)
            total_bots = len(report.robots.ai_bots_allowed)
            if total_bots > 0:
                score += 15 * (allowed_count / total_bots)

        # Sitemap (25 分)
        for sm in report.sitemaps:
            if sm.exists and sm.valid_xml:
                score += 20
                if sm.url_count > 0:
                    score += 5
                break

        # site: 查询 (20 分)
        for sq in report.site_queries:
            if sq.accessible and sq.estimated_results and sq.estimated_results > 0:
                score += 20 / len(report.site_queries)
                break

        return min(round(score, 1), max_score)

    def _generate_summary(self, report: IndexCheckReport) -> str:
        """生成检测摘要"""
        parts = []

        if report.https:
            if report.https.has_https:
                parts.append(f"✅ HTTPS 正常 ({report.https.tls_version})")
            else:
                parts.append("❌ 未启用 HTTPS — AI 搜索引擎可能拒绝收录")

        if report.robots:
            allowed = sum(1 for v in report.robots.ai_bots_allowed.values() if v)
            total = len(report.robots.ai_bots_allowed)
            parts.append(f"📋 robots.txt: {'存在' if report.robots.exists else '不存在'} ({allowed}/{total} AI 爬虫允许)")

        valid_sm = [s for s in report.sitemaps if s.exists and s.valid_xml]
        if valid_sm:
            parts.append(f"🗺️ Sitemap 有效 ({valid_sm[0].url_count} 个 URL)")
        else:
            parts.append("⚠️ 未找到有效 Sitemap")

        indexed = [q for q in report.site_queries if q.estimated_results and q.estimated_results > 0]
        if indexed:
            total_idx = sum(q.estimated_results for q in indexed)
            parts.append(f"🔍 搜索引擎收录约 {total_idx:,} 页")
        else:
            parts.append("⚠️ 未检测到搜索引擎收录（可能受反爬限制）")

        parts.append(f"\n综合评分: {report.overall_score}/100")

        return "\n".join(parts)

    def close(self):
        """关闭 HTTP 客户端"""
        self.client.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()