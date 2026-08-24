# Rollback Strategy

## Purpose

Defines Git-based rollback to a known immutable digest.

## Principle
Rollback is another desired-state change.

```text
bad GitOps commit -> git revert -> validation/merge -> Argo -> previous digest
```

## Procedure
```bash
git log --oneline -- platform/api/overlays/dev/kustomization.yaml
git revert <commit>
```
Open/merge the rollback PR, then:
```bash
argocd app get ai-platform-api --refresh
argocd app wait ai-platform-api --sync --health --timeout 300
```

Because images are digest-pinned, rollback restores exactly the previously known artifact without rebuilding it. Manual emergency changes must be reconciled back into Git immediately to avoid fighting Argo self-heal.

## Official References
- https://git-scm.com/docs/git-revert
- https://argo-cd.readthedocs.io/en/stable/user-guide/auto_sync/

## Documentation Note

Commands, versions, resource names, and behavior in this document reflect the implemented AI Platform development environment. Re-validate version-specific upstream behavior before applying the same procedure to a later release or production environment.
