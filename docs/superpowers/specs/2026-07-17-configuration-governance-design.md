# QueryMind 配置治理与单机部署设计

**日期：** 2026-07-17  
**状态：** 待实施  
**范围：** 配置目录重构、环境配置分层、Docker Compose 单机部署、一键初始化与健康检查

## 目标

将 QueryMind 当前分散在根目录、`config/`、`configs/`、多个 Compose 文件、前端环境文件和启动脚本中的配置统一治理，形成企业项目可理解、可审计、可重复执行的配置与部署结构。

本设计的交付结果：

1. 所有配置源集中到独立的 `config/` 目录。
2. 所有部署编排和部署脚本集中到独立的 `deploy/` 目录。
3. 开发、测试、生产环境有明确的配置模板和边界。
4. fast、balanced、deep 运行时 profile 保持可选且互斥。
5. 生产部署脚本自动生成本机随机密钥，缺少 LLM API Key 时明确失败或交互式补充。
6. 一条命令完成配置生成、Compose 校验、服务启动、应用初始化和健康检查。
7. 不在本次工作中将现有 SQLite 数据存储迁移到 PostgreSQL。

## 非目标

- 不把 SQLite 应用数据层改造成 PostgreSQL。
- 不引入 Kubernetes、Helm、Vault、Consul 或云厂商 Secret Manager。
- 不重写 `app/core/config.py` 的业务变量语义；仅在必要处修正配置文件加载和路径兼容。
- 不删除用户当前工作区中的忽略文件、密钥文件、日志、备份或已有未提交文档变更。

## 目录架构

```text
config/                         # 唯一配置源
├─ README.md
├─ env/
│  ├─ base.env
│  ├─ development.env.example
│  ├─ test.env.example
│  ├─ production.env.example
│  └─ frontend/
│     ├─ development.env.example
│     └─ production.env.example
├─ profiles/
│  ├─ fast.env
│  ├─ balanced.env
│  └─ deep.env
├─ application/
│  ├─ router_calibration.json
│  └─ web_activity_config.json
└─ observability/
   ├─ prometheus/
   ├─ grafana/
   └─ alertmanager/

deploy/                         # 唯一部署入口
├─ README.md
├─ compose/
│  ├─ compose.yaml
│  ├─ compose.dev.yaml
│  └─ compose.monitoring.yaml
└─ scripts/
   ├─ deploy.sh
   ├─ deploy.ps1
   ├─ config.py
   └─ healthcheck.py

.runtime/                       # 运行时生成物，不提交 Git
├─ production.env
├─ development.env
└─ generated-secrets.env
```

`frontend/` 内的 Vite、TypeScript 和构建工具配置仍保留在前端源码目录，因为它们是构建工具配置，不是部署运行时配置；前端环境变量模板迁移到 `config/env/frontend/`。

## 配置职责与优先级

配置源按以下顺序合并，后者覆盖前者：

```text
config/env/base.env
  < config/env/{environment}.env.example
  < config/profiles/{profile}.env
  < .runtime/generated-secrets.env
  < 命令行显式环境变量
```

其中：

- `base.env` 只包含跨环境稳定的非敏感默认值和应用变量名。
- `development.env.example` 面向 Conda 本地开发，使用 localhost、宽松 Cookie 和较低资源消耗。
- `test.env.example` 面向单元测试和集成测试，使用隔离目录、内存缓存或测试专用服务。
- `production.env.example` 只提供生产安全基线和可编辑的非敏感项，不保存真实密钥。
- `profiles/` 只调整检索速度、质量、缓存、并发和重试策略，不配置数据库地址或凭据。
- `.runtime/generated-secrets.env` 只由部署脚本生成，包含 PostgreSQL、Neo4j、Redis、JWT、应用加密和管理员初始化所需密钥。
- 命令行或宿主机环境变量可覆盖模板值，用于 CI/CD 和 Secret Manager 未来接入。

生成器输出一个供 Compose 和后端共同使用的 `.runtime/{environment}.env`，并在生成前校验变量名、重复键和必需项。生成器不把密钥写入日志。

## 一键部署契约

Linux/macOS：

```bash
./deploy/scripts/deploy.sh production balanced
```

Windows PowerShell：

```powershell
powershell -ExecutionPolicy Bypass -File .\deploy\scripts\deploy.ps1 -Environment production -Profile balanced
```

脚本执行顺序固定为：

1. 检查 Docker Engine 和 Docker Compose v2。
2. 检查当前环境模板和 profile 是否存在且可解析。
3. 从宿主机环境读取 LLM API Key；若交互终端中缺失则安全提示输入，非交互环境直接失败。
4. 生成不存在的随机密钥；已有 `.runtime/generated-secrets.env` 时复用，不覆盖现有密钥。
5. 合并配置并执行 `docker compose config`，在启动前发现非法变量和 Compose 错误。
6. 启动基础服务：PostgreSQL、Neo4j、Redis、backend、frontend。
7. 等待服务健康检查通过。
8. 执行应用初始化脚本；初始化必须幂等，重复部署不得删除数据卷。
9. 访问 backend 健康端点并输出前端、API、日志和停止命令。

