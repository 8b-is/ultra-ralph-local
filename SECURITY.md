# Security Policy

## Supported versions

This project is young and currently supports the latest `main` branch only.

## Reporting a vulnerability

Please do not open a public issue for secrets exposure or a security vulnerability.

Instead, report it privately to the repository owner through GitHub security advisories or direct contact if private reporting is enabled on the repo.

## Sensitive data

This project is designed so that:

- OpenRouter and Hugging Face tokens are not committed
- user config lives outside the repo
- runtime logs stay local unless the user explicitly enables uploads

Before publishing logs or screenshots, review them for prompts, decisions, and file paths that may contain sensitive data.
