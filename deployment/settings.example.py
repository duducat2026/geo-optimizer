# -*- coding: utf-8 -*-
"""
GEO 平台部署配置样板

使用方法：
    cp deployment/settings.example.py deployment/settings.py
然后按需修改 settings.py（该文件已在 .gitignore 中，不会提交）。

也可通过环境变量覆盖（优先级：环境变量 > settings.py > 本样板默认值）。
"""

# ---- Flask ----
SECRET_KEY = "change-me-to-a-random-secret"

# ---- MySQL8 数据库 ----
# 库名含连字符时连接串已正确转义；请改为你的真实库信息
DB_HOST = "localhost"
DB_PORT = 3306
DB_USER = "root"
DB_PASSWORD = "change-me-db-password"
DB_NAME = "geo-op"

# ---- 默认管理员（首次初始化时创建） ----
# 登录后请立即在后台修改口令
ADMIN_USERNAME = "geoadmin"
ADMIN_PASSWORD = "geo-optimizer"

# ---- 普通用户默认评估配额 ----
DEFAULT_EVAL_QUOTA = 10

# ---- 系统 LLM 默认配置（写入配置页面作为默认值） ----
# 首次初始化会写入 system_config 表，之后可在管理员配置页面修改
# 算力方案可选: bailian(百炼按量付费) / token_plan(Token Plan 团队版) / custom(自定义)
LLM_DEFAULTS = {
    "llm_provider": "bailian",
    "api_host": "dashscope.aliyuncs.com",
    "api_key": "replace-with-your-api-key",
    "openai_base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
    "dashscope_base_url": "https://dashscope.aliyuncs.com/api/v1",
    "model": "qwen-plus",
    "temperature": "0.7",
    "max_tokens": "4096",
}
