# Security Policy

Vulnerability disclosure policy and security response SLAs for `brain-alpha-pipeline`.

## Reporting Vulnerabilities

If you discover a security vulnerability or credential exposure risk, do not open a public issue. Submit a private advisory at:

https://github.com/Xtley001/brain-alpha-pipeline/security/advisories

The repository maintainers acknowledge receipt within 48 hours and provide remediation status updates.

## Supported Versions

| Version | Status |
|---|---|
| `main` branch | Supported |
| Release tags $\ge$ `v0.1.0` | Supported |
| Releases $<$ `v0.1.0` | Unsupported |

## Scope

- Pipeline orchestration code in `.github/workflows/` and `scripts/`
- Modular Python libraries in `brain_libraries/`
- Credential masking and database connection handling across `brain_core` and `brain_store`

Excludes misconfiguration of third-party services (e.g. exposed PostgreSQL databases, leaked API keys in local untracked `.env` files).
