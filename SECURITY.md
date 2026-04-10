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

Use private reporting for issues where public disclosure before a fix creates real risk:

- Supply chain compromise (tampered model packs, signature verification bypass, dependency confusion)
- Exploitable bugs (unbounded resource consumption, code execution via crafted input)
- Findings that echo original text content into LLM contexts (secondary injection vector)

Detection gaps (a Unicode trick that slips through, a YARA rule that misses a pattern) are bugs, not security vulnerabilities. File those as regular [GitHub issues](https://github.com/shisa-ai/textguard/issues).
