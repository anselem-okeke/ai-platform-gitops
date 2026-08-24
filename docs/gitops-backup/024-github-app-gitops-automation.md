# GitHub App GitOps Automation

## Purpose

Documents the machine identity used for source-to-GitOps updates.

## Why GitHub App
The source release workflow must update the separate GitOps repository without a developer PAT. A GitHub App provides short-lived installation-scoped credentials and auditable machine identity.

Pinned token action:
```text
bcd2ba49218906704ab6c1aa796996da409d3eb1
```

## Flow
```text
release -> installation token -> clone GitOps -> bot branch -> digest commit -> PR
```
The PR is intentionally not auto-merged.

## Failure Mode Encountered
A `Not Found` installation lookup error can indicate that the App exists but is not installed for the target repository, or that owner/repository inputs or credentials are wrong. Validate installation scope before changing workflow logic.

GitHub App private keys belong in GitHub secret storage, never Git.

## Official References
- https://docs.github.com/apps
- https://docs.github.com/apps/creating-github-apps/authenticating-with-a-github-app/authenticating-as-a-github-app-installation
- https://docs.github.com/apps/using-github-apps/installing-your-own-github-app

## Documentation Note

Commands, versions, resource names, and behavior in this document reflect the implemented AI Platform development environment. Re-validate version-specific upstream behavior before applying the same procedure to a later release or production environment.
