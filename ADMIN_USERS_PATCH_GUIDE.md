# Admin Users Security Patch Deployment Guide

**Version**: v0.3.1.2  
**Release Date**: 2026-04-28  
**Severity**: CRITICAL - Deploy Immediately

---

## ⚠️ Pre-Deployment Checklist

Before deploying this security patch, ensure:

- [ ] Backup current database (`data/app.db`)
- [ ] Backup audit logs (`data/audit.log`)
- [ ] Review current admin user list
- [ ] Notify users of upcoming password policy changes
- [ ] Schedule maintenance window (recommended: 15 minutes)
- [ ] Prepare rollback plan

---

## 🚀 Deployment Steps

### Step 1: Backup Current System

```bash
# Backup database
cp data/app.db data/app.db.backup.$(date +%Y%m%d_%H%M%S)

# Backup audit logs
cp data/audit.log data/audit.log.backup.$(date +%Y%m%d_%H%M%S)

# Backup configuration
cp .env .env.backup.$(date +%Y%m%d_%H%M%S)
```

### Step 2: Pull Security Patches

```bash
# Fetch latest changes
git fetch origin main

# Review changes
git log --oneline HEAD..origin/main

# Expected commits:
# 2065fc2 security: add admin security modules for v0.3.1.2
# eb80b44 security: comprehensive security hardening for v0.3.1.2

# Pull changes
git pull origin main
```

### Step 3: Review Configuration Changes

**Cookie Security** (Production with HTTPS):
```bash
# .env - Keep defaults (secure)
AUTH_COOKIE_SECURE=true
AUTH_COOKIE_SAMESITE=strict
```

**Cookie Security** (Development without HTTPS):
```bash
# .env - Override for local development
AUTH_COOKIE_SECURE=false
AUTH_COOKIE_SAMESITE=lax
```

### Step 4: Install Dependencies (if needed)

```bash
# Activate virtual environment
source .venv/bin/activate  # Linux/Mac
# OR
.venv\Scripts\activate  # Windows

# Install any new dependencies
pip install -e .
```

### Step 5: Run Pre-Deployment Tests

```bash
# Run security tests
pytest tests/test_admin_security.py -v
pytest tests/test_security_fixes_v0_3_1_2.py -v

# Expected: 19/20 tests passing (95%)

# Run full test suite
pytest -q

# Expected: All tests passing
```

### Step 6: Stop Application

```bash
# If using systemd
sudo systemctl stop multi-agent-rag

# If using Docker
docker-compose down

# If running manually
# Press Ctrl+C to stop uvicorn
```

### Step 7: Deploy Security Patches

```bash
# No database migrations needed for this release
# Security fixes are code-only changes

# Verify file changes
git diff HEAD~2 --stat

# Expected files changed:
# - app/services/auth/validation.py
# - app/core/config.py
# - app/api/routes/auth.py
# - app/api/routes/admin_users.py
# - app/api/utils/auth_dependencies.py
# - app/api/utils/admin_helpers.py
# - app/services/admin_security.py (NEW)
# - app/services/admin_token_tracker.py (NEW)
# - app/services/admin_rate_limit.py (NEW)
```

### Step 8: Start Application

```bash
# If using systemd
sudo systemctl start multi-agent-rag
sudo systemctl status multi-agent-rag

# If using Docker
docker-compose up -d
docker-compose logs -f

# If running manually
uvicorn app.api.main:app --host 127.0.0.1 --port 8000 --reload
```

### Step 9: Verify Deployment

```bash
# Check health endpoint
curl http://127.0.0.1:8000/health

# Expected: {"status": "healthy"}

# Check application logs
tail -f logs/app.log

# Look for startup messages without errors
```

### Step 10: Post-Deployment Verification

**Test 1: Password Policy Enforcement**
```bash
# Try creating user with weak password (should fail)
curl -X POST http://127.0.0.1:8000/auth/register \
  -H "Content-Type: application/json" \
  -d '{"username":"testuser","password":"Pass123"}'

# Expected: 400 Bad Request
# "password must be at least 12 characters"
```

