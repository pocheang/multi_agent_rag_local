# 第一批修复 - 实施步骤指南

**版本**: 1.0  
**最后更新**: 2026-08-21  
**预计实施时间**: 2-3小时  

---

## 📋 实施前检查清单

### 环境准备
- [ ] 备份生产数据库
- [ ] 备份当前代码版本（Git tag）
- [ ] 确认测试环境可用
- [ ] 通知团队即将发布
- [ ] 准备回滚脚本

### 依赖检查
- [ ] Python 3.11+ 已安装
- [ ] 所有依赖包版本兼容
- [ ] 数据库连接正常
- [ ] Redis连接正常（如使用）
- [ ] 前端构建工具可用

---

## 🚀 实施步骤

### 阶段1: 代码部署（30分钟）

#### 步骤1: 拉取代码
```bash
# 切换到项目目录
cd /path/to/multi_agent_rag_local_v4

# 确认当前分支
git branch
# 应该在 main 或 develop 分支

# 拉取最新代码
git pull origin main

# 查看本次修改的文件
git log --oneline --name-only -5
```

#### 步骤2: 验证修改内容
```bash
# 确认修改的文件存在且正确
ls -la app/api/transport/errors.py
ls -la app/api/schemas/http.py
ls -la app/api/query/request.py
ls -la app/api/deps/sessions.py
ls -la app/api/routes/public/auth.py
ls -la app/api/routes/public/query_status.py  # 新文件

# 检查文件没有语法错误
python -m py_compile app/api/transport/errors.py
python -m py_compile app/api/schemas/http.py
python -m py_compile app/api/query/request.py
python -m py_compile app/api/deps/sessions.py
python -m py_compile app/api/routes/public/auth.py
python -m py_compile app/api/routes/public/query_status.py
```

#### 步骤3: 激活环境并安装依赖
```bash
# 激活conda环境
conda activate rag-local

# 验证Python版本
python --version  # 应该是 3.11+

# 安装/更新依赖（如有新增）
pip install -r requirements.txt

# 验证关键模块可导入
python -c "from app.api.transport.errors import accepted; print('OK')"
python -c "from app.api.schemas.http import QueryResponse; print('OK')"
```

#### 步骤4: 注册新路由（如需要）
```bash
# 检查 query_status 路由是否需要手动注册
# 查看路由注册文件
cat app/api/application/router_registry.py | grep -A5 "query"
```

如果需要手动注册，编辑路由注册文件：
```python
# app/api/application/router_registry.py 或类似文件
from app.api.routes.public import query_status

# 在路由注册部分添加
app.include_router(query_status.router, prefix="/api")
```

---

### 阶段2: 测试验证（60分钟）

#### 步骤5: 单元测试
```bash
# 运行全部测试
pytest tests/ -v

# 如果有失败，只运行相关测试
pytest tests/api/test_query.py -v
pytest tests/api/test_sessions.py -v
pytest tests/api/test_auth.py -v

# 检查测试覆盖率
pytest --cov=app.api tests/api/ --cov-report=html
# 查看报告: htmlcov/index.html
```

#### 步骤6: 启动开发服务器
```bash
# 启动后端（开发模式）
uvicorn app.api.main:app --reload --port 8000

# 在另一个终端检查服务健康
curl http://localhost:8000/health
# 应返回: {"status": "ok", "service": "querymind-api", "version": "..."}

# 检查新端点是否注册
curl http://localhost:8000/docs
# 在 Swagger UI 中查找 /api/query/status/{request_id}
```

#### 步骤7: 手动功能测试

**测试A: 重复请求**
```bash
# 终端1: 发送慢查询
TOKEN="your-test-token"
curl -X POST http://localhost:8000/api/query \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"question": "详细解释量子计算的原理", "session_id": "test-session-1"}' &

# 终端2: 立即发送相同查询
sleep 0.5
curl -X POST http://localhost:8000/api/query \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"question": "详细解释量子计算的原理", "session_id": "test-session-1"}'

# 预期第二个请求返回 status="processing"
```

**测试B: Session自动创建**
```bash
# 使用不存在的session ID
curl -X POST http://localhost:8000/api/query \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "question": "测试自动创建session",
    "session_id": "auto-created-'$(date +%s)'"
  }'

# 预期: 成功返回结果，不返回404

# 验证session已创建
curl http://localhost:8000/api/sessions/auto-created-XXXXX \
  -H "Authorization: Bearer $TOKEN"
```

**测试C: 密码修改**
```bash
# 先登录获取token
LOGIN_RESPONSE=$(curl -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "testuser", "password": "OldPassword123!"}')

TOKEN=$(echo $LOGIN_RESPONSE | jq -r '.token')

# 修改密码
curl -X POST http://localhost:8000/api/auth/change-password \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "old_password": "OldPassword123!",
    "new_password": "NewPassword456!"
  }'

# 检查响应是否包含 token_rotated 字段
```

