# 前端访问

**Owner:** QueryMind maintainers  
**Status:** Active  
**Last verified:** 2026-07-17

## 本地开发

后端运行在 8000 端口、前端 Vite 开发服务运行在 5173 端口：

~~~powershell
conda activate rag-local
uvicorn app.api.main:app --reload --port 8000
~~~

新开终端：

~~~powershell
cd frontend
npm install
npm run dev
~~~

访问 <http://localhost:5173>。

## Docker Compose

Compose 前端由容器提供 80 端口，后端提供 8000 端口：

~~~powershell
docker compose up -d
~~~

访问 <http://localhost>。实际映射以 docker-compose.yml 为准。

## API 文档

- Swagger UI：<http://localhost:8000/docs>
- ReDoc：<http://localhost:8000/redoc>
- OpenAPI JSON：<http://localhost:8000/openapi.json>

## Web activity

Web activity 管理页面和 API 属于可选能力，请查看 [Web activity 运维](web-activity/README.md)，不要把它与普通前端访问页面混为一谈。
