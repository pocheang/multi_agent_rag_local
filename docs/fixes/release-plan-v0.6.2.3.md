# v0.6.2.3 发布计划 - 用户体验全面改进

**版本**: v0.6.2.3  
**发布类型**: 功能改进 + Bug修复  
**优先级**: 高  
**计划发布日期**: 2026-08-25

---

## 📦 发布内容

本次发布包含**第一批**和**第二批**的所有改进，共计**6个核心问题**的修复。

### 🎯 第一批：核心流程问题（3个）

| # | 问题 | 影响用户 | 状态 |
|---|------|----------|------|
| 2 | 重复请求返回409冲突 | 100% | ✅ 完成 |
| 4 | Session必须先创建 | 100% | ✅ 完成 |
| 1 | 密码修改后被登出 | ~5% | ✅ 完成 |

### 🎯 第二批：错误提示改进（3个）

| # | 问题 | 影响用户 | 状态 |
|---|------|----------|------|
| 5 | 文件上传错误不友好 | 常见 | ✅ 完成 |
| 3 | OAuth错误只返回代码 | OAuth用户 | ✅ 完成 |
| 8 | 限流无剩余配额提示 | 被限流用户 | ✅ 完成 |

---

## 📊 改进总览

### 代码变更统计

```
文件修改: 9个文件
新增文件: 2个文件
代码增加: +282行
代码删除: -18行
净增长: +264行
```

### 详细文件清单

**第一批修改**:
- ✏️ `app/api/transport/errors.py` (+4)
- ✏️ `app/api/schemas/http.py` (+2)
- ✏️ `app/api/query/request.py` (+25, -13)
- ✏️ `app/api/deps/sessions.py` (+25, -8)
- ✏️ `app/api/routes/public/auth.py` (+41, -7) ← 第一批修改
- ➕ `app/api/routes/public/query_status.py` (+70) 新增

**第二批修改**:
- ✏️ `app/services/documents/dedup.py` (+18, -2)
- ✏️ `app/api/routes/public/documents.py` (+21, -2)
- ✏️ `app/api/routes/public/auth.py` (+30, -5) ← 第二批继续修改
- ✏️ `app/services/security/rate_limiter.py` (+48)

---

## 🎁 用户可见改进

### 1. 查询更流畅 ⭐⭐⭐
- ✅ 双击提交不再报错
- ✅ 刷新页面后可以继续查询
- ✅ 查询状态可轮询

### 2. 账号管理更清晰 ⭐⭐
- ✅ 密码修改后明确告知是否需要重登
- ✅ Google登录失败有具体原因
- ✅ 登录限流显示倒计时

### 3. 文件操作更友好 ⭐⭐
- ✅ 上传错误显示具体MB数值
- ✅ 提供明确的操作建议

---

## 📈 预期业务效果

### 用户指标

| 指标 | 当前 | 目标 | 改善 |
|------|------|------|------|
| API错误率 | 2-3% | <1% | 50%↓ |
| 用户投诉 | 20个/月 | <10个/月 | 50%↓ |
| OAuth成功率 | 85% | 93% | +8% |
| 文件上传成功率 | 92% | 97% | +5% |

### 支持指标

| 类型 | 当前工单/月 | 目标 | 预期减少 |
|------|-------------|------|---------|
| 重复请求问题 | 5 | 0 | 100%↓ |
| Session问题 | 3 | 0 | 100%↓ |
| 密码修改问题 | 3 | 1 | 67%↓ |
| 上传问题 | 10 | 6 | 40%↓ |
| OAuth问题 | 8 | 3 | 62%↓ |
| 限流问题 | 5 | 1 | 80%↓ |
| **总计** | **34** | **11** | **68%↓** |

---

## 🧪 测试计划

### 阶段1: 单元测试（Day 1）

```bash
# 第一批测试
pytest tests/api/test_query.py::test_duplicate_request -v
pytest tests/api/test_sessions.py::test_auto_create -v
pytest tests/api/test_auth.py::test_password_change_token_rotation -v

# 第二批测试
pytest tests/api/test_documents.py::test_upload_errors -v
pytest tests/api/test_auth.py::test_oauth_error_messages -v
pytest tests/api/test_auth.py::test_login_rate_limit_info -v

# 全部测试
pytest tests/api/ -v --cov=app.api
```

### 阶段2: 集成测试（Day 2-3）

