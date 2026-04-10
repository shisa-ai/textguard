# Security Policy

## Supported Versions

Only the latest published release receives security fixes. There are no backport branches.

## Reporting a Vulnerability

**Do not open a public issue for security vulnerabilities.**

Use GitHub's private vulnerability reporting:

1. Go to the [Security Advisories](https://github.com/shisa-ai/textguard/security/advisories) page.
2. Click **Report a vulnerability**.
3. Describe the issue, affected versions, and reproduction steps.

You should receive an initial response within 7 days. Fixes for confirmed vulnerabilities will be released as patch versions.

## Scope

Reports are welcome for issues in:

- Unicode normalization, detection, or stripping bypasses
- Decode pipeline bounds violations or evasion
- YARA rule gaps that allow known attack patterns through
- PromptGuard model verification or fetch integrity issues
- Findings that leak original text content (injection vector)
- Dependency-related vulnerabilities in optional extras
