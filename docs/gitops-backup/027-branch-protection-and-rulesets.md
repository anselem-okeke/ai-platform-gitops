# Branch Protection and Rulesets

## Purpose

Documents protected-main controls and required status checks.

## Source Ruleset
```text
Name: Source Main Protection
ID: 21120105
State: active
Target: default branch
```

Rules include deletion protection, non-fast-forward protection, PR requirement, strict required checks, stale-review handling, and no bypass actors. Current solo-maintainer approval count is `0`; revisit when additional maintainers exist.

Required checks include Gitleaks, lint, tests, E2E, govulncheck, and CodeQL.

## Security Property
```text
required checks pass before merge -> trusted commit reaches main -> release may run
```
This is stronger than trying to coordinate independent post-merge workflows.

GitOps `main` should likewise require PR validation and controlled promotion. Exact live ruleset details should be kept synchronized with repository configuration.

## Official References
- https://docs.github.com/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/about-rulesets
- https://docs.github.com/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/about-code-owners

## Documentation Note

Commands, versions, resource names, and behavior in this document reflect the implemented AI Platform development environment. Re-validate version-specific upstream behavior before applying the same procedure to a later release or production environment.