**Test 2: Login Error Message Unification**
```bash
# Try login with non-existent user
curl -X POST http://127.0.0.1:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"nonexistent","password":"WrongPass123!"}'

# Expected: 401 Unauthorized
# {"detail": "invalid credentials"}
# (NOT "user not found")
```

**Test 3: Admin Self-Modification Prevention**
```bash
# Login as admin
ADMIN_TOKEN=$(curl -X POST http://127.0.0.1:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"AdminPass123!"}' \
  | jq -r '.token')

# Get admin user ID
ADMIN_ID=$(curl http://127.0.0.1:8000/auth/me \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  | jq -r '.user_id')

# Try to modify own role (should fail)
curl -X PUT http://127.0.0.1:8000/admin/users/$ADMIN_ID \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"role":"viewer"}'

# Expected: 403 Forbidden
# "cannot modify your own account"
```

**Test 4: User Status Enforcement**
```bash
# Disable a test user
curl -X PUT http://127.0.0.1:8000/admin/users/testuser123 \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"status":"disabled"}'

# Try to use disabled user's token (should fail)
curl http://127.0.0.1:8000/query \
  -H "Authorization: Bearer $DISABLED_USER_TOKEN"

# Expected: 403 Forbidden
# "account is not active"
```

**Test 5: Rate Limiting**
```bash
# Try creating multiple admins rapidly (should be rate limited)
for i in {1..3}; do
  curl -X POST http://127.0.0.1:8000/admin/users \
    -H "Authorization: Bearer $ADMIN_TOKEN" \
    -H "Content-Type: application/json" \
    -d '{"username":"admin'$i'","password":"AdminPass123!","role":"admin","approval_token":"'$APPROVAL_TOKEN'"}'
  echo ""
done

# Expected: First request succeeds, subsequent requests return 429
# "rate limit exceeded"
```

---

## 🔍 Monitoring Post-Deployment

### Check Audit Logs

```bash
# Monitor audit log for security events
tail -f data/audit.log | grep -E "auth\.|admin\."

# Look for:
# - "auth.permission_denied" - Permission checks working
# - "auth.access_denied" - Inactive users blocked
# - "admin.user.self_modification_blocked" - Self-modification prevented
```

### Monitor Application Logs

```bash
# Check for errors or warnings
tail -f logs/app.log | grep -E "ERROR|WARNING"

# Should see no security-related errors
```

### Check System Metrics

```bash
# Check /metrics endpoint
curl http://127.0.0.1:8000/metrics | grep -E "auth_|admin_"

# Monitor for unusual patterns
```

---

## 🔄 Rollback Procedure

If critical issues arise:

### Quick Rollback (Revert Commits)

```bash
# Stop application
sudo systemctl stop multi-agent-rag

# Revert security patches
git revert 2065fc2 eb80b44 --no-edit

# Restart application
sudo systemctl start multi-agent-rag

# Verify rollback
curl http://127.0.0.1:8000/health
```

### Full Rollback (Restore Backup)

```bash
# Stop application
sudo systemctl stop multi-agent-rag

# Restore database
cp data/app.db.backup.YYYYMMDD_HHMMSS data/app.db

# Restore configuration
cp .env.backup.YYYYMMDD_HHMMSS .env

# Checkout previous version
git checkout HEAD~2

# Restart application
sudo systemctl start multi-agent-rag
```

---

## 📋 Post-Deployment Tasks

### Immediate (Within 24 hours)

- [ ] Monitor audit logs for unusual activity
- [ ] Verify all admin operations working correctly
- [ ] Check user login success rate
- [ ] Review error logs for unexpected issues

### Short-term (Within 1 week)

- [ ] Force password reset for users with weak passwords
- [ ] Review and update user documentation
- [ ] Notify users of new password requirements
- [ ] Update API documentation if needed

### Medium-term (Within 1 month)

- [ ] Conduct security audit of other endpoints
- [ ] Implement 2FA for admin accounts
- [ ] Review and update security policies
- [ ] Schedule regular security audits