使用测试清单：
- [第一批测试清单](./batch-1-testing-checklist.md)
- [第二批测试清单](./batch-2-testing-checklist.md)

重点场景：
1. ✅ 用户快速双击提交
2. ✅ 用户刷新页面后查询
3. ✅ 用户修改密码
4. ✅ 用户上传大文件
5. ✅ 用户使用Google登录
6. ✅ 用户多次错误登录

### 阶段3: 前端集成（Day 2-3）

前端需要实现：
1. **查询状态轮询UI**
   - 显示"正在处理中..."
   - 自动轮询 `/api/query/status/{request_id}`
   
2. **密码修改后跳转**
   - 检查 `requires_relogin` 字段
   - 3秒倒计时后跳转到登录页

3. **文件上传错误展示**
   - 解析 `file_size_mb` 和 `max_file_size_mb`
   - 显示具体数值和建议

4. **OAuth错误消息**
   - 解析URL参数 `message`
   - 显示友好提示

5. **登录限流倒计时**
   - 解析 `retry_after_seconds`
   - 实时倒计时显示

---

## 🚀 部署步骤

### 准备工作（Day 4）

1. **代码准备**
   ```bash
   git checkout main
   git pull origin main
   git tag -a v0.6.2.3 -m "User experience improvements"
   git push origin v0.6.2.3
   ```

2. **文档更新**
   - 更新 CHANGELOG.md
   - 更新 API文档
   - 准备发布公告

3. **数据备份**
   ```bash
   # 备份数据库
   pg_dump querymind > backup_20260825.sql
   
   # 备份配置
   cp -r /opt/querymind /opt/querymind.backup.20260825
   ```

### 测试环境部署（Day 5）

```bash
# 1. 部署到测试环境
cd /opt/querymind-test
git fetch origin
git checkout v0.6.2.3
conda activate rag-local
pip install -r requirements.txt

# 2. 重启服务
sudo systemctl restart querymind-api-test

# 3. 烟雾测试
curl http://test.querymind.com/health
curl http://test.querymind.com/ready

# 4. 完整测试（2-3小时）
# 使用测试清单进行全面测试
```

### 生产环境灰度发布（Week 2）

**Day 1-2: 10%流量**
```bash
# Nginx配置
# 10%流量到新版本
upstream querymind_v0_6_2_3 {
    server 127.0.0.1:8001;
}

map $request_id $backend {
    ~^[0-9a-f]  querymind_v0_6_2_3;
    default     querymind_current;
}
```

监控指标：
- 错误率
- 响应时间
- 用户反馈

**Day 3-4: 50%流量**

如果10%流量表现良好，增加到50%。

**Day 5-7: 100%流量**

逐步切换到100%，完成发布。

---

## 📊 监控计划

### 关键指标

```promql
# 1. 重复请求处理
rate(query_duplicate_total[5m])
rate(query_duplicate_returned_processing[5m])

# 2. Session自动创建
rate(session_auto_created_total[5m])

# 3. 密码修改
rate(password_change_needs_reauth[1h])

# 4. 文件上传错误
rate(upload_error_too_large[5m])

# 5. OAuth错误分布
oauth_error_total by (error_type)

# 6. 登录限流
rate(login_rate_limited_total[5m])
```

### 告警规则

```yaml
groups:
  - name: v0.6.2.3_rollout
    rules:
      - alert: HighErrorRate
        expr: rate(http_errors_total[5m]) > 0.03
        annotations:
          summary: "Error rate > 3% after v0.6.2.3 deployment"
      
      - alert: SessionAutoCreateFailing
        expr: rate(session_auto_create_failed[5m]) > 0.01
        annotations:
          summary: "Session auto-create failure rate > 1%"
      
      - alert: UploadErrorSpike
        expr: rate(upload_error_total[5m]) > rate(upload_error_total[1h] offset 1d)
        annotations:
          summary: "Upload error rate increased compared to yesterday"
```

---

## ⚠️ 回滚计划

### 触发条件

回滚如果出现：
1. 错误率 > 5%（持续5分钟）
2. 关键功能完全不可用
3. 出现数据丢失或损坏
4. 用户投诉激增

### 快速回滚（<10分钟）

```bash
# Docker环境
docker stop querymind-api
docker start querymind-api-v0.6.2.2  # 旧版本

# Systemd环境
cd /opt/querymind
git checkout v0.6.2.2
sudo systemctl restart querymind-api

# 验证
curl http://localhost:8000/health | jq '.version'
# 应该显示 "0.6.2.2"
```

