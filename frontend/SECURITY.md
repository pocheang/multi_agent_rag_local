# Frontend Security Documentation

## 🔒 Security Measures Implemented

### 1. Authentication & Session Management

#### Token Management
- **Bearer Token Authentication**: JWT tokens stored in localStorage with proper get/set functions
- **Token Injection**: Automatically added to all authenticated requests via `Authorization` header
- **Token Lifecycle**: Properly cleared on logout

#### CSRF Protection
- **CSRF Tokens**: Generated using `crypto.getRandomValues()` for cryptographic randomness
- **Storage**: Stored in `sessionStorage` (expires with browser tab)
- **Validation**: Automatically added to all state-changing requests (POST/PUT/PATCH/DELETE)
- **Token Refresh**: New CSRF token generated on each login
- **Implementation**: See `frontend/src/lib/csrf.ts`

**Backend Requirements**:
```python
# Backend must validate X-CSRF-Token header
@app.middleware("http")
async def validate_csrf(request: Request, call_next):
    if request.method in ["POST", "PUT", "PATCH", "DELETE"]:
        csrf_token = request.headers.get("X-CSRF-Token")
        session_csrf = request.session.get("csrf_token")
        if not csrf_token or csrf_token != session_csrf:
            return JSONResponse({"detail": "CSRF validation failed"}, status_code=403)
    return await call_next(request)
```

### 2. Data Protection

#### Secure Storage
- **Obfuscated Storage**: Sensitive data (username) encrypted using XOR cipher before localStorage
- **Implementation**: `frontend/src/lib/secureStorage.ts`
- **Note**: This is obfuscation, not cryptographic encryption. For true security, store sensitive data server-side only.

#### What's Stored:
- ✅ `auth_token`: JWT token (localStorage)
- ✅ `csrf_token`: CSRF token (sessionStorage - expires with tab)
- ✅ `sec_remembered_username`: Obfuscated username (localStorage)
- ✅ `language`: User preference (localStorage - public)
- ✅ `chatSectionsHidden`: UI state (localStorage - public)

### 3. XSS Protection

#### Input Sanitization
- **React**: Automatic escaping of all text content
- **Markdown Rendering**: Using `react-markdown` with `remark-gfm` (safe by default)
- **No `dangerouslySetInnerHTML`**: Verified zero usage in codebase

#### Output Encoding
- All user input is properly escaped before rendering
- Code blocks use text nodes, not HTML injection

### 4. Open Redirect Prevention

