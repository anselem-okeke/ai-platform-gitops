# Secret Scanning

## Purpose

Documents Gitleaks CI and full-history scanning.

## Repositories
```text
/mnt/data/ai-platform-operator
/mnt/data/ai-platform-gitops
```

## Full-History Command
```bash
gitleaks git --redact --verbose .
```

CI intended to scan full history should use checkout `fetch-depth: 0`. Use `--redact` so logs do not expose the detected value.

GitOps `.gitignore` protects patterns such as `.local/`, `.env`, `*.jwt`, `*.key`, `*.pem`, and secret YAML patterns. `.gitignore` is only prevention; already tracked data remains in history.

If a leak is found: revoke/rotate immediately, assess scope, clean history if required, rescan, and add a prevention rule.

## Official References
- https://github.com/gitleaks/gitleaks
- https://docs.github.com/code-security/secret-scanning/introduction/about-secret-scanning
- https://docs.github.com/authentication/keeping-your-account-and-data-secure/removing-sensitive-data-from-a-repository

## Documentation Note

Commands, versions, resource names, and behavior in this document reflect the implemented AI Platform development environment. Re-validate version-specific upstream behavior before applying the same procedure to a later release or production environment.
