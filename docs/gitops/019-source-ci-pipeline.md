# Source CI Pipeline

## Purpose

This document describes the source repository CI controls that must pass before a source commit can become a releasable artifact.

The design goal is simple:

```text
security visibility
    !=
security enforcement
```

A check only protects the release if failure actually blocks the delivery path.

## Repository

```text
/mnt/data/ai-platform-operator
```

Remote:

```text
git@github.com:anselem-okeke/ai-platform-operator.git
```

## CI Workflow Set

The source repository uses workflows for:

```text
lint.yml
test.yml
test-e2e.yml
security.yml
secret-scan.yml
release-images.yml
```

The exact filenames should be validated against the repository before reuse in another environment.

## Pre-Merge Security Boundary

Required checks are enforced on pull requests before merge to `main`.

Validated required checks include:

```text
Gitleaks
Lint / Run on Ubuntu (pull_request)
E2E Tests / Run on Ubuntu (pull_request)
Tests / Run on Ubuntu (pull_request)
govulncheck
CodeQL
```

This is important because the release workflow itself runs from `main`.

## Why Pre-Merge Enforcement Matters

GitHub Actions workflows triggered from the same push run independently.

That means this unsafe pattern is possible if checks are not branch-required:

```text
Tests        PASS
E2E          PASS
CodeQL       PASS
Gitleaks     FAIL
Release      PASS
```

The platform prevents that by requiring the relevant checks **before merge**.

Correct delivery model:

```text
PR
 |
 +--> required CI checks
 |
 v
protected main
 |
 v
release workflow
```

## Local Validation Before Opening a PR

### 1. Enter Source Repository

```bash
cd /mnt/data/ai-platform-operator
```

### 2. Update Main

```bash
git switch main
git pull --ff-only origin main
```

### 3. Create Feature Branch

```bash
git switch -c feat/<change-name>
```

### 4. Run Lint Configuration Validation

```bash
make lint-config
```

### 5. Run Lint

```bash
make lint
```

Expected:

```text
0 issues
```

### 6. Run Tests

```bash
make test
```

### 7. Run Go Vet

```bash
go vet ./...
```

### 8. Run govulncheck

```bash
govulncheck ./...
```

Validated interpretation:

```text
0 reachable vulnerabilities
```

Important:

Do not document this as:

```text
0 vulnerable dependencies
```

The tool can still report vulnerabilities in imported modules/packages that are not reachable from the current program call graph.

### 9. Run E2E

Use the repository E2E target or workflow-equivalent command:

```bash
make test-e2e
```

If the repository exposes a different target, follow the Makefile used by the workflow.

### 10. Review Diff

```bash
git status --short
git diff
git diff --check
```

### 11. Commit

```bash
git add -A
git diff --cached --check
git diff --cached
git commit -m "<type>: <description>"
```

### 12. Push

```bash
git push -u origin feat/<change-name>
```

## Pull Request Validation

Create PR:

```bash
gh pr create \
  --base main \
  --head feat/<change-name> \
  --title "<title>" \
  --body "<summary>"
```

Check status:

```bash
gh pr checks <PR_NUMBER>
```

The PR must not merge until all required checks pass.

## CodeQL

CodeQL is a required source-security check.

The CodeQL Actions were pinned to a full commit SHA:

```text
f205ea1c3313d32999d8d6a48b4f6530d4437b38
```

This pin corresponded to the selected release at implementation time.

## Gitleaks

Gitleaks protects both current changes and repository history.

Full-history scan:

```bash
gitleaks git \
  --redact \
  --verbose \
  .
```

For CI history scanning, checkout must use:

```yaml
fetch-depth: 0
```

## GitHub Actions Hardening

Third-party GitHub Actions are pinned to immutable full commit SHAs.

Validated examples:

```text
github/codeql-action/*
f205ea1c3313d32999d8d6a48b4f6530d4437b38

actions/attest
508db95dd578ae2727ebd6217d5ba78e4fbda05d

actions/create-github-app-token
bcd2ba49218906704ab6c1aa796996da409d3eb1
```

## Workflow Permissions

Use:

```yaml
permissions: {}
```

at workflow scope where possible, then grant only the permissions required by each job.

## Release Boundary

The release workflow runs only on:

```yaml
on:
  push:
    branches:
      - main
```

The GitOps update job also depends on both image build jobs.

Therefore source delivery has two independent gates:

```text
required pre-merge checks
        +
successful release build jobs
```

## Failure Scenarios

### Required PR check fails

Expected:

```text
merge blocked
```

### Release build fails

Expected:

```text
update-gitops does not run
```

### Gitleaks finding

Do not paste the secret.

Record only:

```text
rule
path
commit
line
```

Then rotate/revoke the credential if real.

## Validation Checklist

```text
[ ] feature branch used
[ ] lint-config passes
[ ] lint passes
[ ] tests pass
[ ] E2E passes
[ ] go vet passes
[ ] govulncheck reports no reachable vulnerability
[ ] Gitleaks passes
[ ] CodeQL passes
[ ] required PR checks green
[ ] merge protected
```

## Official References

- GitHub Actions: https://docs.github.com/actions
- Workflow permissions: https://docs.github.com/actions/using-jobs/assigning-permissions-to-jobs
- Required checks: https://docs.github.com/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches/about-protected-branches
- CodeQL: https://docs.github.com/code-security/code-scanning/introduction-to-code-scanning/about-code-scanning-with-codeql
- Go vulnerability management: https://go.dev/security/vuln/
- Gitleaks: https://github.com/gitleaks/gitleaks
