# 流式生成延迟问题诊断与解决方案

## 问题现象

用户报告："思考很久，然后一下子就有结果了，来不及看流式生成"

这说明答案是在后端生成完成后**一次性发送**，而不是在生成过程中**实时流式发送**。

## 诊断结果

### ✅ 前端流式处理正确
- `consumeChatStream()` 正确处理 SSE
- `handleAnswerChunkEvent()` 处理每个 chunk
- `flushSync()` 强制立即渲染
- 自动滚动和闪烁光标已实现

### ✅ 后端流式代码正确
```python
# app/agents/synthesizer/generation.py:568
for chunk in model.stream([("system", ANSWER_PROMPT), ("human", prompt)]):
    content = getattr(chunk, "content", None)
    if content:
        text = str(content)
        parts.append(text)
        yield text  # ← 这里立即 yield
```

### ❌ 可能的问题点

1. **LangChain 模型配置**
   - 没有显式启用 `streaming=True`
   - 可能存在内部缓冲

2. **网络/WSGI 缓冲**
   - Uvicorn 可能缓冲响应
   - 反向代理（Nginx）可能启用缓冲

3. **LLM API 本身的延迟**
   - OpenAI/Anthropic API 可能先完整生成再返回
   - 某些模型不支持真正的流式

## 解决方案

### 方案 1: 确保 LangChain 模型启用流式

修改 `app/services/models/runtime.py`:

```python
def _build_chat_model_cached(...):
    if backend == "openai":
        from langchain_openai import ChatOpenAI
        
        kwargs = {
            "model": openai_model,
            "temperature": temperature,
            "streaming": True,  # ← 显式启用流式
        }
        if openai_api_key:
            kwargs["api_key"] = openai_api_key
        if openai_base_url:
            kwargs["base_url"] = openai_base_url
        if max_tokens > 0:
            kwargs["max_tokens"] = max_tokens
        return _wrap_chat_model_for_provider(ChatOpenAI(**kwargs), provider=provider)
    
    if backend == "anthropic":
        from langchain_anthropic import ChatAnthropic
        
        kwargs = {
            "model": anthropic_model,
            "temperature": temperature,
            "streaming": True,  # ← 显式启用流式
        }
        if anthropic_api_key:
            kwargs["api_key"] = anthropic_api_key
        if max_tokens > 0:
            kwargs["max_tokens"] = max_tokens
        return _wrap_chat_model_for_provider(ChatAnthropic(**kwargs), provider=provider)
    
    if backend == "ollama":
        from langchain_ollama import ChatOllama
        
        kwargs = {
            "model": ollama_model,
            "base_url": ollama_base_url,
            "temperature": temperature,
            "streaming": True,  # ← 显式启用流式
        }
        if max_tokens > 0:
            kwargs["num_predict"] = max_tokens
        return ChatOllama(**kwargs)
```

### 方案 2: 禁用 Uvicorn 缓冲

在 `app/api/dependencies.py` 或响应头中添加：

```python
def _sse_response(events, append_terminal_event: bool = False) -> StreamingResponse:
    # ... existing code ...
    
    return StreamingResponse(
        content=events_with_terminal if append_terminal_event else events,
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # ← 禁用 Nginx 缓冲
        },
    )
```

### 方案 3: 添加流式诊断日志

在 `app/agents/synthesizer/generation.py` 中添加调试：

```python
def stream_synthesize_answer(...):
    # ... existing code ...
    
    try:
        with bulkhead("llm"):
            model = _build_generation_model(use_reasoning=use_reasoning, question=question)
            parts: list[str] = []
            stream_failed = False
            chunk_count = 0
            start_time = time.time()
            
            try:
                for chunk in model.stream([("system", ANSWER_PROMPT), ("human", prompt)]):
                    content = getattr(chunk, "content", None)
                    if content:
                        text = str(content)
                        parts.append(text)
                        chunk_count += 1
                        elapsed = time.time() - start_time
                        
                        # 诊断日志
                        logger.debug(
                            f"Stream chunk #{chunk_count} at {elapsed:.2f}s: "
                            f"{len(text)} chars, total {len(''.join(parts))} chars"
                        )
                        
                        yield text
            except Exception as stream_error:
                logger.warning(f"Stream failed after {chunk_count} chunks: {type(stream_error).__name__}")
                stream_failed = True
```

