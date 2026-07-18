# 启动指南

**Owner:** QueryMind maintainers  
**Status:** Active  
**Last verified:** 2026-07-17

本项目使用标准命令启动服务，不依赖仓库中不存在的 start-all.ps1、start-backend.ps1 或 start-frontend.ps1 脚本。

## 后端

~~~powershell
conda activate rag-local
uvicorn app.api.main:app --reload --port 8000
~~~

- API 文档：<http://localhost:8000/docs>
- 健康检查：<http://localhost:8000/health>

## 前端

新开终端：

~~~powershell
cd frontend
npm install
npm run dev
~~~

- 开发页面：<http://localhost:5173>

## 停止服务

在运行服务的终端按 Ctrl+C。不要在未确认目标进程的情况下使用强制终止命令。

## 端口检查

~~~powershell
Get-NetTCPConnection -LocalPort 8000,5173 -ErrorAction SilentlyContinue
~~~

## 常见原因

- 后端失败：确认已激活 rag-local，并从项目根目录启动。
- 前端失败：确认 frontend/package.json 存在，并先运行 npm install。
- API 请求失败：确认前端使用的 API 地址指向后端 8000 端口。
- Neo4j 不可用：先查看后端健康响应；系统是否降级取决于当前配置和请求路径。

容器化启动请看[Docker 部署](../operations/docker.md)，完整安装请看[环境搭建](setup.md)。
