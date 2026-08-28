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

项目使用 Conda 环境 `rag-local`。

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

从[文档中心](docs/README.md)开始。描述"系统当前如何工作"的文档（架构、功能、参考、运维等）
已在 v0.7 重构前清理，待重构完成后重新生成；[版本发布记录](docs/releases/README.md)和
[开发日志](docs/development/daily-logs/README.md)作为历史记录保留。

## 常用命令

```bash
# 静态检查
ruff check .
ruff format .

# 前端生产构建
cd frontend
npm run build
```

## 项目协作

- [贡献指南](CONTRIBUTING.md)
- [行为准则](CODE_OF_CONDUCT.md)
- [安全策略](SECURITY.md)
- [变更日志](CHANGELOG.md)
- [许可证](LICENSE)

## License

本项目使用 [MIT License](LICENSE)。
