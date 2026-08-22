# 流式生成和长文本配置指南

## 问题说明

### 问题 1：看不到流式生成效果
**原因**：系统当前使用 `local` 模式（默认配置），这是一个离线的简化模型，不支持真正的流式生成。

### 问题 2：答案太短
**原因**：Local 模式生成的答案是固定模板，只返回检索到的证据摘要（4 条，每条最多 360 字符）。

## 解决方案

### 方案 1：配置真实 LLM（推荐）

要获得真正的流式生成和长答案，需要配置以下任一 LLM：

#### 选项 A：OpenAI (GPT-4/GPT-3.5)

1. 在项目根目录创建 `.env` 文件：
```bash
# .env
MODEL_BACKEND=openai
OPENAI_API_KEY=sk-your-api-key-here
OPENAI_CHAT_MODEL=gpt-4o
OPENAI_BASE_URL=https://api.openai.com/v1
```

2. 重启后端：
```bash
conda activate rag-local
uvicorn app.api.main:app --reload --port 8000
```

**优点**：
- ✅ 真正的流式生成
- ✅ 长答案（可达数千字）
- ✅ 高质量输出
- ✅ 支持推理和工具调用

**成本**：
- GPT-4o: ~$2.50 / 1M tokens 输入，~$10 / 1M tokens 输出
- GPT-3.5-turbo: ~$0.50 / 1M tokens 输入，~$1.50 / 1M tokens 输出

#### 选项 B：Anthropic (Claude)

1. 创建 `.env` 文件：
```bash
# .env
MODEL_BACKEND=anthropic
ANTHROPIC_API_KEY=sk-ant-your-api-key-here
ANTHROPIC_CHAT_MODEL=claude-3-5-sonnet-20241022
```

2. 重启后端

**优点**：
- ✅ 真正的流式生成
- ✅ 超长上下文（200K tokens）
- ✅ 高质量输出
- ✅ 更快的响应速度

**成本**：
- Claude 3.5 Sonnet: ~$3 / 1M tokens 输入，~$15 / 1M tokens 输出

#### 选项 C：Ollama (本地免费)

1. 安装 Ollama：
   - 访问 https://ollama.ai/download
   - 下载并安装

2. 拉取模型：
```bash
ollama pull llama3.1:8b
# 或者更大的模型
ollama pull llama3.1:70b
```

3. 创建 `.env` 文件：
```bash
# .env
MODEL_BACKEND=ollama
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_CHAT_MODEL=llama3.1:8b
```

4. 重启后端

**优点**：
- ✅ 完全免费
- ✅ 数据隐私（本地运行）
- ✅ 真正的流式生成
- ✅ 无需 API key

**缺点**：
- ⚠️ 需要较好的硬件（8B 模型需要至少 8GB RAM）
- ⚠️ 速度取决于本地硬件

### 方案 2：改进 Local 模式（临时方案）

如果暂时无法配置真实 LLM，我已经改进了 Local 模式：

**已实施的改进**：
- ✅ 模拟流式生成（每 3-5 个词发送一次）
- ✅ 50ms 延迟模拟真实网络延迟

**限制**：
- ❌ 仍然是固定模板，不是真正的 AI 生成
- ❌ 答案长度有限（最多 4 个证据片段）
- ❌ 无法生成长文本分析

## 如何生成长文本答案

配置真实 LLM 后，要获得长答案：

### 1. 提问方式优化

**不好的提问**（导致短答案）：
```
什么是 RAG？
```

**好的提问**（获得长答案）：
```
请详细解释 RAG 系统的完整架构，包括：
1. 核心组件和工作流程
2. 检索策略的设计
3. 向量数据库的选择
4. 重排序机制
5. 答案生成和引用
6. 质量保障措施
请提供具体实现细节和代码示例。
```

### 2. 调整模型参数（可选）

在 `.env` 中添加：
```bash
# 增加最大输出长度
OPENAI_MAX_TOKENS=4000

# 或对于 Anthropic
ANTHROPIC_MAX_TOKENS=4000
```

