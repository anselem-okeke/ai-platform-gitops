# Kustomize Architecture

## Purpose

This document defines the base/overlay model used by the GitOps repository and the validation procedure for rendered environment state.

## Pattern

```text
component/
├── base/
│   ├── kustomization.yaml
│   └── resources...
└── overlays/
    └── dev/
        ├── kustomization.yaml
        └── patches / images / replacements
```

## Components

```text
platform/operator
platform/api
platform/gateway
platform/monitoring
platform/namespaces
platform/policies
modelservices
```

## Base Responsibility

Bases contain reusable configuration.

They may contain placeholders where overlays provide final deployment identity.

Known examples:

```text
controller:latest
ai-platform-api:dev
```

These are not final runtime values.

## Overlay Responsibility

The dev overlay applies environment-specific state including:

```text
image digests
patches
namespace
labels
routing/environment settings
```

## Final Security Invariant

Rendered output must contain approved immutable images.

Example:

```text
ghcr.io/anselem-okeke/ai-platform-api@sha256:<digest>
```

## Render All Overlays

```bash
cd /mnt/data/ai-platform-gitops
```

```bash
kubectl kustomize \
  platform/operator/overlays/dev \
  >/tmp/operator.yaml
```

```bash
kubectl kustomize \
  platform/api/overlays/dev \
  >/tmp/api.yaml
```

```bash
kubectl kustomize \
  platform/gateway/overlays/dev \
  >/tmp/gateway.yaml
```

```bash
kubectl kustomize \
  platform/monitoring/overlays/dev \
  >/tmp/monitoring.yaml
```

```bash
kubectl kustomize \
  platform/policies/overlays/dev \
  >/tmp/policies.yaml
```

```bash
kubectl kustomize \
  modelservices/overlays/dev \
  >/tmp/modelservices.yaml
```

## Inspect Images

```bash
grep -RIn 'image:' \
  /tmp/operator.yaml \
  /tmp/api.yaml
```

Expected production/runtime references contain:

```text
@sha256:
```

## Server-Side Validation

Where CRDs exist:

```bash
kubectl apply \
  --dry-run=server \
  -f /tmp/api.yaml
```

## CI Schema Validation

GitOps CI uses:

```text
kubeconform 0.7.0
```

with strict/summary validation and missing-schema handling for third-party CRDs.

## Strategic Merge Failure Encountered

A previous Kustomize bootstrap patch failed with:

```text
no resource matches strategic merge patch
failed to find unique target for patch
```

Diagnosis:

1. render the base
2. verify resource is included
3. verify exact `apiVersion`
4. verify `kind`
5. verify `metadata.name`
6. verify `namespace`
7. ensure exactly one match

## Why Rendered Validation Is Important

Security controls should evaluate the actual environment configuration.

Rejecting raw reusable placeholders creates false positives and encourages weakening the real deployment policy.

Correct approach:

```text
base reusable
overlay environment-specific
rendered output enforced
```

## Official References

- Kustomize: https://kubernetes.io/docs/tasks/manage-kubernetes-objects/kustomization/
- Kustomize project: https://github.com/kubernetes-sigs/kustomize
- Argo CD Kustomize: https://argo-cd.readthedocs.io/en/stable/user-guide/kustomize/
