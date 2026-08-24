# GitOps Architecture

## Purpose

This document defines the GitOps operating model for the AI Platform and explains how Git, Argo CD, Kustomize, immutable image digests, pull requests, and Kubernetes reconciliation work together.

The goal is to make Git the authoritative deployment source of truth while keeping build, promotion, and runtime enforcement as separate security boundaries.

## Scope

Source repository:

```text
/mnt/data/ai-platform-operator
```

GitOps repository:

```text
/mnt/data/ai-platform-gitops
```

GitOps remote:

```text
https://github.com/anselem-okeke/ai-platform-gitops.git
```

## Core Ownership Model

```text
Source repository
    |
    | builds, tests, scans, attests
    v
GHCR
    |
    | immutable SHA-256 digest
    v
GitOps repository
    |
    | approved desired state
    v
Argo CD
    |
    | reconciliation
    v
Kubernetes
```

The source repository does **not** normally deploy directly to the cluster.

The GitOps repository does **not** rebuild application artifacts.

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
├── docs/
├── .github/workflows/
└── README.md
```

## GitOps Invariants

The platform depends on the following invariants:

1. managed cluster state is represented in Git
2. production/runtime images are deployed by digest
3. CI creates GitOps changes rather than applying directly to Kubernetes
4. GitOps pull requests are validated
5. human merge remains the promotion boundary
6. Argo reconciles approved state
7. Kubernetes admission independently verifies runtime policy

## Root and Child Applications

Root Application:

```text
clusters/dev/root-application.yaml
```

Argo name:

```text
ai-platform-root
```

Child Application definitions:

```text
clusters/dev/apps/
```

Children include:

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

## Important Sync Boundary

### Topology Changes

A change under:

```text
clusters/dev/apps/
```

changes the Application topology.

The root Application is intentionally manually synchronized.

Procedure:

```bash
argocd app get ai-platform-root --refresh
argocd app sync ai-platform-root
argocd app wait ai-platform-root --sync --health --timeout 300
```

### Existing Child Source Changes

A change inside an already-created child's source path can auto-sync.

Example:

```text
platform/monitoring/base/policy-controller-prometheusrule.yaml
```

is reconciled by:

```text
ai-platform-monitoring
```

No root sync is required.

## Child Reconciliation

Typical child policy:

```yaml
syncPolicy:
  automated:
    prune: true
    selfHeal: true
```

Common option:

```yaml
syncOptions:
  - CreateNamespace=false
```

External Helm Applications may use different namespace creation behavior where necessary.

## Image Versioning

Runtime images use immutable references:

```text
ghcr.io/anselem-okeke/ai-platform-api@sha256:<digest>
ghcr.io/anselem-okeke/ai-platform-operator@sha256:<digest>
```

The release pipeline opens a GitOps PR that updates only the approved image digests.

## GitOps Change Workflow

```text
source main
   |
   v
release builds images
   |
   v
GHCR digests
   |
   v
GitHub App token
   |
   v
automation/image-<source-sha>
   |
   v
update GitOps digests
   |
   v
Validate GitOps
   |
   v
human merge
   |
   v
Argo reconciliation
```

## Local Validation

Enter GitOps repository:

```bash
cd /mnt/data/ai-platform-gitops
```

Check Git:

```bash
git status --short
git diff --check
```

Render all development overlays:

```bash
kubectl kustomize platform/operator/overlays/dev >/tmp/operator.yaml
kubectl kustomize platform/api/overlays/dev >/tmp/api.yaml
kubectl kustomize platform/gateway/overlays/dev >/tmp/gateway.yaml
kubectl kustomize platform/monitoring/overlays/dev >/tmp/monitoring.yaml
kubectl kustomize platform/policies/overlays/dev >/tmp/policies.yaml
kubectl kustomize modelservices/overlays/dev >/tmp/modelservices.yaml
```

Render the child Application set:

```bash
kubectl kustomize clusters/dev/apps >/tmp/apps.yaml
```

## Drift Validation

Record desired replicas:

```bash
ORIGINAL_REPLICAS="$(
  kubectl get deployment ai-platform-api \
    -n ai-platform \
    -o jsonpath='{.spec.replicas}'
)"
```

Create drift:

```bash
kubectl scale deployment ai-platform-api \
  -n ai-platform \
  --replicas=3
```

Argo should restore the Git-defined value.

## Rollback

Preferred rollback:

```bash
git revert <bad-gitops-commit>
```

Then merge through the same validated PR path.

This restores the previously known immutable digest and preserves Git as the source of truth.

## Security Considerations

- direct CI-to-cluster deployment is intentionally avoided
- Git history records deployment intent
- immutable digests prevent tag mutation
- root topology changes remain human-controlled
- child drift is automatically repaired
- runtime admission remains independent of GitOps validation

## Official References

- Argo CD: https://argo-cd.readthedocs.io/en/stable/
- Argo CD automated sync: https://argo-cd.readthedocs.io/en/stable/user-guide/auto_sync/
- Argo CD cluster bootstrapping: https://argo-cd.readthedocs.io/en/stable/operator-manual/cluster-bootstrapping/
- Kustomize: https://kubernetes.io/docs/tasks/manage-kubernetes-objects/kustomization/
- OpenGitOps: https://opengitops.dev/