#### 步骤8: 检查日志
```bash
# 查看最近的日志
tail -f logs/app.log

# 应该看到类似的日志：
# [INFO] Auto-created session xxxx for user yyyy
# [INFO] Duplicate request detected, returning 202 Accepted
# [INFO] password_changed_token_rotated
```

---

### 阶段3: 前端集成（30分钟）

#### 步骤9: 更新前端代码

编辑 `frontend/src/services/api.ts` 或类似文件：

```typescript
// 1. 处理重复请求的 processing 状态
export async function submitQuery(question: string, sessionId?: string) {
  const response = await fetch('/api/query', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${getToken()}`
    },
    body: JSON.stringify({ question, session_id: sessionId })
  });

  const result = await response.json();

  // 新增：处理 processing 状态
  if (result.status === 'processing') {
    console.log('Query is processing, polling status...');
    return pollQueryStatus(result.request_id);
  }

  return result;
}

// 新增：轮询查询状态
async function pollQueryStatus(requestId: string, maxAttempts = 10): Promise<QueryResponse> {
  for (let i = 0; i < maxAttempts; i++) {
    await new Promise(resolve => setTimeout(resolve, 2000)); // 2秒间隔

    const response = await fetch(`/api/query/status/${requestId}`, {
      headers: { 'Authorization': `Bearer ${getToken()}` }
    });

    const result = await response.json();

    if (result.status === 'completed') {
      return result;
    }

    console.log(`Polling attempt ${i + 1}/${maxAttempts}, status: ${result.status}`);
  }

  throw new Error('查询超时，请刷新页面重试');
}

