# 🤖 支持的 AI 模型（2026版）

> QueryMind 支持2026年主流大模型，覆盖云端API和本地部署

---

## 2026主流大模型分类

| 公司/生态 | 代表模型 | 主要优势 | 使用建议 |
|----------|---------|---------|---------|
| **OpenAI** | GPT-5.5, GPT-5.5 Thinking, GPT-5.3-Codex | 综合能力、复杂推理、代码、Agent | 云端生产首选 |
| **Anthropic** | Claude Opus 4.8, Claude Sonnet, Claude Haiku | 长上下文、代码、复杂任务、企业Agent | 长任务和代码强 |
| **Google DeepMind** | Gemini 3.5 Pro, Gemini Flash, Gemma | 多模态、低成本、Google生态、本地小模型 | 多模态和成本友好 |
| **DeepSeek** | DeepSeek-V4, DeepSeek-V3, DeepSeek-R1 | 高性价比、中文、推理、开放生态 | 中文和低成本优先 |
| **Alibaba Qwen** | Qwen3.7-Max, Qwen3-Coder, Qwen3-235B | 中文、代码、Agent、本地部署 | 国产主流首选 |
| **Meta** | Llama 4 Scout, Llama 4 Maverick | 开放权重、本地部署、生态成熟 | 私有化部署常用 |

---

## ☁️ 云端 API 模型

### OpenAI（综合能力首选）

```bash
# GPT-5.5 系列（2026最新）
export LLM_MODEL="gpt-5.5"                # 综合能力最强
export LLM_MODEL="gpt-5.5-thinking"       # 复杂推理专用
export LLM_MODEL="gpt-5.3-codex"          # 代码生成专用

# GPT-4 系列（稳定生产）
export LLM_MODEL="gpt-4-turbo"
export LLM_MODEL="gpt-4"
```

### Anthropic Claude（长上下文和代码）

```bash
# Claude 4.x 系列（2026推荐）
export LLM_MODEL="claude-opus-4-8"        # 最强能力，长任务
export LLM_MODEL="claude-sonnet-4-6"      # 平衡性能
export LLM_MODEL="claude-haiku-4-5"       # 快速响应
```

### Google DeepMind（多模态和成本友好）

```bash
# Gemini 3.5 系列（2026最新）
export LLM_MODEL="gemini-3.5-pro"         # 多模态专业版
export LLM_MODEL="gemini-flash"           # 快速低成本
```

### DeepSeek（高性价比和中文）

```bash
# DeepSeek V4 系列（2026最新）
export LLM_MODEL="deepseek-v4"            # 最新版本
export LLM_MODEL="deepseek-v3"            # 稳定版本
export LLM_MODEL="deepseek-r1"            # 推理模型
```

---

## 🖥️ 本地模型（Ollama）

### Alibaba Qwen（国产首选，中文最强）

```bash
# Qwen 3.7 系列（2026最新）
ollama pull qwen3.7-max               # Qwen 3.7 Max 旗舰
ollama pull qwen3-coder:235b          # Qwen 3 Coder 235B
ollama pull qwen3-coder:70b           # Qwen 3 Coder 70B
ollama pull qwen3:235b                # Qwen 3 235B
ollama pull qwen3:70b                 # Qwen 3 70B
ollama pull qwen3:14b                 # Qwen 3 14B
ollama pull qwen3:7b                  # Qwen 3 7B
```

### Meta Llama 4（开放权重，生态成熟）

```bash
# Llama 4 系列（2026最新）
ollama pull llama4-scout:405b         # Llama 4 Scout 405B
ollama pull llama4-scout:70b          # Llama 4 Scout 70B
ollama pull llama4-scout:8b           # Llama 4 Scout 8B
ollama pull llama4-maverick:405b      # Llama 4 Maverick 405B
ollama pull llama4-maverick:70b       # Llama 4 Maverick 70B
```

### DeepSeek 开源（高性价比）

```bash
# DeepSeek 开源系列
ollama pull deepseek-v4               # DeepSeek V4 最新
ollama pull deepseek-v3               # DeepSeek V3
ollama pull deepseek-r1:70b           # R1 推理 70B
ollama pull deepseek-r1:32b           # R1 推理 32B
ollama pull deepseek-r1:8b            # R1 推理 8B
```

### Google Gemma（边缘部署）

```bash
# Gemma 3 系列
ollama pull gemma3:27b                # Gemma 3 27B
ollama pull gemma3:9b                 # Gemma 3 9B
ollama pull gemma3:2b                 # Gemma 3 2B
```

### Embedding 模型

```bash
# 高性能嵌入模型
ollama pull nomic-embed-text          # Nomic Embed（推荐）
ollama pull bge-large                 # BGE Large
```

---

## 📝 配置示例

### 使用 GPT-5.5（2026云端首选）

```python
LLM_PROVIDER = "openai"
LLM_MODEL = "gpt-5.5"
OPENAI_API_KEY = "sk-..."
```

### 使用 Claude Opus 4.8（长任务）

```python
LLM_PROVIDER = "anthropic"
LLM_MODEL = "claude-opus-4-8"
ANTHROPIC_API_KEY = "sk-ant-..."
```

### 使用 Qwen 3.7 Max（国产首选）

```python
LLM_PROVIDER = "ollama"
LLM_MODEL = "qwen3.7-max"
OLLAMA_BASE_URL = "http://localhost:11434"
```

### 使用 DeepSeek V4（高性价比）

```python
LLM_PROVIDER = "openai"  # DeepSeek 兼容 OpenAI API
LLM_MODEL = "deepseek-v4"
OPENAI_API_KEY = "sk-..."
OPENAI_API_BASE = "https://api.deepseek.com"
```

---

## 🎯 模型选择建议

| 使用场景 | 推荐模型 | 原因 |
|---------|---------|------|
| **生产环境（云端）** | GPT-5.5, Claude Opus 4.8 | 综合能力最强 |
| **复杂推理** | GPT-5.5 Thinking, DeepSeek-R1 | 推理能力突出 |
| **代码生成** | GPT-5.3-Codex, Qwen3-Coder | 代码专用 |
| **长上下文** | Claude Opus 4.8, Gemini 3.5 Pro | 超长上下文 |
| **多模态** | Gemini 3.5 Pro, Gemini Flash | 图文理解 |
| **高性价比** | DeepSeek-V4, Gemini Flash | 成本低 |
| **中文任务** | Qwen 3.7 Max, DeepSeek-V4 | 中文最强 |
| **本地大型** | Llama 4 Scout 70B, Qwen3 235B | 性能强 |
| **本地中型** | Qwen3 14B, DeepSeek-R1 32B | 平衡 |
| **本地小型** | Gemma3 9B, Llama 4 8B | 轻量 |
| **企业Agent** | Claude Opus 4.8, Qwen3.7-Max | 工具使用 |
| **边缘设备** | Gemma3 2B, Llama 3.2 3B | 边缘优化 |

---

## 🔗 相关文档

- [配置指南](../zh-CN/README.md) - 详细配置说明
- [快速开始](../zh-CN/README.md) - 模型配置步骤

---

<div align="center">

**选择适合您场景的模型** 🚀

[返回主页](./README.md)

</div>
