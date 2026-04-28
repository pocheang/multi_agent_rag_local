# Security Fixes Installation Guide

**最后更新**: 2026-04-28


**Version**: v0.3.1.2  
**Date**: 2026-04-28  
**Priority**: 🔴 CRITICAL

## Overview

This guide explains how to apply the security fixes for admin_users.py vulnerabilities.

## Files Created

### New Security Modules
1. `app/services/admin_security.py` - Security validation functions
2. `app/services/admin_token_tracker.py` - Token usage tracking
3. `app/services/admin_rate_limit.py` - Rate limiting configuration
4. `app/api/utils/admin_helpers.py` - Helper functions (updated)
5. `app/api/routes/admin_users_secure.py` - Secure version of admin routes

### Updated Files
1. `app/api/utils/auth_dependencies.py` - Added user status check
2. `app/api/routes/admin_users.py` - Needs to be replaced

### Test Files
1. `tests/test_admin_security.py` - Security test suite

### Documentation
1. `docs/security/ADMIN_USERS_SECURITY_AUDIT.md` - Security audit report
2. `docs/security/ADMIN_USERS_FIX_PLAN.md` - Fix implementation plan
3. `docs/security/ADMIN_USERS_PATCH_GUIDE.md` - Detailed patch guide

## Installation Steps

### Step 1: Install Dependencies

```bash
# Install slowapi for rate limiting
pip install slowapi
```

### Step 2: Backup Current Files

```bash
# Backup is already created at:
# app/api/routes/admin_users.py.backup
```

### Step 3: Replace admin_users.py

**Option A: Use the secure version (Recommended)**

```bash
# Replace the old file with the secure version
cp app/api/routes/admin_users_secure.py app/api/routes/admin_users.py
```

**Option B: Manual patching**

Follow the detailed instructions in `docs/security/ADMIN_USERS_PATCH_GUIDE.md`

### Step 4: Update main.py

Add rate limiter to `app/api/main.py`:

```python
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from app.services.admin_rate_limit import get_limiter

# Add after app initialization
limiter = get_limiter()
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
```

### Step 5: Verify Installation

```bash
# Check Python syntax
python -m py_compile app/api/routes/admin_users.py
python -m py_compile app/services/admin_security.py
python -m py_compile app/services/admin_token_tracker.py
python -m py_compile app/services/admin_rate_limit.py

# Run security tests
pytest tests/test_admin_security.py -v
```

### Step 6: Update Configuration

Ensure your `.env` file has the approval token configured:

```bash
# Option 1: Use hashed token (recommended)
ADMIN_CREATE_APPROVAL_TOKEN_HASH=<sha256_hash_of_your_token>

# Option 2: Use plain token (less secure)
ADMIN_CREATE_APPROVAL_TOKEN=<your_secret_token>
```

## Verification Checklist

After installation, verify these security features:

- [ ] Admin cannot modify their own role
- [ ] Admin cannot disable themselves
- [ ] Admin cannot reset their own approval token
- [ ] Approval tokens can only be used once
- [ ] Disabled users cannot access any endpoints
- [ ] Rate limiting is active on admin endpoints
- [ ] Error messages don't leak configuration info
- [ ] All exceptions are properly audited
- [ ] Ticket ID format is validated
- [ ] All tests pass

## Testing

### Manual Testing

```bash
# 1. Test self-modification prevention
curl -X PATCH http://localhost:8000/admin/users/{your_admin_id}/role \
  -H "Authorization: Bearer {your_token}" \
  -H "Content-Type: application/json" \
  -d '{"role": "viewer"}'
# Expected: 403 Forbidden

# 2. Test token reuse prevention
# Use the same approval token twice
# Expected: Second attempt fails with 403

# 3. Test disabled user blocking
# Disable a user, then try to use their token
# Expected: 403 Forbidden with "account is not active"
```

### Automated Testing

```bash
# Run full security test suite
pytest tests/test_admin_security.py -v --cov=app/api/routes/admin_users

# Run specific test classes
pytest tests/test_admin_security.py::TestAdminSelfModification -v
pytest tests/test_admin_security.py::TestApprovalTokenSecurity -v
pytest tests/test_admin_security.py::TestUserStatusEnforcement -v
```

## Rollback Procedure

If you encounter issues:

```bash
# Restore the backup
cp app/api/routes/admin_users.py.backup app/api/routes/admin_users.py

# Restart the server
# The old (vulnerable) version will be active
```

## Security Impact

### Fixed Vulnerabilities

| Severity | Vulnerability | Status |
|----------|--------------|--------|
| 🔴 CRITICAL | Admin self-modification | ✅ Fixed |
| 🔴 CRITICAL | Approval token reuse | ✅ Fixed |
| 🔴 CRITICAL | Disabled admin bypass | ✅ Fixed |
| 🟠 HIGH | Information disclosure | ✅ Fixed |
| 🟠 HIGH | Audit log bypass | ✅ Fixed |
| 🟠 HIGH | Race conditions | ✅ Fixed |
| 🟡 MEDIUM | No rate limiting | ✅ Fixed |
| 🟡 MEDIUM | Weak validation | ✅ Fixed |
| 🟡 MEDIUM | Timing attacks | ✅ Fixed |

### Security Improvements

- ✅ Self-modification checks on all sensitive endpoints
- ✅ Single-use approval tokens with 24-hour expiry
- ✅ User status validation in authentication flow
- ✅ Rate limiting (1/hour admin creation, 3/hour token reset, 5/hour password reset)
- ✅ Enhanced input validation (ticket ID format, reason length)
- ✅ Unified error messages (no configuration leakage)
- ✅ Comprehensive exception handling with audit logging
- ✅ Timing-attack resistant token comparison

## Monitoring

After deployment, monitor these metrics:

```bash
# Check audit logs for blocked attempts
grep "blocked_self_modification" data/audit_logs/*.jsonl
grep "approval_failed" data/audit_logs/*.jsonl
grep "blocked_inactive_user" data/audit_logs/*.jsonl

# Check rate limit hits
grep "429" logs/access.log

# Check token reuse attempts
grep "already_used" logs/app.log
```

## Support

If you encounter issues:

1. Check logs: `tail -f logs/app.log`
2. Review audit logs: `cat data/audit_logs/latest.jsonl`
3. Run diagnostics: `pytest tests/test_admin_security.py -v`
4. Consult documentation: `docs/security/ADMIN_USERS_FIX_PLAN.md`

## Next Steps

1. Deploy to staging environment first
2. Run full security test suite
3. Monitor for 24 hours
4. Deploy to production
5. Conduct security audit
6. Update security documentation

## Important Notes

- ⚠️ This is a critical security update
- ⚠️ All admin users should be notified
- ⚠️ Existing approval tokens will need to be rotated
- ⚠️ Rate limits may affect legitimate admin operations
- ⚠️ Test thoroughly before production deployment

## Contact

For security concerns or questions:
- Review: `docs/security/ADMIN_USERS_SECURITY_AUDIT.md`
- Implementation: `docs/security/ADMIN_USERS_FIX_PLAN.md`
- Patches: `docs/security/ADMIN_USERS_PATCH_GUIDE.md`
