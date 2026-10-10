#!/usr/bin/env python3
"""
authority_builder.py — 权威性补充
国内：机构背书、参考文献、备案号
国外：E-E-A-T、ORCID、DOI、author bio
"""

import logging
from dataclasses import dataclass, field
from typing import Optional

from geo_optimizer.config import load_config
from geo_optimizer.crawler import CrawledPage
from geo_optimizer.web.faq_generator import FAQ

logger = logging.getLogger(__name__)


@dataclass
class AuthorityProfile:
    """权威性画像"""
    author_name: str = ""
    author_title: str = ""
    author_bio: str = ""
    author_orcid: str = ""          # 国外学术标识
    organization: str = ""
    org_description: str = ""
    credentials: list = field(default_factory=list)   # 资质/认证
    references: list = field(default_factory=list)     # 参考文献
    data_sources: list = field(default_factory=list)   # 数据来源
    certifications: list = field(default_factory=list) # 认证/备案号
    icp_number: str = ""            # 国内ICP备案
    social_profiles: list = field(default_factory=list)


class AuthorityBuilder:
    """构建页面权威性"""

    # 国内权威元素
    CN_AUTHORITY_ELEMENTS = {
        "references": [
            "据《中国统计年鉴》数据...",
            "根据国家统计局发布信息...",
            "参考文献：《行业标准 GB/T XXXXX》",
        ],
        "credentials": [
            "国家认证",
            "行业资质",
            "专家审核",
        ],
        "trust_signals": [
            "ICP备案",
            "公网安备",
            "营业执照",
        ],
    }

    # 国外权威元素
    EN_AUTHORITY_ELEMENTS = {
        "references": [
            "According to peer-reviewed research published in...",
            "As documented by the U.S. Department of...",
            "Reference: DOI 10.xxxx/xxxxx",
        ],
        "credentials": [
            "Ph.D. in relevant field",
            "Industry-certified professional",
            "Published researcher",
        ],
        "trust_signals": [
            "E-E-A-T compliance",
            "ORCID profile",
            "Google Scholar profile",
        ],
    }

    def build(self, page: CrawledPage, faqs: list[FAQ], config: dict) -> AuthorityProfile:
        """为页面构建权威性画像"""
        profile = AuthorityProfile()

        # 从页面提取作者信息
        profile = self._extract_author_info(page, profile)

        # 根据语言补充权威元素
        if page.language.startswith("zh"):
            profile = self._enhance_cn(page, faqs, profile, config)
        if page.language.startswith("en") or self._has_english_content(page):
            profile = self._enhance_en(page, faqs, profile, config)

        # 双向补充：中文页也补充英文权威
        if page.language.startswith("zh"):
            profile = self._cross_enhance_en(profile)
        if page.language.startswith("en"):
            profile = self._cross_enhance_cn(profile)

        return profile

    @staticmethod
    def _extract_author_info(page: CrawledPage, profile: AuthorityProfile) -> AuthorityProfile:
        """从页面文本提取作者信息"""
        text = page.text
        for line in text.split("\n")[:50]:
            lower = line.lower()
            if any(w in lower for w in ["author", "作者", "by ", "written by"]):
                parts = line.split(":", 1) if ":" in line else line.split("：", 1)
                if len(parts) > 1:
                    profile.author_name = parts[1].strip()
                    break
        return profile

    @staticmethod
    def _has_english_content(page: CrawledPage) -> bool:
        """检测页面是否包含较多英文内容（与 FAQGenerator._has_english 判定一致）"""
        sample = page.text[:1000]
        english_ratio = sum(1 for c in sample if c.isascii() and c.isalpha()) / max(len(sample), 1)
        return english_ratio > 0.3

    def _enhance_cn(self, page: CrawledPage, faqs: list[FAQ], profile: AuthorityProfile, config: dict) -> AuthorityProfile:
        """补充国内权威元素"""
        # 添加参考文献模板
        profile.references.extend(self.CN_AUTHORITY_ELEMENTS["references"])

        # 添加信任信号提示
        profile.certifications = self.CN_AUTHORITY_ELEMENTS["trust_signals"].copy()

        # 从FAQ提取数据引用点
        for f in faqs:
            if f.language == "zh-CN":
                if any(w in f.answer for w in ["%", "数据", "统计", "研究表明"]):
                    profile.data_sources.append(f"FAQ引用: {f.question}")

        return profile

    def _enhance_en(self, page: CrawledPage, faqs: list[FAQ], profile: AuthorityProfile, config: dict) -> AuthorityProfile:
        """补充国外权威元素 (E-E-A-T)"""
        # 添加参考文献模板
        profile.references.extend(self.EN_AUTHORITY_ELEMENTS["references"])

        # E-E-A-T 提示
        profile.certifications = self.EN_AUTHORITY_ELEMENTS["trust_signals"].copy()

        # 从FAQ提取学术引用点
        for f in faqs:
            if f.language == "en-US":
                if any(w in f.answer.lower() for w in ["study", "research", "data", "percent", "%"]):
                    profile.data_sources.append(f"FAQ Citation: {f.question}")

        return profile

    def _cross_enhance_en(self, profile: AuthorityProfile) -> AuthorityProfile:
        """中文页补充英文权威元素"""
        if not profile.author_orcid:
            profile.author_orcid = "https://orcid.org/XXXX-XXXX-XXXX-XXXX (待补充)"
        return profile

    def _cross_enhance_cn(self, profile: AuthorityProfile) -> AuthorityProfile:
        """英文页补充国内权威元素"""
        if not profile.icp_number:
            profile.icp_number = "京ICP备XXXXXXXX号 (待补充)"
        return profile

    def generate_author_box(self, profile: AuthorityProfile, language: str = "zh-CN") -> str:
        """生成作者信息框（HTML）"""
        if language.startswith("zh"):
            return f"""
<div class="author-box" itemscope itemtype="https://schema.org/Person">
  <h3>关于作者</h3>
  <p><strong itemprop="name">{profile.author_name or '待补充'}</strong>
  {f'— {profile.author_title}' if profile.author_title else ''}</p>
  <p itemprop="description">{profile.author_bio or '作者信息待补充'}</p>
  {f'<p>ORCID: <a href="{profile.author_orcid}">{profile.author_orcid}</a></p>' if profile.author_orcid and '待补充' not in profile.author_orcid else ''}
  <h4>资质认证</h4>
  <ul>
    {''.join(f'<li>{c}</li>' for c in profile.credentials)}
    {''.join(f'<li>{cert}</li>' for cert in profile.certifications)}
  </ul>
  {f'<p>ICP备案号: {profile.icp_number}</p>' if profile.icp_number and '待补充' not in profile.icp_number else ''}
</div>
""".strip()
        else:
            return f"""
<div class="author-box" itemscope itemtype="https://schema.org/Person">
  <h3>About the Author</h3>
  <p><strong itemprop="name">{profile.author_name or 'TBD'}</strong>
  {f'— {profile.author_title}' if profile.author_title else ''}</p>
  <p itemprop="description">{profile.author_bio or 'Author bio TBD'}</p>
  {f'<p>ORCID: <a href="{profile.author_orcid}">{profile.author_orcid}</a></p>' if profile.author_orcid and 'TBD' not in profile.author_orcid else ''}
  <h4>Credentials</h4>
  <ul>
    {''.join(f'<li>{c}</li>' for c in profile.credentials)}
    {''.join(f'<li>{cert}</li>' for cert in profile.certifications)}
  </ul>
</div>
""".strip()

    def generate_reference_section(self, profile: AuthorityProfile, language: str = "zh-CN") -> str:
        """生成参考文献区块"""
        lines = ["<h3>参考文献 / References</h3>", "<ol>"]
        for ref in profile.references:
            lines.append(f"  <li>{ref}</li>")
        lines.append("</ol>")
        return "\n".join(lines)


