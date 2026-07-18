# 快速开始

**Owner:** QueryMind maintainers  
**Status:** Active  
**Last verified:** 2026-07-17

本页只保留一条可验证的本地启动路径。高级配置、Docker 和运维操作请使用关联页面。

## 前置条件

- Conda 环境 rag-local
- Python 3.11+
- Node.js 18+ 与 npm
- 已准备 .env；模板见项目根目录 .env.example

## 1. 配置后端

在项目根目录执行：

~~~powershell
Copy-Item .env.example .env
~~~

至少确认以下配置：

- MODEL_BACKEND 与本地模型或云端 API 一致
- 使用 OpenAI/Anthropic/DeepSeek 时填写对应 API key
- NEO4J_PASSWORD 使用随机长密码；Neo4j 不可用时，系统按当前实现降级运行
- 生产环境补齐 API_SETTINGS_ENCRYPTION_KEY 和 ADMIN_CREATE_APPROVAL_TOKEN_HASH

## 2. 启动后端

~~~powershell
conda activate rag-local
uvicorn app.api.main:app --reload --port 8000
~~~

验证：

~~~powershell
Invoke-WebRequest http://localhost:8000/health
~~~

浏览器打开 <http://localhost:8000/docs> 查看 OpenAPI 文档。

## 3. 启动前端

新开一个终端：

~~~powershell
cd frontend
npm install
npm run dev
~~~

浏览器打开 <http://localhost:5173>。

## 4. 验证 Agent 健康

后端启动后可访问：

- 全局健康检查：<http://localhost:8000/health>
- Agent 健康检查：<http://localhost:8000/api/v1/agents/health>
- OpenAPI 文档：<http://localhost:8000/docs>

~~~powershell
Invoke-WebRequest http://localhost:8000/api/v1/agents/health
~~~

## 运行测试和质量检查

~~~powershell
conda activate rag-local
pytest tests/ -v
ruff check .
conda run -n rag-local python scripts/check_docs.py
~~~

## 下一步

- [环境搭建](setup.md)
- [配置说明](configuration.md)
- [Docker 部署](../operations/docker.md)
- [API 参考](../reference/README.md)
- [故障排查](../operations/troubleshooting/README.md)