### 方案 4: 检查实际使用的模型

不同模型的流式表现不同：

```python
# 在配置或日志中记录
logger.info(
    f"Using model: {model.__class__.__name__}, backend: {backend}, model_name: {openai_model or anthropic_model or ollama_model}"
)
```

**已知情况**：
- ✅ GPT-4, GPT-3.5: 支持良好的流式
- ✅ Claude 3.5 Sonnet: 支持良好的流式
- ⚠️ 某些自定义模型/代理可能不支持流式
- ❌ Local 模式: 不支持流式（返回完整答案）

## 快速测试步骤

### 1. 检查后端日志

启动后端时设置日志级别为 DEBUG：

```bash
export LOG_LEVEL=DEBUG
uvicorn app.api.main:app --reload --port 8000
```

发送问题后查看日志中是否有：
- ✅ `Stream chunk #1 at 0.5s` - 说明流式正常
- ❌ 只有一次 chunk 或延迟很久才有第一个 chunk - 说明有问题

### 2. 检查 SSE 原始输出

使用 `curl` 直接测试 SSE 端点：

```bash
curl -N -X POST http://127.0.0.1:8000/query/stream \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -F "question=解释什么是RAG系统" \
  -F "session_id=test-session" \
  -F "use_web_fallback=false"
```

观察输出：
- ✅ 看到多个 `data: {"type":"answer_chunk",...}` 事件逐渐出现
- ❌ 等待很久后一次性输出所有内容

### 3. 检查浏览器 Network 面板

1. 打开浏览器开发者工具
2. 切换到 Network 标签
3. 发送问题
4. 查找 `/query/stream` 请求
5. 查看 EventStream 标签

**正常情况**：应该看到多个 `answer_chunk` 事件逐个到达
**异常情况**：长时间等待后一次性收到所有事件

## 最可能的原因

根据代码审查，**最可能的原因**是：

### 问题：LangChain 模型未显式启用 `streaming=True`

虽然调用了 `model.stream()`，但如果模型初始化时没有设置 `streaming=True`，某些 LangChain 实现可能会：
1. 在内部调用完整的 `invoke()`
2. 将完整结果分块后再"伪装"成流式返回
3. 这导致"思考很久"（等待完整生成），然后"一下子出现"（快速发送所有 chunk）

## 推荐实施顺序

1. ✅ **立即实施方案 1**: 添加 `streaming=True` 参数
2. ✅ **立即实施方案 2**: 添加 `X-Accel-Buffering: no` 响应头
3. 📊 **实施方案 3**: 添加诊断日志（临时，用于确认问题）
4. 🔍 **执行快速测试步骤 1-3**: 验证流式是否正常

## 预期效果

修复后的体验：

```
0.0s: 用户发送问题
0.5s: ◌ 正在思考
2.0s: 开始收到第一个 chunk "RAG"
2.1s: "RAG 系"
2.2s: "RAG 系统"
2.3s: "RAG 系统可以"
2.5s: "RAG 系统可以通过"
...持续流式输出，每 0.1-0.3 秒增加新内容
10.0s: 完整答案生成完成
```

## 备用方案：前端模拟流式

如果后端无法真正流式（例如使用不支持流式的模型），可以在前端添加"打字机效果"：

```typescript
// frontend/src/pages/chat/hooks/streamMessageUpdater.ts

patchStreamMessage: (content: string, meta: StreamMetadata) => {
  // 如果内容突然增加很多，说明是批量到达，需要模拟打字机
  const currentContent = getCurrentContent(); // 获取当前内容
  const newChars = content.length - currentContent.length;
  
  if (newChars > 50) {
    // 批量到达，使用打字机效果
    typewriterEffect(currentContent, content, setMessages, meta);
  } else {
    // 正常流式，立即渲染
    flushSync(() => {
      setMessages((prev) => prev.map(...));
    });
  }
}
```

**但这是最后的手段**，应该优先修复后端真正的流式生成。

## 完成时间

2026-08-17 18:00

## 下一步

1. 修改 `app/services/models/runtime.py` 添加 `streaming=True`
2. 修改响应头添加 `X-Accel-Buffering: no`
3. 重启后端测试
4. 观察浏览器 Network 面板和后端日志
5. 确认流式生成正常工作
