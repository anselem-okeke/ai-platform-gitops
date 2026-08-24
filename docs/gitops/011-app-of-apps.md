# App-of-Apps Architecture

## Purpose

This document explains the root Application, child Application definitions, synchronization boundary, and the procedure for adding or modifying an Application.

## Root

File:

```text
clusters/dev/root-application.yaml
```

Application:

```text
ai-platform-root
```

## Child Definitions

```text
clusters/dev/apps/
```

Current set:

```text
operator.yaml
api.yaml
gateway.yaml
monitoring.yaml
modelservices.yaml
policies.yaml
namespaces.yaml
policy-controller.yaml
trust-policies.yaml
```

## Kustomization

The child Application directory contains:

```text
clusters/dev/apps/kustomization.yaml
```

There is no requirement for a separate:

```text
clusters/dev/kustomization.yaml
```

in the implemented structure.

## Flow

```text
root-application.yaml
      |
      v
ai-platform-root
      |
      v
clusters/dev/apps/kustomization.yaml
      |
      +--> ai-platform-api
      +--> ai-platform-operator
      +--> ai-platform-gateway
      +--> ai-platform-monitoring
      +--> ai-platform-modelservices
      +--> ai-platform-policies
      +--> ai-platform-namespaces
      +--> policy-controller
      +--> trust-policies
```

## Adding a Child Application

### 1. Create Manifest

```bash
cd /mnt/data/ai-platform-gitops
```

Create:

```text
clusters/dev/apps/<name>.yaml
```

### 2. Add to Kustomization

Update:

```text
clusters/dev/apps/kustomization.yaml
```

### 3. Render

```bash
kubectl kustomize \
  clusters/dev/apps \
  >/tmp/apps.yaml
```

### 4. Validate

```bash
kubectl apply \
  --dry-run=server \
  -f /tmp/apps.yaml
```

If server-side validation cannot resolve a third-party CRD because it is not yet installed, use the GitOps CI/kubeconform path and validate the Application object itself.

### 5. Commit and PR

```bash
git status --short
git diff --check
git add clusters/dev/apps
git commit -m "feat(argocd): add <name> application"
git push -u origin <branch>
```

### 6. Merge

Wait for GitOps validation and merge.

### 7. Refresh Root

```bash
argocd app get ai-platform-root --refresh
```

### 8. Manual Root Sync

```bash
argocd app sync ai-platform-root
```

### 9. Verify Child

```bash
argocd app get <child-name> --refresh
```

## Modifying an Existing Child Definition

Because the Application manifest itself is under `clusters/dev/apps`, root sync is required after merge.

## Modifying a Child's Source Files

If the child already exists, a source-path change is auto-synced according to the child policy.

## Removing a Child

Treat removal as destructive.

Before removal:

- understand cascade deletion
- inspect prune
- identify persistent data
- confirm shared resources
- use reviewed PR
- manually sync root

## Validation

```bash
argocd app list
```

All expected Applications should appear.

## Official References

- Argo CD cluster bootstrapping: https://argo-cd.readthedocs.io/en/stable/operator-manual/cluster-bootstrapping/
- Application specification: https://argo-cd.readthedocs.io/en/stable/user-guide/application-specification/
