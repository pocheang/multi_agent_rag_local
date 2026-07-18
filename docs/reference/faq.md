 # ❓ 常见问题解答（FAQ）

> QueryMind 使用过程中的常见问题和解决方案

---

## 📋 目录

- [安装和部署](#安装和部署)
- [模型配置](#模型配置)
- [使用问题](#使用问题)
- [性能优化](#性能优化)
- [故障排查](#故障排查)
- [开发相关](#开发相关)

---

## 安装和部署

### Q: 最低系统配置要求是什么？

**A:** 

**开发环境**：
- CPU: 4核心
- 内存: 8 GB
- 硬盘: 50 GB
- Python 3.11+
- Node.js 18+

**生产环境**：
- CPU: 8核心+
- 内存: 16 GB+
- 硬盘: 100 GB+
- 稳定网络连接

### Q: 支持哪些操作系统？

**A:** 
- ✅ Linux (Ubuntu 22.04+, CentOS 8+, Debian 11+)
- ✅ macOS (12.0+)
- ✅ Windows 10/11 (WSL2推荐)

### Q: 如何快速部署？

**A:** 最快的方式是使用Docker Compose：

```bash
# 1. 克隆仓库
git clone https://github.com/YOUR_USERNAME/querymind.git
cd querymind

# 2. 配置环境变量
cp .env.example .env
# 编辑 .env 配置必要参数

# 3. 启动服务
docker-compose up -d

# 4. 访问
# 前端: http://localhost:5173
# 后端API: http://localhost:8000
```

### Q: Docker部署失败怎么办？

**A:** 常见原因和解决方案：

1. **端口被占用**
   ```bash
   # 查看端口占用
   netstat -tulpn | grep 8000
   # 修改 docker-compose.yml 中的端口映射
   ```

2. **权限问题**
   ```bash
   sudo usermod -aG docker $USER
   # 重新登录生效
   ```

3. **磁盘空间不足**
   ```bash
   docker system prune -a
   ```

---

## 模型配置

### Q: 如何选择合适的模型？

**A:** 根据场景选择：

| 场景 | 推荐模型 | 原因 |
|------|---------|------|
| **生产环境** | GPT-5.5, Claude Opus 4.8 | 最强能力 |
| **中文任务** | Qwen 3.7 Max, DeepSeek-V4 | 中文优化 |
| **本地部署** | Qwen3:14b, Llama 4 Scout | 开源可控 |
| **成本优先** | DeepSeek-V4, Gemini Flash | 高性价比 |
| **代码生成** | GPT-5.3-Codex, Qwen3-Coder | 代码专用 |

详见：[模型选择指南](models.md)

### Q: Ollama模型下载很慢怎么办？

**A:** 使用国内镜像：

```bash
# 设置镜像
export OLLAMA_HOST=https://ollama.ai

# 或使用代理
export http_proxy=http://127.0.0.1:7890
export https_proxy=http://127.0.0.1:7890

# 下载模型
ollama pull qwen3:14b
```

### Q: 如何切换不同的模型提供商？

**A:** 修改 `.env` 文件：

```bash
# 使用本地Ollama
MODEL_BACKEND=ollama
OLLAMA_CHAT_MODEL=qwen3:14b

# 使用OpenAI
MODEL_BACKEND=openai
OPENAI_API_KEY=sk-...
OPENAI_CHAT_MODEL=gpt-5.5

# 使用Anthropic
MODEL_BACKEND=anthropic
ANTHROPIC_API_KEY=sk-ant-...
ANTHROPIC_CHAT_MODEL=claude-opus-4-8
```

重启服务后生效。

### Q: API密钥配置错误怎么排查？

**A:** 检查步骤：

```bash
# 1. 验证密钥格式
echo $OPENAI_API_KEY  # 应以 sk- 开头

# 2. 测试API连接
curl https://api.openai.com/v1/models \
  -H "Authorization: Bearer $OPENAI_API_KEY"

# 3. 查看日志
tail -f logs/app.log | grep "API"
```

---

## 使用问题

### Q: 上传文档后无法检索到内容？

**A:** 可能原因：

1. **文档还在处理中**
   - 等待几分钟，查看处理状态
   - 检查后台日志

2. **文档格式不支持**
   ```bash
   # 支持的格式
   - PDF (推荐)
   - TXT
   - DOCX
   - Markdown
   ```

3. **向量索引未更新**
   ```bash
   # 手动触发重新索引
   curl -X POST http://localhost:8000/api/documents/reindex
   ```

### Q: 查询响应很慢怎么办？

**A:** 优化建议：

1. **启用缓存**
   ```bash
   # .env
   ENABLE_CACHE=true
   REDIS_URL=redis://localhost:6379
   ```

2. **调整检索参数**
   ```bash
   # 减少检索数量
   TOP_K=3  # 默认5
   MAX_CONTEXT_CHUNKS=4  # 默认6
   ```

3. **使用更快的模型**
   ```bash
   # Ollama本地模型更快
   MODEL_BACKEND=ollama
   OLLAMA_CHAT_MODEL=qwen3:7b  # 小模型更快
   ```

### Q: 答案质量不好怎么改进？

**A:** 改进方法：

1. **使用更强的模型**
   - GPT-5.5, Claude Opus 4.8

2. **优化文档质量**
   - 确保文档内容清晰、结构化
   - 删除无关内容

3. **调整检索参数**
   ```bash
   # 增加上下文
   MAX_CONTEXT_CHUNKS=8
   
   # 提高相似度阈值
   VECTOR_SIMILARITY_THRESHOLD=0.3
   ```

4. **启用重排序**
   ```bash
   ENABLE_RERANKER=true
   ```

### Q: 如何实现多轮对话？

**A:** 前端自动处理会话上下文：

```python
# Python客户端示例
import requests

session_id = None
messages = []

def chat(query):
    global session_id
    response = requests.post(
        "http://localhost:8000/api/chat/query",
        json={
            "query": query,
            "session_id": session_id,
            "history": messages[-10:]  # 保留最近10轮
        }
    )
    result = response.json()
    session_id = result.get("session_id")
    messages.append({"role": "user", "content": query})
    messages.append({"role": "assistant", "content": result["answer"]})
    return result["answer"]

# 使用
print(chat("什么是RAG？"))
print(chat("它有什么优势？"))  # 自动关联上下文
```

---

## 性能优化

### Q: 如何提高并发处理能力？

**A:** 

1. **增加Worker数量**
   ```bash
   # 启动时指定
   uvicorn app.api.main:app --workers 8
   ```

2. **启用Redis缓存**
   ```bash
   REDIS_URL=redis://localhost:6379
   CACHE_TTL=3600
   ```

3. **使用负载均衡**
   ```nginx
   upstream querymind {
       server 127.0.0.1:8000;
       server 127.0.0.1:8001;
       server 127.0.0.1:8002;
   }
   ```

详见：[性能优化指南](../operations/performance.md)

### Q: 内存占用太高怎么办？

**A:** 

1. **使用小模型**
   ```bash
   OLLAMA_CHAT_MODEL=qwen3:7b  # 代替 14b
   ```

2. **限制上下文大小**
   ```bash
   MAX_CONTEXT_CHUNKS=4
   MAX_HISTORY_MESSAGES=5
   ```

3. **启用流式处理**
   ```bash
   STREAM_RESPONSE=true
   ```

---

## 故障排查

### Q: 启动失败，报端口占用？

**A:** 

```bash
# 查找占用端口的进程
lsof -i :8000
# 或
netstat -tulpn | grep 8000

# 杀死进程
kill -9 <PID>

# 或修改端口
export PORT=8001
uvicorn app.api.main:app --port 8001
```

### Q: 数据库连接失败？

**A:** 

```bash
# 检查数据库服务
systemctl status postgresql

# 测试连接
psql -h localhost -U querymind -d querymind

# 检查配置
echo $DATABASE_URL
```

### Q: 向量数据库ChromaDB报错？

**A:** 

```bash
# 清理并重建
rm -rf data/chroma
python scripts/rebuild_index.py

# 检查权限
chmod -R 755 data/chroma
```

### Q: 日志在哪里查看？

**A:** 

```bash
# 应用日志
tail -f logs/app.log

# Docker日志
docker-compose logs -f

# Systemd日志
journalctl -u querymind -f
```

---

## 开发相关

### Q: 如何搭建开发环境？

**A:** 

```bash
# 1. 创建虚拟环境
conda create -n querymind python=3.11
conda activate querymind

# 2. 安装依赖
pip install -r requirements.txt
pip install -r requirements-dev.txt

# 3. 安装前端依赖
cd frontend && npm install

# 4. 启动开发服务器
# 后端
uvicorn app.api.main:app --reload

# 前端
cd frontend && npm run dev
```

### Q: 如何运行测试？

**A:** 

```bash
# 后端测试
pytest tests/ -v

# 测试覆盖率
pytest --cov=app tests/

# 前端测试
cd frontend && npm test

# 集成测试
pytest tests/integration/ -v
```

### Q: 如何添加新的Agent？

**A:** 参考 [Agent集成指南](../development/agent-integration.md)

### Q: 如何贡献代码？

**A:** 

1. Fork项目
2. 创建功能分支
3. 编写代码和测试
4. 提交Pull Request

详见：[贡献指南](../../CONTRIBUTING.md)

### Q: 代码规范是什么？

**A:** 

**Python**:
```bash
# 格式化
black app/
isort app/

# 检查
pylint app/
mypy app/
```

**TypeScript**:
```bash
cd frontend
npm run format
npm run lint
npm run type-check
```

---

## 其他问题

### Q: 支持哪些语言？

**A:** 
- ✅ 中文（优化支持）
- ✅ 英文
- ⚠️ 其他语言（基础支持，取决于模型能力）

### Q: 数据安全性如何？

**A:** 
- ✅ 支持本地部署（数据不出内网）
- ✅ RBAC权限控制
- ✅ JWT认证
- ✅ 数据加密存储
- ✅ 审计日志

详见：[安全政策](../../SECURITY.md)

### Q: 商业使用需要授权吗？

**A:** 
- ✅ MIT协议，可免费商用
- ✅ 无需额外授权
- ⚠️ 请保留版权声明

### Q: 如何获取技术支持？

**A:** 
- 📋 [GitHub Issues](https://github.com/YOUR_USERNAME/querymind/issues)
- 💬 [GitHub Discussions](https://github.com/YOUR_USERNAME/querymind/discussions)
- 📖 [完整文档](../zh-CN/README.md)

---

## 🔗 相关文档

- [快速开始](../zh-CN/README.md)
- [配置指南](../zh-CN/README.md)
- [故障排查](../zh-CN/README.md)
- [性能优化](../operations/performance.md)
- [API使用示例](api-examples.md)

---

<div align="center">

**找不到答案？** [提交Issue](https://github.com/YOUR_USERNAME/querymind/issues/new) 💬

[返回主页](./README.md)

</div>
