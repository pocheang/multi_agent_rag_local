# 安全政策

## 🔒 支持的版本

| 版本 | 支持状态 | 安全更新 |
| --- | --- | --- |
| 0.6.x | ✅ 支持 | 统一认证系统，强制加密密钥 |
| 0.5.x | ⚠️ 有限支持 | 建议升级到0.6.x |
| < 0.5 | ❌ 不支持 | 不再维护 |

## 🚨 报告安全漏洞

发现安全问题？请通过以下方式负责任地披露：

1. **私密报告**: security@yourorg.com
2. **GitHub Security Advisory**: 使用私密安全报告功能
3. **不要公开披露**: 在修复之前请勿公开漏洞细节

**响应承诺**: 我们会在48小时内响应您的报告。

---

## 🛡️ 最新安全更新 (v0.6.0+, 2026-07-01)

### ✅ 已修复的安全问题

1. **统一认证系统**
   - 移除了存在硬编码密钥的旧认证模块 (`app.api.auth`)
   - 所有端点现在使用主认证系统
   - 消除了认证不一致漏洞

2. **强制加密密钥**
   - `API_SETTINGS_ENCRYPTION_KEY` 现在是必需的环境变量
   - 禁止自动生成弱密钥
   - 使用 AES-256 加密用户API设置

3. **安全配置文档化**
   - 创建 `.env.security` 配置模板
   - 提供详细的生产环境安全检查清单

---

## 🔐 安全功能

### 认证与授权
- **JWT Bearer Token**: 安全随机令牌，可配置过期时间
- **密码加密**: bcrypt哈希算法
- **RBAC**: 基于角色的访问控制 (admin/manager/viewer)
- **会话管理**: 自动过期和清理
- **审计日志**: 所有安全操作记录

### 数据保护
- **API密钥加密**: AES-256加密存储敏感配置
- **CSRF保护**: Cookie认证强制CSRF验证
- **Cookie安全**: 支持Secure和SameSite配置

---

## 📋 生产环境安全检查清单

### 必须配置项 ✅

- [x] **API_SETTINGS_ENCRYPTION_KEY** - 已配置
- [ ] **APP_ENV=production** - 设置为生产模式
- [ ] **AUTH_COOKIE_SECURE=true** - 启用HTTPS-only cookies
- [ ] **AUTH_COOKIE_SAMESITE=strict** - 防止CSRF攻击
- [ ] **HTTPS/SSL** - 配置SSL证书
- [ ] **更改默认密码** - 修改所有默认凭证
- [ ] **防火墙** - 配置网络访问控制
- [ ] **自动备份** - 设置数据库备份

### 推荐配置项

- [ ] **AUTH_TOKEN_TTL_HOURS=8** - 缩短会话超时
- [ ] **Nginx反向代理** - 配置安全头部
- [ ] **IP白名单** - 限制访问来源
- [ ] **日志监控** - 监控异常活动
- [ ] **定期安全审计** - 每季度检查

---

## 🚀 快速安全配置

### 1. 查看安全配置模板

```bash
cat .env.security
```

该文件包含：
- 生产环境完整配置示例
- 开发/生产环境对比
- 密钥生成命令
- Nginx配置示例

### 2. 生成安全密钥

```bash
# 生成API设置加密密钥
python -c "import secrets; print(secrets.token_urlsafe(48))"

# 生成管理员创建令牌
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

### 3. 启用生产安全设置

编辑 `.env` 文件：

```env
APP_ENV=production
AUTH_COOKIE_SECURE=true
AUTH_COOKIE_SAMESITE=strict
AUTH_TOKEN_TTL_HOURS=8
API_SETTINGS_ENCRYPTION_KEY=<你生成的密钥>
```

---

## 🛡️ 安全最佳实践

### 开发环境
- ✅ 使用 `APP_ENV=dev`
- ✅ Cookie设置可以宽松 (`SECURE=false`, `SAMESITE=lax`)
- ✅ 使用测试数据
- ✅ 不要将 `.env` 提交到Git

### 生产环境
- ✅ 始终使用 `APP_ENV=production`
- ✅ 启用HTTPS和严格的Cookie设置
- ✅ 使用强密钥和短会话超时
- ✅ 配置防火墙和访问控制
- ✅ 启用日志监控和告警
- ✅ 定期备份数据库
- ✅ 定期更新依赖包
- ✅ 实施密钥轮换策略

### 密钥管理
- ❌ 不要硬编码密钥
- ❌ 不要将密钥提交到版本控制
- ✅ 使用环境变量
- ✅ 使用密钥管理服务 (如 AWS Secrets Manager)
- ✅ 定期轮换密钥（每3-6个月）

---

## 🔍 安全审计

### 审计日志位置
```bash
# SQLite数据库
sqlite3 data/app.db "SELECT * FROM auth_audit ORDER BY created_at DESC LIMIT 50;"
```

### 检查会话
```bash
# 查看活动会话
sqlite3 data/app.db "SELECT user_id, username, issued_at, expires_at FROM auth_sessions;"
```

### 监控建议
- 监控登录失败率
- 告警异常访问模式
- 记录所有管理员操作
- 定期审查审计日志

---

## 📚 更多资源

- 📄 [.env.security](/.env.security) - 完整安全配置模板
- 📄 [部署指南](/DEPLOYMENT.md) - 生产部署说明
- 📄 [配置参考](/docs/guides/development/CONFIGURATION_REFERENCE.md)

---

## 🔒 当前安全评级

| 类别 | 开发环境 | 生产环境 |
|------|----------|----------|
| 认证系统 | ✅ 安全 | ✅ 安全 |
| 密码存储 | ✅ 安全 | ✅ 安全 |
| API密钥加密 | ✅ 安全 | ✅ 安全 |
| 权限控制 | ✅ 安全 | ✅ 安全 |
| Cookie安全 | ⚠️ 宽松 | ⚠️ 需配置 |
| 会话超时 | ⚠️ 24小时 | ⚠️ 建议8小时 |
| HTTPS | ❌ 未启用 | ⚠️ 需配置 |

**总体**: 开发环境✅可用 | 生产环境⚠️需完成配置清单

---

感谢您帮助保持项目安全！

最后更新：2026-07-01
