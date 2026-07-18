# 快速部署

**Owner:** QueryMind maintainers  
**Status:** Active  
**Last verified:** 2026-07-17

本页是已完成环境准备后的最短部署入口，不再包含过时的 Agent 质量验证脚本或临时启动脚本。

## Docker

~~~powershell
Copy-Item .env.example .env
docker compose up -d
docker compose ps
docker compose exec backend python scripts/init_db.py
Invoke-WebRequest http://localhost:8000/health
~~~

访问前端 <http://localhost>，API 文档 <http://localhost:8000/docs>。

## 本地开发

终端 1：

~~~powershell
conda activate rag-local
uvicorn app.api.main:app --reload --port 8000
~~~

终端 2：

~~~powershell
cd frontend
npm install
npm run dev
~~~

访问前端 <http://localhost:5173>。

## 发布前最小检查

~~~powershell
conda run -n rag-local python scripts/check_docs.py
pytest tests/ -q
~~~

生产发布请改用[生产部署](deployment.md)和[GitHub 发布流程](../development/github-release.md)。
