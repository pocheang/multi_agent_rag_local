# QueryMind（智询）

企业级私有知识库 Agentic RAG 系统，基于 FastAPI、React、LangGraph 和混合检索构建。

## 项目能力

- 多智能体路由、检索、推理和答案合成
- 向量检索、BM25、RRF 融合与重排序
- 可选 GraphRAG、Web Research 和多轮上下文跟踪
- 引用优先、答案校验、质量评分和 SSE 执行追踪
- JWT/RBAC、结构化日志、健康检查和监控集成

## 快速开始

### Docker（推荐用于集成环境）

```bash
export OPENAI_API_KEY="your-api-key"
./deploy/scripts/deploy.sh production balanced
```

Canonical configuration lives in config/ and generated runtime files live in .runtime/. Root .env files, legacy Compose files, and legacy startup scripts are not supported.

### 本地开发

项目使用 Conda 环境 `rag-local`。完整安装、配置和验证步骤见[本地安装](docs/getting-started/setup.md)。

```bash
conda activate rag-local
uvicorn app.api.main:app --reload --port 8000
```

前端：

```bash
cd frontend
npm install
npm run dev
```

启动后可访问：

- API 文档：<http://localhost:8000/docs>
- 前端开发服务：<http://localhost:5173>

## 开发者

**Po Cheang** - [po.cheang@gmail.com](mailto:po.cheang@gmail.com)

## 文档入口

从[文档中心](docs/README.md)开始。按使用场景查看：

- [快速开始](docs/getting-started/README.md)
- [用户指南](docs/user-guide/README.md)
- [系统架构](docs/architecture/README.md)
- [功能说明](docs/features/README.md)
- [开发指南](docs/development/README.md)
- [部署与运维](docs/operations/README.md)
- [API、配置与 FAQ](docs/reference/README.md)
- [版本发布记录](docs/releases/README.md)
- [中文文档](docs/zh-CN/README.md)

文档规则和归档策略见[文档治理政策](docs/DOCUMENTATION_POLICY.md)。

## 常用命令

```bash
# 后端测试
pytest tests/ -v

# 静态检查
ruff check .
ruff format .

# 前端生产构建
cd frontend
npm run build
```

文档完整性检查：

```bash
conda run -n rag-local python scripts/check_docs.py
```

## 项目协作

- [贡献指南](CONTRIBUTING.md)
- [行为准则](CODE_OF_CONDUCT.md)
- [安全策略](SECURITY.md)
- [变更日志](CHANGELOG.md)
- [许可证](LICENSE)

## License

本项目使用 [MIT License](LICENSE)。
