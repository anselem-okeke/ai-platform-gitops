# GitOps Architecture

## Purpose

This document defines how Git, Argo CD, Kustomize, pull requests, and immutable image digests are used to control the AI Platform Kubernetes desired state.

## Scope

The GitOps repository is:

```text
/mnt/data/ai-platform-gitops
```

Remote:

```text
https://github.com/anselem-okeke/ai-platform-gitops.git
```

The source repository builds artifacts. The GitOps repository decides which immutable artifacts and Kubernetes resources are deployed.

## Core Principle

```text
Source code != deployment state
```

The platform follows this ownership model:

```text
ai-platform-operator
      |
      | builds, scans, attests, publishes
      v
     GHCR
      |
      | immutable image digest
      v
ai-platform-gitops
      |
      | desired state
      v
    Argo CD
      |
      | reconciliation
      v
  Kubernetes
```

CI does not normally deploy workloads with `kubectl apply`. Deployment state must first be represented in Git.

## Repository Layout

```text
ai-platform-gitops/
├── argocd/
│   ├── bootstrap/
│   ├── projects/
│   ├── applicationsets/
│   └── exposure/
├── clusters/
│   └── dev/
│       ├── apps/
│       └── root-application.yaml
├── platform/
│   ├── operator/{base,overlays/dev}
│   ├── api/{base,overlays/dev}
│   ├── gateway/{base,overlays/dev}
│   ├── monitoring/{base,overlays/dev}
│   ├── namespaces/{base,overlays/dev}
│   └── policies/{base,overlays/dev}
├── modelservices/{base,overlays/dev}
└── docs/
```

## App-of-Apps Model

The root Application is defined by:

```text
clusters/dev/root-application.yaml
```

It points to:

```text
clusters/dev/apps/
```

Child Applications include:

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

### Important Sync Boundary

The root Application is intentionally manual.

Therefore:

```text
change under clusters/dev/apps/*
    -> manual root sync required
```

but:

```text
change inside source path of an existing child Application
    -> child auto-sync
```

This distinction protects application topology from silently changing.

## Child Sync Policy

Existing child Applications use automated reconciliation where appropriate:

```yaml
syncPolicy:
  automated:
    prune: true
    selfHeal: true
```

Some Applications also use:

```yaml
syncOptions:
  - CreateNamespace=false
```

External infrastructure Helm Applications may use different namespace-creation behavior when necessary.

## Why Self-Heal

Self-heal repairs direct manual changes to managed Kubernetes resources.

Example:

```text
Git says replicas=2
      |
      v
operator manually scales to 3
      |
      v
Argo detects drift
      |
      v
Argo restores replicas=2
```

This makes Git the effective desired-state authority.

## Why Prune

Prune allows resources removed from the declared desired state to be deleted by Argo CD.

Prune must be used deliberately because deleting a manifest from Git can become a Kubernetes deletion.

The platform uses prune for child Applications, while changes to application topology remain protected by the manually synchronized root.

## Image Versioning

Runtime deployments use immutable digests:

```text
ghcr.io/anselem-okeke/ai-platform-api@sha256:<digest>
ghcr.io/anselem-okeke/ai-platform-operator@sha256:<digest>
```

The source release workflow opens a GitOps pull request that updates the digest references.

## Pull-Request Delivery

```text
source main
    |
    v
release workflow
    |
    v
new immutable digests
    |
    v
GitHub App token
    |
    v
GitOps bot branch
    |
    v
GitOps PR
    |
    v
validation
    |
    v
human merge
    |
    v
Argo sync
```

Expected automation branch:

```text
automation/image-<source-sha>
```

Expected commit and PR title:

```text
chore(dev): deploy images from <source-sha>
```

## Validation Boundary

GitOps validation renders Kustomize overlays before validating final image state.

This matters because raw bases may intentionally contain placeholders such as:

```text
controller:latest
ai-platform-api:dev
```

The overlay replaces these with approved immutable digest references.

The deployment invariant therefore applies to the rendered environment, not to reusable base placeholders.

## Rollback

Rollback is Git-based.

```text
bad GitOps commit
    |
    v
git revert
    |
    v
previous immutable digest restored in Git
    |
    v
Argo reconciliation
    |
    v
known-good workload
```

No new image build is required for rollback when reverting to an already trusted digest.

## Operational Verification

```bash
argocd app list
```

Inspect a child Application:

```bash
argocd app get ai-platform-api --refresh
```

Render an overlay:

```bash
kubectl kustomize platform/api/overlays/dev
```

Check Git state:

```bash
git status --short
git diff --check
```

## Security Considerations

- CI has no reason to bypass GitOps with direct cluster deployment.
- Immutable digests prevent tag mutation from changing runtime identity.
- Pull-request review separates build from promotion.
- Argo self-heal reduces unmanaged cluster drift.
- Root topology remains manually synchronized.
- Git history provides an auditable record of desired-state changes.

## Official References

- Argo CD overview: https://argo-cd.readthedocs.io/en/stable/
- Argo CD automated sync: https://argo-cd.readthedocs.io/en/stable/user-guide/auto_sync/
- Argo CD sync options: https://argo-cd.readthedocs.io/en/stable/user-guide/sync-options/
- Kubernetes Kustomize: https://kubernetes.io/docs/tasks/manage-kubernetes-objects/kustomization/
- OpenGitOps principles: https://opengitops.dev/

## Related Documentation

- [003-repository-architecture.md](003-repository-architecture.md)
- [011-app-of-apps.md](011-app-of-apps.md)
- [012-kustomize-architecture.md](012-kustomize-architecture.md)
