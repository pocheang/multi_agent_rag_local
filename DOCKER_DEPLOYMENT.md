# Docker 部署指南

本指南介绍如何使用 Docker 和 Docker Compose 部署 QueryMind 系统。

## 📋 前置要求

- Docker Engine 20.10+
- Docker Compose 2.0+
- 至少 8GB RAM
- 至少 20GB 磁盘空间

## 🚀 快速启动

### 1. 准备环境变量

```bash
# 复制环境变量模板
cp .env.example .env

# 编辑 .env 文件，设置必需的配置
nano .env
```

**必须设置的变量：**
```env
POSTGRES_PASSWORD=your_strong_password
NEO4J_PASSWORD=your_neo4j_password
JWT_SECRET_KEY=your_32_character_secret_key
OPENAI_API_KEY=sk-your-openai-key
```

**生成 JWT 密钥：**
```bash
openssl rand -hex 32
```

### 2. 启动所有服务

```bash
# 启动核心服务（后端、前端、数据库）
docker-compose up -d

# 启动包含 n8n 的完整服务
docker-compose --profile with-n8n up -d
```

### 3. 初始化数据库

```bash
# 等待服务启动（约30秒）
docker-compose ps

# 执行数据库初始化
docker-compose exec backend python scripts/init_db.py
```

### 4. 访问应用

- **前端界面**: http://localhost
- **后端API**: http://localhost:8000
- **API文档**: http://localhost:8000/docs
- **Neo4j浏览器**: http://localhost:7474
- **n8n工作流**: http://localhost:5678 (如果启用)

## 📦 服务说明

### 核心服务

| 服务 | 容器名 | 端口 | 说明 |
|------|--------|------|------|
| postgres | querymind-postgres | 5432 | PostgreSQL数据库 |
| neo4j | querymind-neo4j | 7474, 7687 | Neo4j知识图谱 |
| redis | querymind-redis | 6379 | Redis缓存 |
| backend | querymind-backend | 8000 | FastAPI后端 |
| frontend | querymind-frontend | 80 | React前端 |

### 可选服务

| 服务 | 容器名 | 端口 | 说明 |
|------|--------|------|------|
| n8n | querymind-n8n | 5678 | 工作流自动化 |

## 🔧 常用命令

### 启动/停止服务

```bash
# 启动所有服务
docker-compose up -d

# 停止所有服务
docker-compose down

# 停止并删除所有数据（谨慎使用）
docker-compose down -v

# 重启特定服务
docker-compose restart backend

# 查看服务状态
docker-compose ps

# 查看服务日志
docker-compose logs -f backend
```

### 构建和更新

```bash
# 重新构建镜像
docker-compose build

# 重新构建特定服务
docker-compose build backend

# 拉取最新镜像并重启
docker-compose pull
docker-compose up -d
```

### 数据管理

```bash
# 备份PostgreSQL数据库
docker-compose exec postgres pg_dump -U querymind querymind > backup.sql

# 恢复PostgreSQL数据库
docker-compose exec -T postgres psql -U querymind querymind < backup.sql

# 备份Neo4j数据库
docker-compose exec neo4j neo4j-admin database dump neo4j

# 清理未使用的Docker资源
docker system prune -a
```

### 调试和诊断

```bash
# 进入后端容器
docker-compose exec backend bash

# 查看后端日志（实时）
docker-compose logs -f backend

# 检查容器健康状态
docker-compose ps

# 查看容器资源使用
docker stats

# 检查网络连接
docker-compose exec backend curl http://postgres:5432
```

## 🔒 安全配置

### 生产环境建议

1. **更改所有默认密码**
```env
POSTGRES_PASSWORD=<strong-unique-password>
NEO4J_PASSWORD=<strong-unique-password>
REDIS_PASSWORD=<strong-unique-password>
JWT_SECRET_KEY=<32-character-random-string>
```

2. **限制端口访问**
```yaml
# docker-compose.yml
ports:
  - "127.0.0.1:5432:5432"  # 仅本地访问
```

3. **使用 HTTPS**
- 配置反向代理（Nginx/Caddy）
- 使用 Let's Encrypt 证书

4. **启用防火墙**
```bash
# Ubuntu/Debian
ufw allow 80/tcp
ufw allow 443/tcp
ufw enable
```

5. **定期更新镜像**
```bash
docker-compose pull
docker-compose up -d
```

## 📊 性能优化

### 资源限制

```yaml
# docker-compose.yml
services:
  backend:
    deploy:
      resources:
        limits:
          cpus: '2'
          memory: 4G
        reservations:
          cpus: '1'
          memory: 2G
```

### 数据库优化

```yaml
# docker-compose.yml
postgres:
  command:
    - "postgres"
    - "-c"
    - "max_connections=200"
    - "-c"
    - "shared_buffers=256MB"
    - "-c"
    - "effective_cache_size=1GB"
```

### Redis配置

```yaml
redis:
  command: >
    redis-server
    --maxmemory 512mb
    --maxmemory-policy allkeys-lru
    --appendonly yes
```

## 🔍 健康检查

所有服务都配置了健康检查，可以通过以下方式查看：

```bash
# 查看健康状态
docker-compose ps

# 详细健康检查信息
docker inspect querymind-backend | grep -A 10 Health
```

## 🐛 故障排查

### 服务无法启动

```bash
# 查看详细日志
docker-compose logs backend

# 检查配置
docker-compose config

# 验证环境变量
docker-compose exec backend env | grep -i api
```

### 数据库连接失败

```bash
# 测试PostgreSQL连接
docker-compose exec backend python -c "from app.core.config import get_settings; print(get_settings().database_url)"

# 测试Neo4j连接
docker-compose exec backend python -c "from app.graph.neo4j_client import Neo4jClient; client = Neo4jClient(); print(client.verify_connectivity())"
```

### 内存不足

```bash
# 查看资源使用
docker stats

# 清理未使用的资源
docker system prune -a --volumes
```

### 端口冲突

```bash
# 检查端口占用
netstat -tuln | grep 8000

# 修改 docker-compose.yml 中的端口映射
ports:
  - "8001:8000"  # 使用其他端口
```

## 📝 开发模式

开发时可以挂载本地代码实现热重载：

```yaml
# docker-compose.override.yml
services:
  backend:
    volumes:
      - ./app:/app/app
      - ./scripts:/app/scripts
    command: uvicorn app.api.main:app --reload --host 0.0.0.0 --port 8000
    
  frontend:
    volumes:
      - ./frontend/src:/app/src
    command: npm run dev
```

```bash
# 启动开发环境
docker-compose -f docker-compose.yml -f docker-compose.override.yml up
```

## 🔄 更新和迁移

### 更新到新版本

```bash
# 1. 备份数据
docker-compose exec postgres pg_dump -U querymind querymind > backup_$(date +%Y%m%d).sql

# 2. 停止服务
docker-compose down

# 3. 拉取新代码
git pull origin main

# 4. 重新构建
docker-compose build

# 5. 启动服务
docker-compose up -d

# 6. 运行迁移（如需要）
docker-compose exec backend alembic upgrade head
```

## 📞 支持

遇到问题？
- 查看日志: `docker-compose logs -f`
- 查看文档: http://localhost:8000/docs
- 提交Issue: [GitHub Issues](https://github.com/yourorg/querymind/issues)

---

**生产环境部署建议**：
- 使用环境特定的 `.env.production` 文件
- 配置反向代理和SSL证书
- 设置日志收集和监控
- 配置自动备份策略
- 使用容器编排（Kubernetes）处理大规模部署
