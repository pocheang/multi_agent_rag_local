# 黑屏问题排查指南

## 问题描述
在聊天界面提问后，页面出现黑屏或无响应。

## 可能的原因

### 1. 前端状态卡住
**症状**: 页面显示"Processing"或加载状态，但没有响应
**解决方法**:
- 刷新浏览器页面 (F5 或 Ctrl+R)
- 清除浏览器缓存后重新加载
- 检查浏览器控制台 (F12) 是否有 JavaScript 错误

### 2. 流式响应超时
**症状**: 请求发送了但长时间没有响应
**原因**: 
- Ollama 模型响应慢
- 查询太复杂导致处理时间长
- 网络连接问题

**解决方法**:
```powershell
# 检查 Ollama 是否正常
Invoke-WebRequest -Uri "http://localhost:11434/api/tags" -UseBasicParsing

# 测试 Ollama 模型响应
curl http://localhost:11434/api/generate -d '{
  "model": "qwen2.5:7b-instruct",
  "prompt": "Hello",
  "stream": false
}'
```

### 3. 后端错误未正确处理
**检查后端日志**:
查看后端窗口或日志文件，寻找错误信息

### 4. 前端流式处理错误
**症状**: 数据返回了但前端没有正确解析
**检查**: 
- 打开浏览器开发者工具 (F12)
- 查看 Network 标签
- 找到 `/query/stream` 请求
- 查看 Response 内容是否正常

## 快速修复步骤

### 步骤 1: 刷新页面
```
按 F5 或 Ctrl+R 刷新浏览器
```

### 步骤 2: 检查服务状态
```powershell
# 检查后端端口
netstat -ano | findstr :8000

# 检查前端端口
netstat -ano | findstr :5173

# 检查 Ollama
netstat -ano | findstr :11434
```

### 步骤 3: 重启服务
如果服务卡住，重启它们：

```powershell
# 停止所有相关进程
Get-Process | Where-Object {$_.ProcessName -like "*python*" -or $_.ProcessName -like "*node*"} | Stop-Process -Force

# 重新启动
conda activate rag-local`nuvicorn app.api.main:app --reload --port 8000
```

### 步骤 4: 使用更简单的查询测试
尝试一个简单的问题，比如"你好"，看看是否能正常响应。

### 步骤 5: 检查模型是否卡住
```powershell
# 查看 Ollama 进程
Get-Process ollama

# 如果 CPU 使用率很高，可能模型在处理中
# 等待一段时间或重启 Ollama
```

## 预防措施

1. **避免过长或过于复杂的查询** - 可能导致模型处理时间过长
2. **定期重启服务** - 长时间运行可能导致内存泄漏
3. **监控资源使用** - 确保系统有足够的内存和 CPU
4. **使用更快的模型** - 如果 7B 模型太慢，考虑使用更小的模型或 API 服务

## 配置调整

如果问题频繁出现，可以调整 `.env` 配置：

```env
# 增加超时时间（毫秒）
QUERY_REQUEST_TIMEOUT_MS=120000

# 减少心跳间隔（秒）
STREAM_HEARTBEAT_SECONDS=3

# 使用更快的模型
OLLAMA_CHAT_MODEL=gemma3:4b
```

## 联系支持

如果以上方法都无法解决问题，请：
1. 记录浏览器控制台的错误信息
2. 记录后端日志的错误信息
3. 记录复现步骤
4. 提交 Issue 到项目仓库