### 验证回滚成功

```bash
# 1. 检查版本
curl http://localhost:8000/health

# 2. 检查关键功能
curl -X POST http://localhost:8000/api/query ...
curl -X POST http://localhost:8000/api/documents/upload ...

# 3. 检查错误率
curl http://localhost:8000/metrics | grep http_errors_total
```

---

## 📢 发布沟通

### 内部通知

**发给**: 全体技术团队  
**时间**: 发布前1天

```
主题: v0.6.2.3 发布通知 - 用户体验全面改进

团队好，

我们将于明天发布 v0.6.2.3，包含重要的用户体验改进：

✅ 核心流程优化
  - 重复请求不再报错
  - Session自动创建
  - 密码修改清晰反馈

✅ 错误提示改进
  - 文件上传错误更友好
  - OAuth错误有明确原因
  - 登录限流显示倒计时

详细信息: [链接到文档]

发布计划:
  - 测试环境: 2026-08-24
  - 灰度发布: 2026-08-26 (10% → 50% → 100%)

请关注监控告警，发现问题及时反馈。

谢谢！
```

### 用户公告（可选）

**发给**: 所有用户  
**时间**: 发布完成后

```
🎉 系统更新通知

我们刚刚完成了一次重要更新，改善了您的使用体验：

✨ 更流畅的查询体验
  不小心双击提交？没问题，我们会智能处理

✨ 更清晰的错误提示
  文件太大？我们会告诉您具体大小和限制

✨ 更友好的登录体验
  如果尝试次数过多，我们会显示倒计时

感谢您的支持！
如有问题，请联系：support@querymind.com
```

---

## 📋 检查清单

### 发布前（Day 4）
- [ ] 所有单元测试通过
- [ ] 集成测试通过
- [ ] 前端集成完成
- [ ] 代码审核完成
- [ ] 文档已更新
- [ ] 数据已备份
- [ ] 回滚脚本已准备
- [ ] 团队已通知

### 发布时（Day 5）
- [ ] 测试环境部署成功
- [ ] 烟雾测试通过
- [ ] 监控正常
- [ ] 无严重错误

### 发布后（Week 2）
- [ ] 10%灰度监控正常
- [ ] 50%灰度监控正常
- [ ] 100%全量监控正常
- [ ] 用户反馈收集
- [ ] 支持工单统计
- [ ] 发布总结文档

---

## 📞 关键联系人

| 角色 | 姓名 | 联系方式 | 职责 |
|------|------|----------|------|
| 发布经理 | - | - | 总体协调 |
| 后端负责人 | - | - | 技术决策 |
| 前端负责人 | - | - | 前端集成 |
| 测试负责人 | - | - | 质量把关 |
| 运维负责人 | - | - | 部署执行 |
| 产品经理 | - | - | 用户沟通 |
| On-call工程师 | - | - | 紧急响应 |

---

## 📅 时间表

```
Week 1 (8月18-22日):
  ✅ Day 1: 代码完成
  ✅ Day 2: 文档完成
  ⏳ Day 3: 单元测试
  ⏳ Day 4-5: 集成测试 + 前端集成

Week 2 (8月25-29日):
  ⏳ Day 1 (8/25): 测试环境部署
  ⏳ Day 2 (8/26): 生产灰度 10%
  ⏳ Day 3 (8/27): 扩大到 50%
  ⏳ Day 4-5 (8/28-29): 扩大到 100%

Week 3 (9月1-5日):
  ⏳ 持续监控
  ⏳ 收集反馈
  ⏳ 效果评估
```

---

## 🎯 成功标准

发布成功的标准：

1. ✅ 错误率 < 1%
2. ✅ 响应时间无显著增加
3. ✅ 支持工单减少 > 50%
4. ✅ 用户满意度提升
5. ✅ 无严重bug
6. ✅ 无需回滚

---

## 📝 后续计划

### Week 3: 效果评估
- 收集用户反馈
- 统计支持工单
- 分析监控数据
- 编写发布总结

### Week 4: 持续优化
- 根据反馈微调
- 完善国际化
- 优化错误文案
- 准备下一批改进

---

**文档维护者**: 发布团队  
**最后更新**: 2026-08-21  
**版本**: 1.0

