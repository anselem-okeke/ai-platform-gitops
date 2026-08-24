# Operator GitOps Deployment

## Purpose

This document describes how the AI Platform Go operator is built, promoted by digest, admitted, and reconciled through Argo CD.

## Source Repository

```text
/mnt/data/ai-platform-operator
```

## GitOps Path

```text
/mnt/data/ai-platform-gitops/platform/operator
```

Structure:

```text
platform/operator/
├── base/
└── overlays/dev/
```

## Argo Application

```text
ai-platform-operator
```

## Namespace

```text
ai-platform-operator-system
```

## Image

```text
ghcr.io/anselem-okeke/ai-platform-operator@sha256:<digest>
```

## Build Security

Runtime characteristics:

```text
Go 1.26.6 builder
CGO_ENABLED=0
trimpath
distroless static Debian 13
USER 65532:65532
binary /manager
```

## Delivery Flow

```text
source merge
  |
  v
build operator
  |
  v
Trivy
  |
  v
SBOM + attest
  |
  v
GHCR digest
  |
  v
GitOps PR
  |
  v
human merge
  |
  v
Argo
  |
  v
native admission
  |
  v
Sigstore
  |
  v
operator Pod
```

## Render Desired State

```bash
cd /mnt/data/ai-platform-gitops

kubectl kustomize \
  platform/operator/overlays/dev \
  >/tmp/operator.yaml
```

Inspect image:

```bash
grep -n 'image:' /tmp/operator.yaml
```

Expected:

```text
ghcr.io/anselem-okeke/ai-platform-operator@sha256:
```

## Server Validation

```bash
kubectl apply \
  --dry-run=server \
  -f /tmp/operator.yaml
```

## Argo Validation

```bash
argocd app get \
  ai-platform-operator \
  --refresh
```

Wait:

```bash
argocd app wait \
  ai-platform-operator \
  --sync \
  --health \
  --timeout 300
```

## Live Image Validation

```bash
kubectl get deployment \
  ai-platform-operator-controller-manager \
  -n ai-platform-operator-system \
  -o jsonpath='{.spec.template.spec.containers[*].image}{"\n"}'
```

Expected:

```text
@sha256:
```

## Rollout Validation

```bash
kubectl rollout status \
  deployment/ai-platform-operator-controller-manager \
  -n ai-platform-operator-system \
  --timeout=300s
```

## Admission Positive Test

Restart:

```bash
kubectl rollout restart \
  deployment/ai-platform-operator-controller-manager \
  -n ai-platform-operator-system
```

Then wait for successful rollout.

This validates that the currently trusted digest is accepted by both native and Sigstore admission.

## Namespace Enforcement

```bash
kubectl get namespace \
  ai-platform-operator-system \
  --show-labels
```

Expected:

```text
policy.sigstore.dev/include=true
```

## Logs

```bash
kubectl logs \
  -n ai-platform-operator-system \
  deployment/ai-platform-operator-controller-manager \
  --tail=200
```

## Troubleshooting

### Rollout denied

Check:

- image starts with approved GHCR path
- image uses full SHA-256 digest
- trust policy exists
- image attestation exists
- Policy Controller healthy

### Deployment name differs

```bash
kubectl get deployment \
  -n ai-platform-operator-system
```

Use the live name.

## Official References

- Kubernetes Deployments: https://kubernetes.io/docs/concepts/workloads/controllers/deployment/
- Kubernetes operator pattern: https://kubernetes.io/docs/concepts/extend-kubernetes/operator/
- Argo CD Application spec: https://argo-cd.readthedocs.io/en/stable/user-guide/application-specification/
