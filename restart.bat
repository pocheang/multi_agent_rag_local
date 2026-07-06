@echo off
echo ========================================
echo  完整项目重启脚本
echo ========================================
echo.

echo [1/5] 停止现有服务...
taskkill /F /IM python.exe /FI "WINDOWTITLE eq *uvicorn*" 2>nul
taskkill /F /IM node.exe /FI "WINDOWTITLE eq *vite*" 2>nul
timeout /t 2 >nul

echo [2/5] 启动后端服务器...
cd /d c:\Users\pocheang\Desktop\llm\multi_agent_rag_local_v4
start "Backend - FastAPI" cmd /k "uvicorn app.api.main:app --host 0.0.0.0 --port 8000 --reload"
timeout /t 5 >nul

echo [3/5] 启动前端服务器...
cd /d c:\Users\pocheang\Desktop\llm\multi_agent_rag_local_v4\frontend
start "Frontend - Vite" cmd /k "npm run dev"
timeout /t 5 >nul

echo [4/5] 验证服务状态...
curl -s http://localhost:8000/api/v1/admin/web-activity/health >nul 2>&1
if %errorlevel% equ 0 (
    echo   后端: 运行中 [OK]
) else (
    echo   后端: 启动中... [WAIT]
)

curl -s -I http://localhost:5173/ >nul 2>&1
if %errorlevel% equ 0 (
    echo   前端: 运行中 [OK]
) else (
    echo   前端: 启动中... [WAIT]
)

echo.
echo [5/5] 打开浏览器...
timeout /t 3 >nul
start http://localhost:5173

echo.
echo ========================================
echo  重启完成！
echo ========================================
echo.
echo  前端: http://localhost:5173
echo  后端: http://localhost:8000
echo  文档: http://localhost:8000/docs
echo.
echo  登录: admin / admin123
echo  进入: Admin -^> Web Activity
echo.
echo ========================================
echo.
pause