监控作为显式 profile 启用，不默认暴露：

```bash
./deploy/scripts/deploy.sh production balanced --monitoring
```

n8n 同样保持显式 Compose profile，不在默认生产启动中启用。

## Compose 设计

- `deploy/compose/compose.yaml` 是生产基础编排，所有服务镜像使用固定版本，不使用 `latest`。
- 数据库、Neo4j、Redis 只加入内部 Docker 网络，不发布宿主机管理端口。
- frontend 对外提供入口，backend 仅通过内部网络和受控健康端点提供服务；开发覆盖文件才发布本机开发端口。
- 所有数据使用命名卷或显式宿主机目录，并在 `deploy/README.md` 中标注备份对象。
- `compose.dev.yaml` 只覆盖源码挂载、热重载、开发端口和开发日志级别，不改变生产数据卷策略。
- `compose.monitoring.yaml` 只引用 `config/observability/` 下的 Prometheus、Grafana 和 Alertmanager 配置。
- Compose 文件中的环境变量统一来自 `.runtime/{environment}.env`，不再依赖根目录隐式 `.env`。

## 安全约束

- 真实 API Key、密码、JWT、加密密钥和管理员 Token 不进入 Git。
- 生产 Cookie 使用 Secure + Strict；开发环境通过开发模板显式放宽。
- 生产 CORS 只允许部署域名，不使用 `*`。
- 生产部署默认不发布 PostgreSQL、Neo4j、Redis、Prometheus、Grafana 和 Alertmanager 管理端口到公网。
- 生产配置生成后，POSIX 环境设置文件权限为仅当前用户可读；PowerShell 环境使用当前用户 ACL 作为最低保护。
- 部署脚本只输出变量名和脱敏状态，不输出变量值。
- 任何初始化、重启和升级操作都不得隐式执行 `docker compose down -v`。

## 迁移规则

| 现有位置 | 目标位置 | 处理方式 |
| --- | --- | --- |
| `.env.example` | `config/env/development.env.example` | 迁移为开发模板 |
| `.env.docker.example` | `config/env/production.env.example` | 迁移并删除默认弱密码 |
| `.env.docling.example` | `config/env/base.env` 中的文档处理段 | 合并为统一配置 |
| `.env.optimized*` | `config/profiles/` | 只保留策略性参数，去除重复基础配置 |
| `.env.security` | `config/env/production.env.example` 的安全段 | 只保留安全基线，不迁移真实密钥 |
| `configs/runtime-profiles/*.env` | `config/profiles/*.env` | 合并目录 |
| `config/router_calibration.json` | `config/application/router_calibration.json` | 迁移静态应用配置 |
| `config/web_activity_config.json` | `config/application/web_activity_config.json` | 迁移静态应用配置 |
| `config/prometheus/*`、`config/grafana/*`、`config/alertmanager/*` | `config/observability/` | 迁移监控配置 |
| `docker-compose*.yml` | `deploy/compose/*.yaml` | 统一命名和路径 |
| `start.sh`、`start.bat`、`restart.bat` | `deploy/scripts/` | 保留兼容入口或改为调用新脚本 |

忽略的本地 `.env`、日志、备份和数据库文件不自动删除；迁移脚本只处理明确的配置模板和已纳入版本控制的部署文件。

## 兼容与回滚

迁移完成后，README 和运维文档只推荐 `deploy/scripts/` 命令。旧入口如果保留，仅调用新入口并输出迁移提示，不再维护独立配置逻辑。

回滚时只需：

1. 保留 `.runtime/` 和数据卷。
2. 切换回上一版 Compose 文件和应用镜像。
3. 使用相同的 `.runtime/generated-secrets.env`，避免用户会话和加密数据失效。

不得通过删除卷回滚，也不得重新生成已经存在的生产密钥。

## 验证标准

配置治理完成后必须通过以下检查：

1. `config/` 和 `deploy/` 目录结构与本设计一致。
2. `config/env/`、`config/profiles/` 中没有重复变量或弱默认密钥。
3. 生产模板缺少 LLM API Key 时，部署预检给出明确错误并退出非零状态。
4. 生产部署命令可重复执行，第二次执行复用密钥、不删除数据卷且服务保持可用。
5. `docker compose config` 在开发、生产和监控组合下均返回成功。
6. backend `/health`、frontend 根路径和 API 文档均可访问。
7. 旧配置路径不再被 Compose、脚本或文档作为主入口引用。
8. Python 单元测试、配置生成器测试、部署脚本静态检查和前端构建均通过。

