# 部署入口

`deploy/` 是 QueryMind 的独立部署目录，集中放置 Compose 编排、运行时初始化、健康检查和一键部署脚本。

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

脚本会在 `.runtime/` 中生成环境配置和随机密钥，校验 Compose 配置，构建并启动服务，初始化应用数据库并执行后端健康检查。`.runtime/` 不应提交到 Git。

可选参数：`--monitoring` / `-Monitoring` 启用 Prometheus、Alertmanager、Grafana；`--with-n8n` / `-WithN8n` 启用 n8n。

## 本地开发

```bash
./deploy/scripts/deploy.sh development fast
```

开发环境使用 `config/env/development.env.example` 作为覆盖层，后端在 `127.0.0.1:8000`，前端在 `127.0.0.1:5173`。本地 Conda 环境仍使用 `rag-local`。

## 配置目录

- `compose/`：生产基线、开发覆盖和监控覆盖。
- `scripts/`：配置渲染、初始化和健康检查。
- `../config/`：环境模板、运行策略、应用配置和可观测性配置。
- `../.runtime/`：仅由脚本生成的最终配置和密钥。

规范目录：deploy/compose/ 保存 Compose 编排，deploy/scripts/ 保存部署脚本。
