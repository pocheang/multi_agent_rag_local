# 配置说明

**Owner:** QueryMind maintainers  
**Status:** Active  
**Last verified:** 2026-07-17

本页说明配置入口和常用变量。完整变量清单以项目根目录的 .env.example 和[配置参考](../reference/configuration.md)为准；不要把密钥提交到 Git。

## 配置文件

| 文件 | 用途 |
| --- | --- |
| .env.example | 可提交的配置模板 |
| .env | 本地/部署环境实际配置，不应提交 |
| configs/runtime-profiles/fast.env | 低延迟和高吞吐 |
| configs/runtime-profiles/balanced.env | 大多数场景的平衡配置 |
| configs/runtime-profiles/deep.env | 高质量和更强推理 |
| app/core/config.py | 环境变量的类型化读取和默认值 |

## 最小配置路径

~~~powershell
Copy-Item .env.example .env
~~~

本地模型使用 MODEL_BACKEND=ollama 时，确认 Ollama 地址和模型名；使用 OpenAI 时设置 MODEL_BACKEND=openai 与 OPENAI_API_KEY。具体 provider 变量见 .env.example。

## 运行配置档

配置档是可复制到 .env 的环境变量集合：

~~~powershell
Get-Content configs/runtime-profiles/balanced.env | Add-Content .env
~~~

| 配置档 | 适用场景 | 关键取舍 |
| --- | --- | --- |
| fast | 本地开发、低延迟 | 关闭查询改写和分解，减少重试 |
| balanced | 默认推荐 | 保留改写、分解和动态检索 |
| deep | 高风险或复杂分析 | 增加推理、重试和合成轮次，延迟更高 |

不要同时叠加多个 profile；需要组合配置时，以 .env 中最后出现的值为准，并在发布记录中说明。

## 安全相关变量

生产环境至少核对：

- OPENAI_API_KEY、ANTHROPIC_API_KEY 等外部服务密钥
- NEO4J_PASSWORD
- AUTH_TOKEN_TTL_HOURS
- ADMIN_CREATE_APPROVAL_TOKEN_HASH
- API_SETTINGS_ENCRYPTION_KEY
- API_BASE_URL_ALLOWLIST 与 API_BASE_URL_ALLOW_PRIVATE

密钥必须通过部署平台的 Secret 管理注入；不要写入文档、日志、截图或示例值以外的文件。

## 检查配置

~~~powershell
conda activate rag-local
python -c "from app.core.config import get_settings; print(get_settings().model_dump(exclude={'openai_api_key'}))"
~~~

如果配置不生效，依次确认当前目录、Conda 环境、.env 文件位置和变量拼写，再查看[故障排查](../operations/troubleshooting/README.md)。

## 相关页面

- [环境搭建](setup.md)
- [快速开始](quick-start.md)
- [配置参考](../reference/configuration.md)
- [Docker 部署](../operations/docker.md)
