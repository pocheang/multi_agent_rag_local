# 环境搭建指南 (Setup Guide)

本指南将帮助你从零开始搭建 QueryMind（智询） 项目的开发环境。

## 目录

- [系统要求](#系统要求)
- [前置依赖安装](#前置依赖安装)
- [Python 环境配置](#python-环境配置)
- [项目依赖安装](#项目依赖安装)
- [数据库配置](#数据库配置)
- [环境变量配置](#环境变量配置)
- [验证安装](#验证安装)
- [常见问题](#常见问题)

---

## 系统要求

### 硬件要求

- **CPU**: 4核及以上（推荐 8核）
- **内存**: 8GB 及以上（推荐 16GB）
- **磁盘**: 至少 20GB 可用空间
- **GPU**: 可选（用于本地模型推理，NVIDIA GPU 推荐）

### 操作系统

- Windows 10/11
- macOS 12+
- Linux (Ubuntu 20.04+, CentOS 8+)

### 软件版本

| 软件 | 最低版本 | 推荐版本 | 说明 |
|------|---------|---------|------|
| Python | 3.11.0 | 3.11.8 | 核心运行环境 |
| Node.js | 18.0.0 | 20.x LTS | 前端开发 |
| Docker | 20.10.0 | 24.x | 容器化服务 |
| Git | 2.30.0 | 最新版 | 版本控制 |

---

## 前置依赖安装

### 1. 安装 Python 3.11+

#### Windows

**方法一：从官网下载**
```bash
# 访问 https://www.python.org/downloads/
# 下载 Python 3.11.x 安装包并运行
# 注意：勾选 "Add Python to PATH"
```

**方法二：使用 Chocolatey**
```powershell
choco install python311 -y
```

#### macOS

**使用 Homebrew**
```bash
brew install python@3.11
```

#### Linux (Ubuntu/Debian)

```bash
sudo apt update
sudo apt install python3.11 python3.11-venv python3.11-dev
```

**验证安装**
```bash
python --version  # 应显示 Python 3.11.x
```

---

### 2. 安装 Node.js 18+

#### Windows

**从官网下载**
```bash
# 访问 https://nodejs.org/
# 下载 LTS 版本并安装
```

#### macOS

```bash
brew install node@20
```

#### Linux

```bash
# 使用 NodeSource 仓库
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
sudo apt install -y nodejs
```

**验证安装**
```bash
node --version  # 应显示 v18.x 或更高
npm --version   # 应显示 9.x 或更高
```

---

### 3. 安装 Docker

#### Windows

1. 下载 [Docker Desktop for Windows](https://www.docker.com/products/docker-desktop/)
2. 运行安装程序
3. 启动 Docker Desktop
4. 确保 WSL 2 后端已启用

#### macOS

```bash
brew install --cask docker
# 或从官网下载 Docker Desktop for Mac
```

#### Linux

```bash
# Ubuntu/Debian
sudo apt update
sudo apt install docker.io docker-compose
sudo systemctl start docker
sudo systemctl enable docker
sudo usermod -aG docker $USER  # 添加当前用户到 docker 组
```

**验证安装**
```bash
docker --version
docker-compose --version
```

---

### 4. 安装 Git

#### Windows

```powershell
# 使用 Chocolatey
choco install git -y

# 或从官网下载
# https://git-scm.com/download/win
```

#### macOS

```bash
brew install git
```

#### Linux

```bash
sudo apt install git
```

**配置 Git**
```bash
git config --global user.name "Your Name"
git config --global user.email "your.email@example.com"
```

---

## Python 环境配置

我们**强烈推荐**使用 Conda 创建隔离的 Python 环境。

### 方法一：使用 Conda（推荐）

#### 1. 安装 Miniconda/Anaconda

**Windows/macOS**
```bash
# 下载 Miniconda
# https://docs.conda.io/en/latest/miniconda.html
```

**Linux**
```bash
wget https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh
bash Miniconda3-latest-Linux-x86_64.sh
```

#### 2. 创建 Conda 环境

```bash
# 创建名为 rag-local 的环境
conda create -n rag-local python=3.11 -y

# 激活环境
conda activate rag-local

# 验证 Python 版本
python --version  # 应显示 Python 3.11.x
```

#### 3. 配置环境自动激活（可选）

**Windows PowerShell**
```powershell
# 将以下内容添加到 PowerShell 配置文件
notepad $PROFILE

# 添加这一行：
conda activate rag-local
```

**macOS/Linux Bash/Zsh**
```bash
# 添加到 ~/.bashrc 或 ~/.zshrc
echo "conda activate rag-local" >> ~/.bashrc
source ~/.bashrc
```

---

### 方法二：使用 venv

如果你不想使用 Conda，可以使用 Python 内置的 venv：

#### Windows PowerShell

```powershell
# 创建虚拟环境
python -m venv .venv

# 激活虚拟环境
.venv\Scripts\Activate.ps1

# 如果遇到执行策略错误，运行：
Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned
```

#### macOS/Linux

```bash
# 创建虚拟环境
python -m venv .venv

# 激活虚拟环境
source .venv/bin/activate
```

---

## 项目依赖安装

### 1. 克隆项目

```bash
# 克隆仓库
git clone https://github.com/your-org/querymind.git
cd querymind

# 或者如果你已经有项目
cd /path/to/multi_agent_rag_local_v4
```

### 2. 升级 pip

```bash
# 确保使用最新的 pip
pip install -U pip
```

### 3. 安装核心依赖

**基础安装**（包含核心功能）：
```bash
pip install -e .
```

这将安装：
- FastAPI 后端框架
- LangChain 和 LangGraph
- ChromaDB 向量数据库
- Neo4j 图数据库客户端
- 基础 PDF 解析（pypdf）
- BM25 检索
- 中文分词（jieba）

### 4. 安装可选依赖

根据你的需求安装额外功能：

**OCR 支持**（扫描 PDF 和图片文本提取）：
```bash
pip install -e ".[ocr]"
```

**重排序模型**（提高检索精度）：
```bash
pip install -e ".[reranker]"
```

**高级文档解析**（Docling - 结构化 PDF/DOCX/PPTX）：
```bash
pip install -e ".[docling]"
```

**PaddleOCR**（中文友好的 OCR，约 500MB）：
```bash
pip install -e ".[paddle]"
```

**完整安装**（包含所有可选功能）：
```bash
pip install -e ".[full]"
```

**开发工具**（测试、代码质量检查）：
```bash
pip install -e ".[dev]"
```

### 5. 安装前端依赖

```bash
cd frontend
npm install
cd ..
```

---

## 数据库配置

### 1. 启动 Neo4j（知识图谱）

使用 Docker Compose 启动 Neo4j：

```bash
# 启动 Neo4j
docker-compose up -d neo4j

# 查看日志
docker-compose logs -f neo4j

# 等待 Neo4j 完全启动（约 30 秒）
```

**验证 Neo4j**：
- 浏览器访问: http://localhost:7474
- 默认用户名: `neo4j`
- 默认密码: `password`（可在 `.env` 中修改）

### 2. ChromaDB（向量数据库）

ChromaDB 使用本地文件存储，无需额外配置。首次运行时会自动创建：
```
data/chroma_db/  # 向量存储目录
```

### 3. SQLite（应用数据库）

SQLite 也是文件数据库，会自动创建：
```
data/app.db      # 用户、会话、文档元数据
```

---

## 环境变量配置

### 1. 创建 .env 文件

```bash
# 复制示例配置文件
cp .env.example .env

# Windows PowerShell
copy .env.example .env
```

### 2. 基础配置

编辑 `.env` 文件，配置以下必需项：

```bash
# ============================================
# 模型后端配置（三选一）
# ============================================

# 选项 1: OpenAI
MODEL_BACKEND=openai
OPENAI_API_KEY=sk-your-api-key-here
OPENAI_CHAT_MODEL=gpt-4-turbo
OPENAI_EMBED_MODEL=text-embedding-3-small

# 选项 2: Anthropic
MODEL_BACKEND=anthropic
ANTHROPIC_API_KEY=sk-ant-your-api-key-here
ANTHROPIC_CHAT_MODEL=claude-3-5-sonnet-20241022
# 注意：Anthropic 需要 OpenAI 的嵌入模型
OPENAI_API_KEY=sk-your-openai-key-for-embeddings
OPENAI_EMBED_MODEL=text-embedding-3-small

# 选项 3: Ollama（本地模型）
MODEL_BACKEND=ollama
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_CHAT_MODEL=qwen2.5:7b-instruct
OLLAMA_EMBED_MODEL=nomic-embed-text

# ============================================
# 数据库配置
# ============================================
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=password

# ============================================
# 安全配置
# ============================================
# 生成随机密钥的方法：
# python -c "import secrets; print(secrets.token_urlsafe(32))"

JWT_SECRET_KEY=your-jwt-secret-key-here
API_SETTINGS_ENCRYPTION_KEY=your-encryption-key-here
ADMIN_CREATE_APPROVAL_TOKEN_HASH=your-approval-token-hash-here

# ============================================
# 应用配置
# ============================================
DEBUG=true
LOG_LEVEL=INFO
CORS_ORIGINS=http://localhost:5173,http://127.0.0.1:5173
```

### 3. 高级配置（可选）

```bash
# OCR 配置
TESSERACT_CMD=/usr/bin/tesseract  # Tesseract 可执行文件路径
TESSERACT_LANG=eng+chi_sim        # 支持英文和简体中文
OCR_PREPROCESS_ENABLED=true
IMAGE_CAPTION_ENABLED=true

# 检索配置
TOP_K=10
ENABLE_RERANKER=true
RERANKER_MODEL_NAME=BAAI/bge-reranker-v2-m3
RETRIEVAL_PROFILE=balanced  # fast/balanced/deep

# 性能配置
QUERY_REQUEST_TIMEOUT_MS=30000
MAX_UPLOAD_SIZE_MB=100
ENABLE_CACHE=true
```

### 4. 生成安全密钥

```bash
# 生成 JWT 密钥
python -c "import secrets; print('JWT_SECRET_KEY=' + secrets.token_urlsafe(32))"

# 生成加密密钥
python -c "import secrets; print('API_SETTINGS_ENCRYPTION_KEY=' + secrets.token_urlsafe(32))"

# 生成管理员审批令牌哈希
python -c "import hashlib; token='your-secret-token'; print('ADMIN_CREATE_APPROVAL_TOKEN_HASH=' + hashlib.sha256(token.encode()).hexdigest())"
```

---

## 验证安装

### 1. 验证 Python 环境

```bash
# 确保在正确的环境中
conda activate rag-local  # 如果使用 Conda

# 检查 Python 版本
python --version

# 检查已安装的包
pip list | grep -E "langchain|fastapi|chromadb"
```

### 2. 运行后端

```bash
# 从项目根目录运行
uvicorn app.api.main:app --host 127.0.0.1 --port 8000 --reload

# 成功启动后，你应该看到类似输出：
# INFO:     Uvicorn running on http://127.0.0.1:8000 (Press CTRL+C to quit)
# INFO:     Started reloader process
# INFO:     Started server process
# INFO:     Waiting for application startup.
# INFO:     Application startup complete.
```

**验证后端**：
- API 文档: http://127.0.0.1:8000/docs
- 健康检查: http://127.0.0.1:8000/health
- 就绪检查: http://127.0.0.1:8000/ready

### 3. 运行前端

打开新终端：

```bash
cd frontend
npm run dev

# 成功启动后，你应该看到：
# VITE v5.x.x ready in xxx ms
# ➜  Local:   http://localhost:5173/
# ➜  Network: use --host to expose
```

**访问应用**：
- 打开浏览器: http://localhost:5173/app

### 4. 运行测试

```bash
# 回到项目根目录
cd ..

# 运行所有测试
pytest -v

# 运行特定测试
pytest tests/test_routing_logic.py -v

# 运行测试并生成覆盖率报告
pytest --cov=app --cov-report=html
```

### 5. 验证完整流程

```bash
# 1. 摄取测试文档
python scripts/ingest.py

# 2. 运行基准测试
python scripts/benchmark_pipeline.py

# 3. 运行 CI 质量检查
python scripts/ci_quality_gate.py
```

---

## 常见问题

### 问题 1: Python 版本不匹配

**症状**：
```
ERROR: Python 3.11 or later is required.
```

**解决方案**：
```bash
# 检查当前 Python 版本
python --version

# 如果使用 Conda，确保激活了正确的环境
conda activate rag-local

# 如果使用 venv，确保激活了虚拟环境
source .venv/bin/activate  # Linux/macOS
.venv\Scripts\Activate.ps1  # Windows
```

---

### 问题 2: Docker 连接失败

**症状**：
```
Cannot connect to the Docker daemon
```

**解决方案**：
```bash
# 确保 Docker 服务正在运行
# Windows/macOS: 启动 Docker Desktop
# Linux:
sudo systemctl start docker

# 验证 Docker 状态
docker ps
```

---

### 问题 3: Neo4j 连接失败

**症状**：
```
Failed to connect to Neo4j at bolt://localhost:7687
```

**解决方案**：
```bash
# 检查 Neo4j 容器状态
docker-compose ps

# 查看 Neo4j 日志
docker-compose logs neo4j

# 重启 Neo4j
docker-compose restart neo4j

# 等待 30-60 秒让 Neo4j 完全启动
```

---

### 问题 4: 端口被占用

**症状**：
```
ERROR: [Errno 48] Address already in use
```

**解决方案**：
```bash
# Linux/macOS - 查找占用端口的进程
lsof -ti:8000 | xargs kill -9  # 杀死占用 8000 端口的进程

# Windows PowerShell
netstat -ano | findstr :8000
taskkill /PID <PID> /F

# 或者使用不同的端口
uvicorn app.api.main:app --port 8001
```

---

### 问题 5: 依赖安装失败

**症状**：
```
ERROR: Failed building wheel for xxx
```

**解决方案**：
```bash
# 升级 pip 和 setuptools
pip install -U pip setuptools wheel

# 确保安装了编译工具
# Windows: 安装 Visual Studio Build Tools
# Linux: sudo apt install build-essential python3-dev
# macOS: xcode-select --install

# 尝试重新安装
pip install -e . --no-cache-dir
```

---

### 问题 6: ChromaDB 数据库损坏

**症状**：
```
RuntimeError: Error in ChromaDB
```

**解决方案**：
```bash
# 删除现有的 ChromaDB 数据
rm -rf data/chroma_db  # Linux/macOS
rmdir /s data\chroma_db  # Windows

# 重新摄取文档
python scripts/ingest.py
```

---

### 问题 7: 前端构建失败

**症状**：
```
npm ERR! code ELIFECYCLE
```

**解决方案**：
```bash
cd frontend

# 清理缓存和依赖
rm -rf node_modules package-lock.json
npm cache clean --force

# 重新安装
npm install

# 如果还有问题，尝试使用 npm ci
npm ci
```

---

### 问题 8: Ollama 模型未找到

**症状**：
```
Model 'qwen2.5:7b-instruct' not found
```

**解决方案**：
```bash
# 拉取所需的模型
ollama pull qwen2.5:7b-instruct
ollama pull nomic-embed-text

# 列出已安装的模型
ollama list
```

---

---

## 快速参考

### 常用命令速查

```bash
# ============ 环境管理 ============
# 激活 Conda 环境
conda activate rag-local

# 检查 Python 版本
python --version

# 升级 pip
pip install -U pip

# ============ 安装依赖 ============
# 基础安装
pip install -e .

# 完整安装（所有可选功能）
pip install -e ".[full]"

# 开发工具
pip install -e ".[dev]"

# ============ 服务管理 ============
# 启动 Neo4j
docker-compose up -d neo4j

# 查看 Neo4j 日志
docker-compose logs -f neo4j

# 停止所有服务
docker-compose down

# ============ 运行应用 ============
# 启动后端
uvicorn app.api.main:app --host 127.0.0.1 --port 8000 --reload

# 启动前端
cd frontend && npm run dev

# ============ 测试 ============
# 运行所有测试
pytest -v

# 运行测试并生成覆盖率
pytest --cov=app --cov-report=html

# ============ 代码质量 ============
# 格式化代码
ruff format app/ tests/

# 检查代码
ruff check app/ tests/ --fix
```

### 环境变量速查

```bash
# 最小配置
MODEL_BACKEND=local
NEO4J_PASSWORD=your-password

# OpenAI 配置
MODEL_BACKEND=openai
OPENAI_API_KEY=sk-your-key
OPENAI_CHAT_MODEL=gpt-4-turbo
OPENAI_EMBED_MODEL=text-embedding-3-small

# Ollama 配置
MODEL_BACKEND=ollama
OLLAMA_CHAT_MODEL=qwen2.5:7b-instruct
OLLAMA_EMBED_MODEL=nomic-embed-text
```

### 端口速查

| 服务 | 默认端口 | 访问地址 |
|------|---------|---------|
| **后端 API** | 8000 | http://127.0.0.1:8000 |
| **API 文档** | 8000 | http://127.0.0.1:8000/docs |
| **前端** | 5173 | http://localhost:5173/app |
| **Neo4j Browser** | 7474 | http://localhost:7474 |
| **Neo4j Bolt** | 7687 | bolt://localhost:7687 |
| **Redis** | 6379 | redis://localhost:6379 |

### 目录速查

| 目录 | 用途 |
|------|------|
| `data/chroma_db/` | ChromaDB 向量存储 |
| `data/docs/` | 待摄取文档 |
| `data/uploads/` | 用户上传文件 |
| `data/app.db` | SQLite 数据库 |
| `.env` | 环境变量配置 |

---

## 下一步

环境搭建完成后，建议按以下顺序继续学习：

1. **[项目结构](./PROJECT_STRUCTURE.md)** - 了解代码组织
2. **[系统架构](./ARCHITECTURE.md)** - 理解整体设计
3. **[开发流程](./DEVELOPMENT_WORKFLOW.md)** - 学习开发规范
4. **[配置参考](./CONFIGURATION_REFERENCE.md)** - 查看所有配置选项
5. **[API 开发](./API_DEVELOPMENT.md)** - 开始编写代码

---

## 获取帮助

如果遇到本文档未涵盖的问题：

- 查看 [故障排查指南](../troubleshooting-black-screen.md)
- 查看 [快速参考](../quick-reference.md)
- 查看 [配置参考](./CONFIGURATION_REFERENCE.md)
- 提交 [GitHub Issues](https://github.com/your-org/querymind/issues)

---

**更新日期**: 2026-06-19  
**文档版本**: 1.1  
**贡献者**: Bronit Team
