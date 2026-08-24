# Source CI Pipeline

## Purpose

Documents pre-merge CI controls in `/mnt/data/ai-platform-operator`.

## Pipeline
```text
PR -> Lint -> Tests -> E2E -> go vet -> govulncheck -> CodeQL -> Gitleaks -> protected main -> release
```

Required source checks include `Gitleaks`, lint, tests, E2E, `govulncheck`, and CodeQL. The key release-safety property is that required checks pass **before merge**. Independent GitHub Actions workflows triggered by the same push can run concurrently, so the release workflow must not depend on unrelated post-merge workflows eventually finishing.

## Go Validation
```bash
make lint-config
make lint
make test
go vet ./...
```

Validated `govulncheck` result: **0 reachable vulnerabilities**. This does not imply that no vulnerable module exists anywhere in the dependency graph.

## Actions Hardening
Third-party actions are pinned to immutable 40-character SHAs. Validated pins include:
```text
CodeQL: <COMMIT_SHA>
actions/attest: <COMMIT_SHA>
actions/create-github-app-token: <COMMIT_SHA>
```

Use least-privilege workflow permissions, preferably `permissions: {}` at workflow scope with explicit job permissions.

## Verification
```bash
ls -1 .github/workflows
grep -RIn 'uses:' .github/workflows
```

## Official References
- https://docs.github.com/actions
- https://docs.github.com/actions/using-jobs/assigning-permissions-to-jobs
- https://docs.github.com/code-security/code-scanning/introduction-to-code-scanning/about-code-scanning-with-codeql
- https://go.dev/security/vuln/
- https://github.com/gitleaks/gitleaks

## Documentation Note

Commands, versions, resource names, and behavior in this document reflect the implemented AI Platform development environment. Re-validate version-specific upstream behavior before applying the same procedure to a later release or production environment.
