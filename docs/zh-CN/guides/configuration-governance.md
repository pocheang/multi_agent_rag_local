# 企业化配置与部署

项目配置已经按“配置源、部署资产、运行时产物”分离：

```text
config/                    # 可审查、可版本化的配置源
├── env/                   # base + development/test/production 覆盖层
├── env/frontend/          # 前端构建环境模板
├── profiles/              # fast / balanced / deep 检索策略
├── application/           # 路由校准、Web 活动等应用配置
└── observability/         # Prometheus、Grafana、Alertmanager
deploy/                    # Compose 和运维脚本
├── compose/
└── scripts/
.runtime/                  # 自动生成的最终配置和随机密钥，不提交 Git
```

## 一键部署

Linux/macOS/WSL：

```bash
export OPENAI_API_KEY="your-api-key"
./deploy/scripts/deploy.sh production balanced
```

PowerShell：

```powershell
$env:OPENAI_API_KEY = "your-api-key"
.\deploy\scripts\deploy.ps1 -Environment production -Profile balanced
```

脚本会渲染 `.runtime/production.env`、生成本地随机密钥、执行 Compose 静态校验、构建并启动服务、初始化应用数据库，并等待后端健康检查通过。密钥不会写入配置模板或终端输出。

开发环境：

```bash
./deploy/scripts/deploy.sh development fast
```

开发服务默认访问地址为后端 `http://127.0.0.1:8000`、前端 `http://127.0.0.1:5173`。生产基线只暴露前端 80 端口，PostgreSQL、Neo4j、Redis 仅在 Compose 内网可见。

## 配置层级

配置渲染顺序为：`base.env` → 环境覆盖层 → 检索 profile → `.runtime/generated-secrets.env` → 当前进程环境变量。最后一层用于 CI/CD 或部署主机注入 API Key，不应把真实凭据写入仓库。

常用校验命令：

```bash
conda run -n rag-local python deploy/scripts/config.py validate --environment development --profile balanced
conda run -n rag-local python deploy/scripts/config.py render --environment production --profile balanced --output .runtime/production.env
```

生产环境要求关闭调试、使用明确的 CORS 来源、配置模型 API Key，并设置所有应用密钥。部署失败时先查看配置校验错误，再查看 `docker compose logs backend`；不要使用 `down -v`，以免删除持久化卷。

监控与工作流服务按需启用：

```bash
./deploy/scripts/deploy.sh production balanced --monitoring --with-n8n
```
