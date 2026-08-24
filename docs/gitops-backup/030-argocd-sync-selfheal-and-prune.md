# Argo CD Sync, Self-Heal, and Prune

## Purpose

Documents automated child reconciliation and manual root topology control.

## Child Policy
```yaml
syncPolicy:
  automated:
    prune: true
    selfHeal: true
```

Self-heal was empirically validated by introducing manual drift and observing Argo restore Git state. Prune is configured, but destructive whole-resource prune should not be claimed as empirically tested unless a controlled deletion test is performed.

## Manual Root
Changes under `clusters/dev/apps/*` require manual `ai-platform-root` sync; changes inside an existing child source path auto-sync.

## Narrow Drift Ignore
Policy Controller webhooks receive an external selector:
```yaml
- key: webhooks.knative.dev/exclude
  operator: DoesNotExist
```
A narrow `ignoreDifferences` rule is used for exactly that externally managed selector. Do not broadly ignore webhook resources.

## Official References
- https://argo-cd.readthedocs.io/en/stable/user-guide/auto_sync/
- https://argo-cd.readthedocs.io/en/stable/user-guide/sync-options/
- https://argo-cd.readthedocs.io/en/stable/user-guide/diffing/

## Documentation Note

Commands, versions, resource names, and behavior in this document reflect the implemented AI Platform development environment. Re-validate version-specific upstream behavior before applying the same procedure to a later release or production environment.
