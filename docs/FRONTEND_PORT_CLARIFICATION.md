# 🔧 前端运行方式说明 - 重要更正

## ⚠️ 重要：前端架构说明

这个项目有**两种前端运行方式**：

---

## 📊 架构说明

### 方式1: 开发模式 - 独立前端服务器 🔧

**前端**: Vite Dev Server (端口 5173)  
**后端**: FastAPI (端口 8000)  
**通信**: Vite代理转发API请求

```
前端: http://localhost:5173  ← 开发时访问这个
后端: http://localhost:8000  ← API服务
```

**启动步骤**:
```bash
# Terminal 1: 启动后端
cd c:/Users/pocheang/Desktop/llm/multi_agent_rag_local_v4
uvicorn app.api.main:app --host 0.0.0.0 --port 8000 --reload

# Terminal 2: 启动前端
cd frontend
npm run dev
# 前端运行在: http://localhost:5173
```

**访问**:
```
http://localhost:5173  ← 访问React前端
→ 登录 → Admin → Web Activity
```

---

### 方式2: 生产模式 - 单一服务器 📦

**前端**: 构建后的静态文件 (由FastAPI服务)  
**后端**: FastAPI (端口 8000)  
**通信**: 同源，无需代理

```
全栈: http://localhost:8000  ← 生产环境访问
```

**构建步骤**:
```bash
# 1. 构建前端
cd frontend
npm run build
# 输出到: frontend/dist/

# 2. FastAPI自动服务静态文件
# app/api/main.py 已配置:
# app.mount("/app/assets", StaticFiles(directory=...))
```

**访问**:
```
http://localhost:8000  ← 访问生产构建
→ 登录 → Admin → Web Activity
```

---

## 🎯 当前状态

### 后端 ✅ 运行中
```
端口: 8000
状态: ✅ Running
健康检查: http://localhost:8000/api/v1/admin/web-activity/health
```

### 前端 ⚠️ 需要确认

**选项A: 开发模式** (推荐用于开发)
```bash
cd frontend
npm run dev
# 访问: http://localhost:5173
```

**选项B: 生产模式** (已构建，通过8000访问)
```bash
# 已完成构建
# 访问: http://localhost:8000
```

---

## 🔍 检查前端是否在8000端口可用

让我检查React构建是否已正确挂载：

```bash
# 检查React构建文件
ls frontend/dist/

# 检查FastAPI是否挂载了静态文件
curl http://localhost:8000/ | head -20
```

---

## 💡 建议

### 开发环境（推荐）

**同时运行前后端**:
```bash
# Terminal 1: 后端
uvicorn app.api.main:app --reload

# Terminal 2: 前端  
cd frontend && npm run dev
```

**访问**: `http://localhost:5173`

**优点**:
- ✅ 热重载
- ✅ 快速开发
- ✅ 实时预览

### 生产环境

**只运行后端**:
```bash
uvicorn app.api.main:app --host 0.0.0.0 --port 8000
```

**访问**: `http://localhost:8000`

**优点**:
- ✅ 单一端口
- ✅ 生产优化
- ✅ 部署简单

---

## 🚀 现在应该怎么做？

### 选项1: 启动开发模式（推荐）

```bash
# 新开一个终端
cd c:/Users/pocheang/Desktop/llm/multi_agent_rag_local_v4/frontend
npm run dev
```

然后访问: **http://localhost:5173**

### 选项2: 使用生产构建

直接访问: **http://localhost:8000**

（前提是React构建文件已正确挂载到FastAPI）

---

## 📝 Web Activity Dashboard 访问

### 如果使用开发模式（5173）

```
http://localhost:5173
→ 登录: admin / admin123
→ Admin → Web Activity
```

### 如果使用生产模式（8000）

```
http://localhost:8000
→ 登录: admin / admin123
→ Admin → Web Activity
```

### 备用方案（独立Dashboard）

```
http://localhost:8000/api/v1/admin/web-activity/dashboard
```

这个总是可用的，不需要React前端！

---

## ✅ 总结

- **后端**: ✅ 运行在 8000 端口
- **前端开发**: 应该运行在 5173 端口
- **前端生产**: 通过 8000 端口访问（如果已挂载）
- **备用方案**: 独立HTML Dashboard 在 8000 端口

你想用哪种方式？我可以帮你启动！
