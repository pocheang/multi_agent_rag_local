# 🚀 QueryMind 项目完整重启指南

## 📋 重启步骤

### 1️⃣ 停止所有服务
```powershell
# 停止所有Python和Node进程
Get-Process | Where-Object { $_.ProcessName -match "python|node" } | Stop-Process -Force
```

### 2️⃣ 启动后端服务
```powershell
# 在项目根目录
cd c:\Users\pocheang\Desktop\llm\multi_agent_rag_local_v4

# 激活虚拟环境（如果有）
.\venv\Scripts\Activate.ps1

# 启动后端
python -m uvicorn app.api.main:app --host 0.0.0.0 --port 8000 --reload
```

**等待看到**: `Application startup complete.`

### 3️⃣ 启动前端服务
```powershell
# 新开一个终端
cd c:\Users\pocheang\Desktop\llm\multi_agent_rag_local_v4\frontend

# 启动前端开发服务器
npm run dev
```

**等待看到**: `Local: http://localhost:5173/`

---

## ✅ 验证服务

### 后端健康检查
```powershell
Invoke-WebRequest -Uri http://localhost:8000/health
```
**期望**: `{"status":"ok"}`

### 前端访问
浏览器打开: http://localhost:5173

---

## 🔧 如果遇到问题

### 端口被占用
```powershell
# 查找占用端口的进程
netstat -ano | findstr :8000
netstat -ano | findstr :5173

# 结束进程（替换PID）
Stop-Process -Id <PID> -Force
```

### 依赖问题
```powershell
# 后端
pip install -r requirements.txt

# 前端
cd frontend
npm install
```

### 数据库问题
```powershell
# 检查数据库文件
ls data/

# 如果需要，重新初始化
python scripts/init_db.py
```

---

## 📊 服务端口

| 服务 | 端口 | URL |
|------|------|-----|
| 后端API | 8000 | http://localhost:8000 |
| 前端Dev | 5173 | http://localhost:5173 |
| 后端文档 | 8000 | http://localhost:8000/docs |

---

## 🎯 启动后检查清单

- [ ] 后端启动成功（8000端口）
- [ ] 前端启动成功（5173端口）
- [ ] 健康检查通过
- [ ] 前端可以访问
- [ ] 登录功能正常
- [ ] 管理控制台可访问

---

最后更新：2026-07-01
