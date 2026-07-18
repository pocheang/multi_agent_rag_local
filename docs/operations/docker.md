# Docker 部署

**Owner:** QueryMind maintainers  
**Status:** Active  
**Last verified:** 2026-07-17

本页描述仓库内 docker-compose.yml 的容器化路径。开发服务器端口 5173 与 Compose 前端端口 80 是不同场景，不要混用。

## 前置条件

- Docker Engine 20.10+
- Docker Compose v2
- 至少 8 GB 内存
- 至少 20 GB 可用磁盘

## 启动

在项目根目录：

~~~powershell
Copy-Item .env.example .env
docker compose up -d
docker compose ps
docker compose exec backend python scripts/init_db.py
~~~

访问：

- 前端：<http://localhost>
- 后端：<http://localhost:8000>
- API 文档：<http://localhost:8000/docs>
- Neo4j Browser：<http://localhost:7474>

可选 n8n profile：

~~~powershell
docker compose --profile with-n8n up -d
~~~

n8n 地址：<http://localhost:5678>。只有在需要该能力时启用。

## Compose 服务

| 服务 | 默认地址/端口 | 说明 |
| --- | --- | --- |
| postgres | 127.0.0.1:5432 | PostgreSQL |
| neo4j | 127.0.0.1:7474、7687 | 图数据库 |
| redis | 127.0.0.1:6379 | 缓存 |
| backend | 127.0.0.1:8000 | FastAPI |
| frontend | 0.0.0.0:80 | React 静态服务 |
| n8n | 127.0.0.1:5678 | 可选工作流服务 |

实际端口以 docker-compose.yml 为准。

## 日常操作

~~~powershell
docker compose ps
docker compose logs -f backend
docker compose restart backend
docker compose down
~~~

不要在生产环境使用 docker compose down -v，除非已确认卷数据已备份并允许删除。

## 配置与安全

- 从 .env.example 创建 .env，不使用不存在的 .env.docker.example。
- 修改 NEO4J_PASSWORD、REDIS_PASSWORD、POSTGRES_PASSWORD 和应用密钥。
- 生产环境限制数据库、Redis、Neo4j 管理端口的网络暴露。
- 固定镜像版本，避免使用未固定的 latest。
- 使用反向代理和 HTTPS 暴露公网服务。

## 故障处理

1. 查看 docker compose ps 和对应服务日志。
2. 先检查 .env 变量和健康检查。
3. 仅重启异常服务，不要直接删除数据卷。
4. 初始化/迁移前先备份数据库。

详细生产部署请看[生产部署](deployment.md)，本地非容器启动请看[快速开始](../getting-started/quick-start.md)。