---

## ⚠️ Breaking Changes

### Password Policy Changes

**Impact**: Users with passwords shorter than 12 characters or without special characters will need to reset their passwords.

**Action Required**:
1. Identify affected users:
   ```sql
   -- This is informational only - password hashes cannot be validated
   -- Users will discover weak passwords on next login attempt
   ```

2. Notify users via email/announcement:
   ```
   Subject: Password Policy Update - Action Required

   We've strengthened our password requirements for enhanced security.
   New requirements:
   - Minimum 12 characters (was 8)
   - Must include special characters (!@#$%^&*...)
   - Maximum 128 characters

   If your current password doesn't meet these requirements, you'll be
   prompted to reset it on your next login.
   ```

### Cookie Security Changes

**Impact**: Development environments without HTTPS may need configuration updates.

**Action Required** (Development only):
```bash
# Add to .env for local development
AUTH_COOKIE_SECURE=false
AUTH_COOKIE_SAMESITE=lax
```

**Production**: Keep defaults (secure=true, samesite=strict)

---

## 🆘 Troubleshooting

### Issue: Users Cannot Login After Deployment

**Symptom**: All login attempts fail with "invalid credentials"

**Possible Causes**:
1. Cookie security settings incompatible with HTTP
2. Database connection issues
3. Session token validation failing

**Solution**:
```bash
# Check if running on HTTP without HTTPS
# If yes, update .env:
AUTH_COOKIE_SECURE=false

# Restart application
sudo systemctl restart multi-agent-rag
```

### Issue: Admin Operations Return 403 Forbidden

**Symptom**: Admin users cannot perform admin operations

**Possible Causes**:
1. Admin trying to modify their own account
2. Admin account status is not "active"
3. RBAC permissions not configured correctly

**Solution**:
```bash
# Check admin user status
sqlite3 data/app.db "SELECT user_id, username, role, status FROM users WHERE role='admin';"

# Ensure status is 'active'
# If not, update manually:
sqlite3 data/app.db "UPDATE users SET status='active' WHERE username='admin';"
```

### Issue: Rate Limiting Too Aggressive

**Symptom**: Legitimate admin operations blocked by rate limiting

**Solution**:
```python
# Adjust rate limits in app/services/admin_rate_limit.py
ADMIN_RATE_LIMITS = {
    "admin_create": (2, 3600),  # Increase from 1 to 2 per hour
    "token_reset": (5, 3600),   # Increase from 3 to 5 per hour
    "password_reset": (10, 3600),  # Increase from 5 to 10 per hour
}
```

### Issue: Approval Token Marked as Used Incorrectly

**Symptom**: Valid approval token rejected as "already used"

**Solution**:
```bash
# Check token tracker
cat data/admin_token_usage.json

# If token incorrectly marked, remove entry:
# Edit data/admin_token_usage.json and remove the token entry

# Or clear all token usage (use with caution):
echo '{}' > data/admin_token_usage.json
```

---

## 📞 Support

For issues or questions:
- **GitHub Issues**: https://github.com/pocheang/multi_agent_rag_local/issues
- **Security Issues**: Create private security advisory on GitHub
- **Documentation**: See `SECURITY_FIXES_v0.3.1.2.md` for detailed information

---

## ✅ Deployment Checklist

- [ ] Pre-deployment backup completed
- [ ] Security patches pulled from git
- [ ] Configuration reviewed and updated
- [ ] Pre-deployment tests passed
- [ ] Application stopped
- [ ] Security patches deployed
- [ ] Application started
- [ ] Health check passed
- [ ] Post-deployment verification completed
- [ ] Audit logs monitored
- [ ] Users notified of password policy changes
- [ ] Documentation updated

---

**Deployment Status**: Ready for Production  
**Estimated Downtime**: 5-10 minutes  
**Risk Level**: Low (with proper testing)  
**Rollback Time**: < 5 minutes

**Version**: v0.3.1.2  
**Release Date**: 2026-04-28