def format_authority_report(profile: AuthorityProfile) -> str:
    """格式化权威性报告"""
    lines = [
        "# 权威性建设报告\n",
        f"**作者:** {profile.author_name or '待补充'}",
        f"**机构:** {profile.organization or '待补充'}",
        f"**ORCID:** {profile.author_orcid or '待补充'}",
        f"**ICP备案:** {profile.icp_number or '待补充'}",
        "",
        "## 资质认证",
    ]
    for c in profile.credentials + profile.certifications:
        lines.append(f"- {c}")

    lines.append("\n## 参考文献")
    for ref in profile.references:
        lines.append(f"- {ref}")

    lines.append("\n## 数据来源")
    for ds in profile.data_sources:
        lines.append(f"- {ds}")

    return "\n".join(lines)


# --- 快捷测试 ---
def main():
    config = load_config()
    from geo_optimizer.crawler import CrawledPage
    page = CrawledPage(
        url="https://example.com",
        title="智能空气净化器",
        html="",
        text="作者：张三\n这是一款智能空气净化器...",
        language="zh-CN",
        meta_desc="",
        meta_keywords="",
        headings=[],
        links=[],
        word_count=500,
    )
    builder = AuthorityBuilder()
    profile = builder.build(page, [], config)
    print(format_authority_report(profile))


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main()