// 2. 密码修改处理
export async function changePassword(oldPassword: string, newPassword: string) {
  const response = await fetch('/api/auth/change-password', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${getToken()}`
    },
    body: JSON.stringify({
      old_password: oldPassword,
      new_password: newPassword
    })
  });

  const result = await response.json();

  // 新增：处理需要重新登录的情况
  if (result.requires_relogin) {
    // 显示成功消息
    showNotification({
      type: 'success',
      title: '密码修改成功',
      message: result.message,
      duration: 5000
    });

    // 清除本地token
    clearToken();

    // 3秒后跳转到登录页
    setTimeout(() => {
      window.location.href = '/login';
    }, 3000);

    return result;
  }

  // 正常流程
  showNotification({
    type: 'success',
    message: '密码修改成功'
  });

  return result;
}
```

#### 步骤10: 前端构建和测试
```bash
cd frontend

# 安装依赖（如有新增）
npm install

# 构建
npm run build

# 检查构建输出
ls -la dist/

# 启动前端开发服务器
npm run dev
# 访问 http://localhost:5173
```

#### 步骤11: 端到端测试

在浏览器中测试：
1. 打开 http://localhost:5173
2. 登录系统
3. 快速双击"发送"按钮，观察是否显示"正在处理中..."
4. 刷新页面后发送消息，检查是否正常工作
5. 修改密码，观察提示信息

---

### 阶段4: 生产部署（30分钟）

#### 步骤12: 创建部署分支
```bash
# 创建发布分支
git checkout -b release/batch-1-ux-fixes

# 打tag
git tag -a v0.6.2.2 -m "Batch 1 UX fixes: duplicate request, auto session, password change"
git push origin v0.6.2.2
```

#### 步骤13: 部署到生产

**选项A: Docker部署**
```bash
# 构建新镜像
docker build -t querymind-api:v0.6.2.2 .

# 停止旧容器
docker stop querymind-api

# 备份旧容器
docker commit querymind-api querymind-api:backup-$(date +%Y%m%d)

# 启动新容器
docker run -d \
  --name querymind-api \
  --restart unless-stopped \
  -p 8000:8000 \
  -v /data/querymind:/app/data \
  -e APP_ENV=production \
  --env-file .runtime/production.env \
  querymind-api:v0.6.2.2

# 检查容器状态
docker ps | grep querymind
docker logs querymind-api --tail 50
```

**选项B: Systemd部署**
```bash
# 停止服务
sudo systemctl stop querymind-api

# 切换到生产目录
cd /opt/querymind

# 备份当前版本
sudo cp -r /opt/querymind /opt/querymind.backup.$(date +%Y%m%d)

# 拉取新代码
sudo -u querymind git fetch origin
sudo -u querymind git checkout v0.6.2.2

# 激活环境并重启
sudo -u querymind conda activate rag-local
sudo -u querymind pip install -r requirements.txt

# 启动服务
sudo systemctl start querymind-api

# 检查状态
sudo systemctl status querymind-api
journalctl -u querymind-api -f  # 实时日志
```

#### 步骤14: 健康检查
```bash
# 等待服务启动（约10-30秒）
sleep 30

# 检查健康端点
curl http://localhost:8000/health

# 检查就绪端点
curl http://localhost:8000/ready

# 检查新端点
curl http://localhost:8000/docs | grep "query/status"

# 如果有负载均衡器，逐步切换流量
# 例如 Nginx upstream 配置
```

#### 步骤15: 监控和告警
```bash
# 检查Prometheus指标
curl http://localhost:8000/metrics | grep query_duplicate

# 预期看到：
# query_duplicate_total 0
# query_duplicate_returned_processing 0

# 检查日志没有错误
tail -100 /var/log/querymind/app.log | grep ERROR
# 应该没有输出或只有无关错误

# 检查CPU和内存使用正常
top -p $(pgrep -f "uvicorn.*querymind")
```

---

### 阶段5: 灰度发布（可选，60分钟）

#### 步骤16: 配置灰度规则

如果使用Nginx作为负载均衡器：

```nginx
# /etc/nginx/conf.d/querymind.conf

upstream querymind_old {
    server 127.0.0.1:8000;  # 旧版本
}

upstream querymind_new {
    server 127.0.0.1:8001;  # 新版本
}

# 根据Cookie进行灰度
map $cookie_canary $backend {
    "true"  querymind_new;
    default querymind_old;
}

server {
    listen 80;
    server_name querymind.example.com;

    location /api/ {
        # 10%流量到新版本
        if ($request_id ~* "^[0-9a-f]") {
            proxy_pass http://querymind_new;
        }

        proxy_pass http://$backend;
    }
}
```

重载Nginx：
```bash
sudo nginx -t
sudo systemctl reload nginx
```

#### 步骤17: 观察灰度效果

```bash
# 监控两个版本的请求量
watch -n 5 'curl -s http://localhost:8000/metrics | grep http_requests_total'
watch -n 5 'curl -s http://localhost:8001/metrics | grep http_requests_total'

# 对比错误率
watch -n 5 'curl -s http://localhost:8000/metrics | grep http_requests_failed'
watch -n 5 'curl -s http://localhost:8001/metrics | grep http_requests_failed'

# 如果新版本表现良好，逐步增加流量
# 10% → 25% → 50% → 100%
```

---

## 🔍 验证清单

### 功能验证
- [ ] 重复请求返回processing状态（不是409）
- [ ] 状态轮询端点可访问
- [ ] Session自动创建功能正常
- [ ] 密码修改后正确处理token轮换
- [ ] 所有原有功能正常

### 性能验证
- [ ] 查询响应时间没有显著增加
- [ ] 内存使用没有异常增长
- [ ] CPU使用率正常
- [ ] 数据库连接池健康

### 监控验证
- [ ] Prometheus指标正确暴露
- [ ] 日志格式正确
- [ ] 告警规则生效
- [ ] Grafana仪表盘正常

---

## ⚠️ 回滚步骤

如果发现严重问题，立即回滚：

### 快速回滚（5分钟内）

**Docker环境**:
```bash
# 停止新容器
docker stop querymind-api
docker rm querymind-api

# 启动备份容器
docker run -d \
  --name querymind-api \
  --restart unless-stopped \
  -p 8000:8000 \
  -v /data/querymind:/app/data \
  -e APP_ENV=production \
  --env-file .runtime/production.env \
  querymind-api:backup-YYYYMMDD

# 验证
curl http://localhost:8000/health
```

**Systemd环境**:
```bash
# 停止服务
sudo systemctl stop querymind-api

# 恢复旧代码
cd /opt/querymind
sudo -u querymind git checkout v0.6.2.1  # 上一个版本

# 重启服务
sudo systemctl start querymind-api

# 验证
curl http://localhost:8000/health
```

### 完全回滚（15分钟）

```bash
# 1. 恢复代码
git checkout v0.6.2.1

# 2. 恢复数据库（如有schema变更）
# 本次修改没有数据库变更，跳过

# 3. 重启所有服务
sudo systemctl restart querymind-api
sudo systemctl restart nginx

# 4. 清理失败的部署
docker rmi querymind-api:v0.6.2.2  # 如使用Docker

# 5. 通知团队
echo "已回滚到 v0.6.2.1" | mail -s "Rollback Alert" team@example.com
```

---

## 📊 发布后监控

### 第一小时
- [ ] 每5分钟检查错误日志
- [ ] 监控响应时间
- [ ] 查看用户反馈渠道

### 第一天
- [ ] 每小时检查关键指标
- [ ] 收集用户反馈
- [ ] 统计新功能使用率

### 第一周
- [ ] 每天查看监控报告
- [ ] 分析 A/B 测试结果（如有）
- [ ] 总结问题和改进点

---

## 📝 发布记录

**发布人员**: ________________  
**发布时间**: ________________  
**环境**: □ 测试 □ 预发布 □ 生产  
**发布结果**: □ 成功 □ 失败 □ 部分成功  
**回滚**: □ 是 □ 否  
**备注**: ____________________________________

---

## 🎉 发布成功后

1. **更新文档**: 在 CHANGELOG.md 中记录本次变更
2. **通知团队**: 发送发布邮件，包含变更内容和注意事项
3. **用户通知**: 如有必要，在系统中发布公告
4. **关闭工单**: 关闭相关的 Issue 和 Bug 报告
5. **庆祝**: 给团队买咖啡 ☕️

