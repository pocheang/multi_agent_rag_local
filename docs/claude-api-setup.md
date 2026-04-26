# Claude API 配置指南

本项目现已支持使用 Anthropic Claude API 作为 LLM 后端。

## 快速开始

### 1. 安装依赖

```bash
pip install -e .
```

这将自动安装 `langchain-anthropic` 包。

### 2. 配置环境变量

编辑 `.env` 文件，设置以下配置：

```bash
# 设置模型后端为 anthropic
MODEL_BACKEND=anthropic

# 配置 Claude API Key
ANTHROPIC_API_KEY=your_api_key_here

# 配置 Claude 模型（可选，默认值如下）
ANTHROPIC_CHAT_MODEL=claude-sonnet-4-6
ANTHROPIC_REASONING_MODEL=claude-sonnet-4-6
```

### 3. 启动服务

```bash
# 确保 Neo4j 已启动
docker compose up -d neo4j

# 启动后端服务
uvicorn app.api.main:app --host 127.0.0.1 --port 8000 --reload
```

## 可用的 Claude 模型

根据 Anthropic 官方文档，以下是推荐的模型 ID：

- **Claude Opus 4.7**: `claude-opus-4-7` - 最强大的模型
- **Claude Sonnet 4.6**: `claude-sonnet-4-6` - 平衡性能和成本（推荐）
- **Claude Haiku 4.5**: `claude-haiku-4-5-20251001` - 最快速的模型

## 切换模型后端

项目支持三种 LLM 后端，可以通过 `MODEL_BACKEND` 环境变量切换：

### 使用 Claude API（推荐）

```bash
MODEL_BACKEND=anthropic
ANTHROPIC_API_KEY=your_api_key_here
```

### 使用 OpenAI API

```bash
MODEL_BACKEND=openai
OPENAI_API_KEY=your_api_key_here
```

### 使用本地 Ollama

```bash
MODEL_BACKEND=ollama
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_CHAT_MODEL=qwen2.5:7b-instruct
```

## 注意事项

1. **Embedding 模型**: 目前 Claude API 不提供 embedding 模型，因此即使使用 Claude 作为聊天模型，embedding 仍需使用 OpenAI 或 Ollama。如果使用 OpenAI embedding，需要同时配置 `OPENAI_API_KEY`。

2. **API Key 安全**: 请勿将 API Key 提交到版本控制系统。`.env` 文件已在 `.gitignore` 中排除。

3. **成本控制**: Claude API 按 token 计费，建议在开发环境使用 Sonnet 或 Haiku 模型以控制成本。

4. **速率限制**: 注意 Anthropic API 的速率限制，避免频繁请求导致限流。

## 故障排查

### 错误: "unsupported model backend: anthropic"

确保已安装最新版本的依赖：

```bash
pip install -e . --upgrade
```

### 错误: "No module named 'langchain_anthropic'"

手动安装 langchain-anthropic：

```bash
pip install langchain-anthropic>=0.3.0
```

### API Key 无效

检查 `.env` 文件中的 `ANTHROPIC_API_KEY` 是否正确配置，并确保 API Key 有效。

## 参考资源

- [Anthropic API 文档](https://docs.anthropic.com/)
- [LangChain Anthropic 集成](https://python.langchain.com/docs/integrations/chat/anthropic)
- [Claude 模型列表](https://docs.anthropic.com/en/docs/about-claude/models)
