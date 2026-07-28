# Security Policy

## Supported Versions

Currently, this system operates as a single-operator local application without public internet exposure. Only the `main` branch is actively supported with security updates.

| Version | Supported          |
| ------- | ------------------ |
| V1.x    | :white_check_mark: |
| < V1.0  | :x:                |

## Reporting a Vulnerability

If you discover a security vulnerability within Autonomous Media, please immediately contact the project operator.

**Do not file a public issue.** Please report it privately to ensure the system is patched before the vulnerability details are exposed. Given this software accesses YouTube Channels on behalf of the operator, OAuth token leaks and SSRF vulnerabilities are treated as critical priorities.
