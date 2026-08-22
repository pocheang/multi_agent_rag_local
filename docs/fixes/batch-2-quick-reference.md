# 第二批修复 - 快速参考

**版本**: v0.6.2.3  
**状态**: ✅ 已完成  

---

## 🎯 修复了什么？

| 问题 | 之前 | 现在 |
|------|------|------|
| **文件上传** | ❌ "file too large" | ✅ "30MB超过20MB限制，建议压缩" |
| **OAuth错误** | ❌ "oauth_failed" | ✅ "登录超时，请检查网络后重试" |
| **登录限流** | ❌ "retry later" | ✅ "请在4分5秒后重试" + 倒计时 |

---

## ⚡ 5分钟快速测试

```bash
TOKEN="your-test-token"

# 1. 测试文件上传过大
dd if=/dev/zero of=test_30mb.pdf bs=1M count=30
curl -X POST http://localhost:8000/api/documents/upload \
  -H "Authorization: Bearer $TOKEN" \
  -F "files=@test_30mb.pdf"
# 预期: HTTP 413，包含 file_size_mb 和 max_file_size_mb

# 2. 测试OAuth错误（手动测试）
# 访问: http://localhost:8000/api/auth/google/callback?state=invalid
# 预期: 跳转到 /login?error=invalid_state&hint=csrf_expired&message=...

# 3. 测试登录限流
for i in {1..6}; do
  curl -X POST http://localhost:8000/api/auth/login \
    -H "Content-Type: application/json" \
    -d '{"username":"test","password":"wrong"}'
done
# 预期第6次: HTTP 429，包含 retry_after_seconds
```

---

## 📁 修改的文件

```
✏️ 修改（4个文件）:
  app/services/documents/dedup.py           # 增强异常类
  app/api/routes/public/documents.py        # 文件上传错误
  app/api/routes/public/auth.py             # OAuth和限流错误
  app/services/security/rate_limiter.py     # 限流详情

代码统计: +117行, -9行
```

---

## 🔑 关键API变更

### 文件上传错误响应
```json
HTTP 413
{
  "detail": {
    "error": "upload_too_large",
    "file_size_mb": 30.0,
    "max_file_size_mb": 20.0,
    "filename": "report.pdf",
    "suggestion": "单个文件不能超过 20.0MB"
  }
}
```

### OAuth错误URL参数
```
/login?error=invalid_state
      &hint=csrf_expired
      &message=登录会话已过期，请重新尝试
```

### 登录限流响应
```json
HTTP 429
Headers: Retry-After: 245

{
  "detail": {
    "error": "rate_limited",
    "message": "登录尝试次数过多，请在4分5秒后重试",
    "retry_after_seconds": 245,
    "attempts_used": 5,
    "max_attempts": 5,
    "suggestion": "如果忘记密码，请使用'忘记密码'功能重置"
  }
}
```

---

## 💡 前端集成要点

### 文件上传错误
```typescript
if (error.status === 413) {
  const { file_size_mb, max_file_size_mb, suggestion } = error.data.detail;
  showError(`${file_size_mb}MB 超过 ${max_file_size_mb}MB，${suggestion}`);
}
```

### OAuth错误
```typescript
const params = new URLSearchParams(location.search);
const message = decodeURIComponent(params.get('message') || '');
showError(message);
```

### 限流倒计时
```typescript
if (error.status === 429) {
  const { retry_after_seconds } = error.data.detail;
  startCountdown(retry_after_seconds);
}
```

---

## 🐛 常见问题排查

### 问题: 上传错误仍然不友好
```bash
# 检查异常类是否更新
grep -A 10 "class UploadPayloadTooLargeError" app/services/documents/dedup.py
# 应该看到 __init__ 方法带参数

# 检查错误处理
grep -A 20 "except UploadPayloadTooLargeError" app/api/routes/public/documents.py
# 应该看到 error_details 字典
```

### 问题: OAuth错误参数缺失
```bash
# 检查所有OAuth错误返回
grep "RedirectResponse.*error=" app/api/routes/public/auth.py | grep -v "&hint="
# 应该没有输出（所有都应该包含hint和message）
```

### 问题: 限流信息不完整
```bash
# 测试 get_limit_info 方法
python -c "
from app.services.security.rate_limiter import SlidingWindowLimiter
limiter = SlidingWindowLimiter(max_attempts=5, window_seconds=300)
print(limiter.get_limit_info('test_key'))
"
# 应该返回字典，包含所有字段
```

---

## 📊 监控指标

```bash
# 访问指标端点
curl http://localhost:8000/metrics

# 查找相关指标（如果已添加）:
upload_errors_too_large_total
oauth_errors_by_type{type="invalid_state"}
login_rate_limited_total
```

---

## 🔄 快速回滚

```bash
# Git回滚
git checkout HEAD~1 -- app/services/documents/dedup.py
git checkout HEAD~1 -- app/api/routes/public/documents.py
git checkout HEAD~1 -- app/api/routes/public/auth.py
git checkout HEAD~1 -- app/services/security/rate_limiter.py

# 重启服务
sudo systemctl restart querymind-api
```

---

## ✅ 验证清单

部署后验证:
- [ ] 上传过大文件，错误消息包含MB数值
- [ ] OAuth错误跳转包含hint和message参数
- [ ] 登录限流返回429，包含retry_after_seconds
- [ ] HTTP响应头包含Retry-After
- [ ] 所有原有功能正常

---

## 📈 成功指标

**目标**:
- 上传错误相关工单 ↓ 40%
- OAuth错误相关工单 ↓ 60%
- 限流相关咨询 ↓ 70%
- 用户自助解决率 ↑ 60%

**监控**:
```bash
# 错误提示清晰度（需要用户反馈数据）
# 工单数量对比（部署前后7天）
# 用户重试成功率
```

---

**完整文档**: [batch-2-error-feedback-improvements.md](./batch-2-error-feedback-improvements.md)

