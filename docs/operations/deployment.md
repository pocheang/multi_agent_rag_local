# 生产部署

**Owner:** QueryMind maintainers  
**Status:** Active  
**Last verified:** 2026-07-17

本页描述生产部署的决策和检查项。仓库提供 Docker Compose 基线；生产环境应在其上增加反向代理、Secret 管理、备份、监控和回滚策略。

## 推荐拓扑

公网流量进入 HTTPS 反向代理，再转发到 frontend 和 backend。PostgreSQL、Neo4j、Redis、Chroma 数据目录和日志必须位于受控网络，数据库端口不直接暴露到公网。

## 部署前检查

- 使用固定版本的 Docker 镜像，不使用未固定的 latest。
- 准备生产 .env，密钥通过 Secret 管理注入。
- 设置 OPENAI_API_KEY 或实际使用的模型后端配置。
- 设置 NEO4J_PASSWORD、REDIS_PASSWORD、POSTGRES_PASSWORD。
- 设置 API_SETTINGS_ENCRYPTION_KEY 和 ADMIN_CREATE_APPROVAL_TOKEN_HASH。
- 确认数据卷、数据库和文档目录的备份策略。
- 确认健康检查、日志采集、告警和回滚负责人。

## Compose 基线

在项目根目录：

~~~powershell
Copy-Item .env.example .env
docker compose up -d
docker compose ps
docker compose exec backend python scripts/init_db.py
Invoke-WebRequest http://localhost:8000/health
~~~

Compose 的实际服务、端口和卷以 docker-compose.yml 为准，详见[Docker 部署](docker.md)。

## 发布流程

1. 审阅版本说明和迁移要求。
2. 备份数据库、索引和上传数据。
3. 在非生产环境执行镜像构建和 smoke check。
4. 通过受控配置发布新镜像。
5. 检查 docker compose ps、日志和 /health。
6. 验证登录、查询、文档上传和关键管理功能。
7. 保留回滚镜像和上一版本配置。

## 回滚

- 先停止接收变更并保留当前日志。
- 回滚应用镜像和对应兼容配置。
- 不要未经批准删除数据卷。
- 回滚后重新检查 /health、API 文档和核心查询链路。
- 在发布记录中记录原因、影响和恢复时间。

## 监控与运维

- [监控中心](monitoring/README.md)
- [运行手册](runbooks/README.md)
- [故障排查](troubleshooting/README.md)
- [性能与容量](performance.md)
- [Docker 部署](docker.md)
