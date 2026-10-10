# GEO-Optimizer 镜像构建（Web 平台 + MCP 服务端共用同一镜像）。
#
# 采用与 deployment/start.sh 一致的源码布局 + 可编辑安装（单阶段）：
#   1. 依赖均为纯 wheel（无编译层可剥离，多阶段无收益）；
#   2. 运行时代码按仓库根定位 deployment/、geo_config.yaml 与 data/artifacts，
#      源码必须整体位于 /app，可编辑安装保证包内路径解析正确。
#
# 构建参数面向国内网络环境，均可用 --build-arg 覆盖：
#   APT_MIRROR    Debian 源主机名，默认清华（可选阿里云 mirrors.aliyun.com）
#   PIP_INDEX     pip 源，默认清华
#   PLAYWRIGHT_DOWNLOAD_HOST  Chromium 下载镜像，默认 npmmirror

FROM python:3.12-slim

ARG APT_MIRROR=mirrors.tuna.tsinghua.edu.cn
ARG PIP_INDEX=https://pypi.tuna.tsinghua.edu.cn/simple
ARG PLAYWRIGHT_DOWNLOAD_HOST=https://npmmirror.com/mirrors/playwright/

# 同时改写 deb822 (debian.sources) 与经典 sources.list 两种 apt 配置
RUN set -eux; for f in /etc/apt/sources.list /etc/apt/sources.list.d/debian.sources; do \
      [ -f "$f" ] && sed -i -e "s|deb.debian.org|${APT_MIRROR}|g" -e "s|security.debian.org|${APT_MIRROR}|g" "$f" || true; \
    done

ENV PIP_INDEX_URL=${PIP_INDEX} \
    PLAYWRIGHT_DOWNLOAD_HOST=${PLAYWRIGHT_DOWNLOAD_HOST}

WORKDIR /app

# 依赖与 Chromium 浏览器（pyproject/README 先行拷贝，源码变更时命中层缓存重装即可）
COPY pyproject.toml README.md LICENSE ./
COPY src ./src
RUN pip install --no-cache-dir -e ".[web,mcp]" \
 && playwright install --with-deps chromium \
 && rm -rf /var/lib/apt/lists/*

# 运行时代码与部署配置（settings.example.py 供配置加载器兜底，实际值走环境变量）
# docs/geo-skill/：SKILL 包导出功能的运行时依赖（SKILL.md + 客户端脚本）
COPY mcp_server ./mcp_server
COPY deployment ./deployment
COPY docs/geo-skill ./docs/geo-skill
COPY geo_config.yaml ./

# 评估产物与日志落在此处，compose 中挂卷持久化
RUN mkdir -p data logs

EXPOSE 5000 8000

# 默认启动 Web 平台（GEO_HOST/GEO_PORT 与 deployment/start.sh 语义一致）；
# MCP 服务端在 compose 中用 command 覆盖为: python -m mcp_server
CMD ["sh", "-c", "python -m geo_optimizer.web.app --host \"${GEO_HOST:-0.0.0.0}\" --port \"${GEO_PORT:-5000}\""]