#### OAuth Callback Validation
- **Return URL Validation**: Checks that redirect URLs are same-origin
- **Whitelist Approach**: Only allows URLs matching `window.location.origin`
- **Implementation**: [LoginPage.tsx:91-108](frontend/src/pages/LoginPage.tsx#L91-L108)

Example:
```typescript
const allowedOrigins = [window.location.origin];
if (returnUrl.startsWith('http://') || returnUrl.startsWith('https://') || returnUrl.startsWith('//')) {
  const parsed = new URL(returnUrl, window.location.origin);
  if (!allowedOrigins.some(origin => parsed.origin === origin)) {
    setError(t('auth.invalidRedirect'));
    return;
  }
}
```

### 5. Dependency Security

#### Vulnerability Remediation
All high-severity npm vulnerabilities have been fixed:

**Before**: 15 vulnerabilities (13 high, 2 moderate)
**After**: 0 vulnerabilities ✅

**Fixed packages**:
- ✅ `react-router-dom`: Upgraded to v7.18.2+ (Open redirect & XSS fix)
- ✅ `postcss`: Upgraded to v8.5.23+ (Path traversal fix)
- ✅ `nanoid`: Upgraded to v3.3.18+ (DoS fix)
- ✅ `brace-expansion`: Upgraded to v1.1.18+ (DoS fix)
- ✅ `js-yaml`: Upgraded to v4.3.1+ (DoS fix)
- ✅ `undici`: Upgraded to v7.29.0+ (Multiple fixes)
- ✅ `svgo`: Upgraded to v3.3.4+ (XSS fix)
- ✅ `ip-address`: Upgraded to latest (SSRF fix)
- ❌ `puppeteer` & `critical`: **Removed** (dev-only dependencies with unfixed vulnerabilities)

### 6. Security Headers

#### Production Configuration
Security headers configured for Nginx and static hosting:

**Files**:
- `frontend/nginx-security.conf`: Nginx configuration
- `frontend/public/_headers`: Netlify/Vercel compatible headers

**Headers Implemented**:
```nginx
Content-Security-Policy: default-src 'self'; script-src 'self' 'unsafe-inline' 'unsafe-eval'; ...
X-Frame-Options: SAMEORIGIN
X-Content-Type-Options: nosniff
X-XSS-Protection: 1; mode=block
Referrer-Policy: strict-origin-when-cross-origin
Permissions-Policy: accelerometer=(), camera=(), geolocation=(), ...
```

**HSTS** (HTTPS only):
```nginx
Strict-Transport-Security: max-age=31536000; includeSubDomains; preload
```

### 7. Rate Limiting (Nginx)

Protected endpoints:
```nginx
location /auth/login {
    limit_req zone=login_limit burst=3 nodelay;  # 5 req/min
}

location /api/ {
    limit_req zone=api_limit burst=20 nodelay;  # 100 req/min
}
```

## 🚀 Deployment Checklist

### Before Production:

- [ ] Enable HTTPS and force all HTTP → HTTPS redirects
- [ ] Enable HSTS header (uncomment in `nginx-security.conf`)
- [ ] Set `Secure` flag on all cookies
- [ ] Configure CSP to remove `unsafe-inline` and `unsafe-eval` (requires code refactoring)
- [ ] Implement backend CSRF validation
- [ ] Set up rate limiting on authentication endpoints
- [ ] Enable security headers (use provided config files)
- [ ] Run `npm audit` to verify 0 vulnerabilities
- [ ] Test OAuth redirect validation with malicious URLs
- [ ] Enable Content Security Policy reporting

### Environment Variables:

```bash
# Production
VITE_API_BASE_URL=https://api.yourdomain.com

# Security
NODE_ENV=production
```

## 🔍 Security Testing

### Manual Tests:

1. **XSS Test**: Try injecting `<script>alert('XSS')</script>` in all input fields
2. **CSRF Test**: Make POST request without X-CSRF-Token header (should fail)
3. **Open Redirect**: Try `?return=https://evil.com` on login page (should fail)
4. **Token Expiry**: Check that expired tokens redirect to login
5. **HTTPS**: Verify all production traffic uses HTTPS

### Automated Tests:

```bash
# Run dependency audit
npm audit

# Check for security issues
npm run lint

# Run tests
npm test
```

## 📋 Known Limitations

1. **LocalStorage Security**: Tokens in localStorage are vulnerable to XSS. Consider migrating to httpOnly cookies.
2. **CSP Compatibility**: Current CSP allows `unsafe-inline` and `unsafe-eval` for compatibility. Should be tightened.
3. **Obfuscation vs Encryption**: Username storage uses XOR obfuscation, not true encryption.
4. **Client-Side Validation**: All frontend validation can be bypassed. Backend validation is mandatory.
5. **No Subresource Integrity**: Third-party scripts (if added) should use SRI hashes.

## 🛡️ Security Best Practices

### For Developers:

1. **Never trust user input**: Always validate and sanitize
2. **Use parameterized queries**: Prevent SQL injection (backend)
3. **Avoid `eval()` and `Function()`**: Code injection risk
4. **Keep dependencies updated**: Run `npm audit` regularly
5. **Follow principle of least privilege**: Request only necessary permissions
6. **Log security events**: Failed logins, CSRF failures, etc.

### For Users:

1. Use strong, unique passwords
2. Enable 2FA when available
3. Don't share credentials
4. Log out on shared devices
5. Keep browser updated

## 📞 Security Contacts

If you discover a security vulnerability, please report it to:
- Email: security@yourcompany.com
- Do NOT create public GitHub issues for security vulnerabilities

## 📚 References

- [OWASP Top 10](https://owasp.org/www-project-top-ten/)
- [OWASP Cheat Sheet Series](https://cheatsheetseries.owasp.org/)
- [MDN Web Security](https://developer.mozilla.org/en-US/docs/Web/Security)
- [Content Security Policy](https://content-security-policy.com/)
