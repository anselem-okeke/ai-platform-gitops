# App-of-Apps Architecture

## Purpose

This document explains how Argo CD Applications are bootstrapped and grouped using a root Application and child Applications.

## Root Application

Git path:

```text
clusters/dev/root-application.yaml
```

Argo Application:

```text
ai-platform-root
```

The root points to child Application definitions under:

```text
clusters/dev/apps/
```

## Child Applications

```text
clusters/dev/apps/
├── operator.yaml
├── api.yaml
├── gateway.yaml
├── monitoring.yaml
├── modelservices.yaml
├── policies.yaml
├── namespaces.yaml
├── policy-controller.yaml
└── trust-policies.yaml
```

## Control Flow

```text
root-application.yaml
       |
       v
ai-platform-root
       |
       v
clusters/dev/apps/*
       |
       +--> ai-platform-operator
       +--> ai-platform-api
       +--> ai-platform-gateway
       +--> ai-platform-monitoring
       +--> ai-platform-modelservices
       +--> ai-platform-policies
       +--> ai-platform-namespaces
       +--> policy-controller
       +--> trust-policies
```

## Manual Root Sync

The root is intentionally manual.

Reason:

The root controls **which Applications exist**, their source repositories, destinations, and other topology-level properties.

A Git change under:

```text
clusters/dev/apps/
```

does not automatically become live until the root Application is synchronized.

Typical procedure:

```bash
argocd app get ai-platform-root --refresh
argocd app sync ai-platform-root
argocd app wait ai-platform-root --sync --health --timeout 300
```

## Automated Child Sync

Once a child Application exists, changes under its source path may auto-sync.

Example:

```text
platform/monitoring/base/policy-controller-servicemonitor.yaml
```

is managed by:

```text
ai-platform-monitoring
```

After merge, the monitoring child can reconcile it automatically without a root sync.

## Why This Split Is Valuable

```text
Topology change
  -> human-controlled root sync

Workload/config change within known app
  -> automated child reconciliation
```

This creates a safety boundary between platform structure and routine desired-state updates.

## Health Verification

```bash
argocd app list
```

Inspect root:

```bash
argocd app get ai-platform-root --refresh
```

Inspect a child:

```bash
argocd app get ai-platform-api --refresh
```

Wait for child:

```bash
argocd app wait ai-platform-api \
  --sync \
  --health \
  --timeout 300
```

## Adding a New Child Application

1. create the Application manifest under `clusters/dev/apps/`
2. add it to `clusters/dev/apps/kustomization.yaml` if required by the repository layout
3. render/validate the Applications Kustomization
4. open a GitOps PR
5. merge after validation
6. refresh `ai-platform-root`
7. manually sync root
8. verify the child exists
9. verify child sync/health

## Removing a Child

Removal changes topology and should be treated as destructive.

Before removing:

- understand prune behavior
- confirm data/resource ownership
- confirm whether deletion should cascade
- use a reviewed PR
- synchronize root deliberately

## Official References

- Argo CD cluster bootstrapping / App-of-Apps: https://argo-cd.readthedocs.io/en/stable/operator-manual/cluster-bootstrapping/
- Argo CD Applications: https://argo-cd.readthedocs.io/en/stable/user-guide/application-specification/
- Argo CD automated sync: https://argo-cd.readthedocs.io/en/stable/user-guide/auto_sync/

## Related Documentation

- [005-gitops-architecture.md](005-gitops-architecture.md)
- [010-argocd-project.md](010-argocd-project.md)
- [030-argocd-sync-selfheal-and-prune.md](030-argocd-sync-selfheal-and-prune.md)
