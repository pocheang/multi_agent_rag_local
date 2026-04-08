# Changelog

All notable changes to this project will be documented in this file.

The format is based on Keep a Changelog and this project follows Semantic Versioning.

## [0.2] - 2026-04-08

### Added
- Admin operations overview API (`/admin/ops/overview`) and CSV export (`/admin/ops/export.csv`).
- Admin user provisioning flow (`/admin/users/create-admin`) with approval-token verification.
- Admin security actions for user password reset and admin approval-token reset.
- New readiness endpoint and related API coverage.
- New frontend admin operations dashboard, KPI views, trend charts, and CSV export action.
- New tests:
  - `tests/test_admin_ops_api.py`
  - `tests/test_admin_user_provisioning.py`
  - `tests/test_readiness_api.py`

### Changed
- Extended auth/user schema with creator metadata, ticket metadata, approval-token hash, and user classification fields.
- Improved audit log capabilities with richer filters and operational event classification.
- Expanded admin user-management flows (role/status/classification updates) across backend + frontend.
- Enhanced ingestion loaders for OCR/image extraction and text loading fallbacks.
- Updated query and document visibility logic to enforce user-scoped source access more consistently.

### Security
- Added stricter approval-token checks for privileged admin operations.
- Added stronger audit coverage for admin and auth-sensitive actions.

### Tests
- Expanded regression coverage for auth DB service, ingestion loaders, query intent, and agent resilience.

## [0.1.0] - 2026-04-08

### Added
- Initial public release.
- FastAPI backend + React frontend.
- Session, prompt, document upload/reindex/delete flows.
- User data isolation and retrieval allowlist protection.
- Admin file visibility controls (`private` / `public`).
- OCR configuration support with Tesseract.