### 3. 使用推理模式

在前端界面中：
- 启用"使用推理"开关
- 这会激活更强的推理能力，生成更深入的分析

## 验证配置

### 1. 检查后端日志

启动后端后，查看日志中的模型信息：

```bash
# 应该看到类似：
INFO: Using backend: openai, model: gpt-4o
# 或
INFO: Using backend: anthropic, model: claude-3-5-sonnet
# 或
INFO: Using backend: ollama, model: llama3.1:8b
```

如果看到：
```bash
INFO: Using backend: local
```
说明仍在使用 Local 模式。

### 2. 测试流式生成

发送问题后：
- ✅ **真实 LLM**：文字逐渐流式出现，带闪烁光标
- ❌ **Local 模式**：即使有模拟流式，答案仍然是固定模板

### 3. 测试长答案

发送详细问题：
```
请详细解释深度学习中的 Transformer 架构，包括自注意力机制、位置编码、多头注意力、前馈网络等核心组件，并说明在 NLP 任务中的应用。
```

- ✅ **真实 LLM**：生成 1000+ 字的详细分析
- ❌ **Local 模式**：只返回检索到的证据摘要

## 推荐配置

### 开发/测试环境
```bash
# 使用 Ollama（免费本地）
MODEL_BACKEND=ollama
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_CHAT_MODEL=llama3.1:8b
```

### 生产环境（高质量）
```bash
# 使用 Claude 3.5 Sonnet
MODEL_BACKEND=anthropic
ANTHROPIC_API_KEY=your-key-here
ANTHROPIC_CHAT_MODEL=claude-3-5-sonnet-20241022
```

### 生产环境（性价比）
```bash
# 使用 GPT-4o-mini
MODEL_BACKEND=openai
OPENAI_API_KEY=your-key-here
OPENAI_CHAT_MODEL=gpt-4o-mini
```

## 当前系统状态

根据配置文件 `app/core/config.py`：
```python
model_backend: str = Field(default="local", alias="MODEL_BACKEND")
```

**当前默认**: `local` 模式

**要改变**: 创建 `.env` 文件设置 `MODEL_BACKEND`

## 常见问题

### Q: 为什么默认是 local 模式？
A: 为了让系统在没有 API key 的情况下也能运行，方便快速测试和演示。

### Q: Local 模式能用于生产吗？
A: 不推荐。Local 模式只适合：
- 快速测试系统功能
- 演示检索能力
- 开发调试

### Q: 如何在不同环境使用不同模型？
A: 使用环境变量：
```bash
# 开发
export MODEL_BACKEND=local
# 测试
export MODEL_BACKEND=ollama
# 生产
export MODEL_BACKEND=anthropic
```

### Q: 流式生成需要特殊配置吗？
A: 不需要。我已经在所有真实 LLM 中启用了 `streaming=True`，包括：
- OpenAI
- Anthropic
- Ollama

### Q: 如何控制答案长度？
A: 通过提示词引导：
```
请用 500 字左右解释...
请详细解释（1000+ 字）...
请简要说明（100 字以内）...
```

## 下一步行动

1. **选择一个方案**：
   - 有 API key → 配置 OpenAI 或 Anthropic
   - 想要免费 → 安装 Ollama
   - 只是测试 → 继续使用改进的 Local 模式

2. **创建 `.env` 文件**（如果选择真实 LLM）

3. **重启后端**：
   ```bash
   conda activate rag-local
   uvicorn app.api.main:app --reload --port 8000
   ```

4. **刷新前端浏览器**

5. **发送详细问题测试**

## 相关文档

- OpenAI API: https://platform.openai.com/docs/api-reference
- Anthropic Claude: https://docs.anthropic.com/claude/reference/getting-started-with-the-api
- Ollama: https://ollama.ai/
- LangChain Models: https://python.langchain.com/docs/integrations/chat/

## 完成时间

2026-08-17 18:15
