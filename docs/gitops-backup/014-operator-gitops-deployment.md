# Operator GitOps Deployment

## Purpose

This document explains how the AI Platform Go operator is deployed from the GitOps repository by immutable digest and reconciled by Argo CD.

## Source vs Deployment

Source repository:

```text
/mnt/data/ai-platform-operator
```

GitOps desired state:

```text
/mnt/data/ai-platform-gitops/platform/operator
```

The source repository builds the operator image. The GitOps repository selects the image digest.

## GitOps Layout

```text
platform/operator/
├── base/
└── overlays/
    └── dev/
```

Argo Application:

```text
ai-platform-operator
```

Target namespace:

```text
ai-platform-operator-system
```

## Image

Registry:

```text
ghcr.io/anselem-okeke/ai-platform-operator
```

Final deployment form:

```text
ghcr.io/anselem-okeke/ai-platform-operator@sha256:<digest>
```

## Container Hardening

The operator image is built using:

- Go 1.26.6 builder
- `CGO_ENABLED=0`
- `-trimpath`
- linker stripping flags
- distroless static Debian 13 runtime
- non-root UID/GID `65532:65532`

The runtime binary path is:

```text
/manager
```

## Delivery

```text
source main
   |
   v
build-operator
   |
   v
Trivy
   |
   v
SBOM
   |
   v
GHCR + attestations
   |
   v
operator digest
   |
   v
GitOps PR updates dev overlay
   |
   v
merge
   |
   v
Argo CD
   |
   v
operator Deployment
```

## Admission Enforcement

The namespace is included in Sigstore enforcement.

The image must satisfy:

- approved `ghcr.io/anselem-okeke/` registry prefix
- complete SHA-256 digest
- trusted artifact attestation policy

## Validation

Render:

```bash
kubectl kustomize \
  platform/operator/overlays/dev
```

Inspect final image:

```bash
kubectl get deployment \
  -n ai-platform-operator-system \
  -o jsonpath='{range .items[*]}{.metadata.name}{" -> "}{.spec.template.spec.containers[*].image}{"\n"}{end}'
```

Rollout:

```bash
kubectl rollout status \
  deployment/ai-platform-operator-controller-manager \
  -n ai-platform-operator-system \
  --timeout=300s
```

Argo:

```bash
argocd app get ai-platform-operator --refresh
```

## Reconciliation Test

A successful rollout of a trusted digest is a positive supply-chain admission test.

An untrusted or invalid image should be denied before the new Pod runs.

## Official References

- Kubernetes Deployments: https://kubernetes.io/docs/concepts/workloads/controllers/deployment/
- Argo CD Applications: https://argo-cd.readthedocs.io/en/stable/user-guide/application-specification/
- Kustomize: https://kubernetes.io/docs/tasks/manage-kubernetes-objects/kustomization/
- Distroless images: https://github.com/GoogleContainerTools/distroless

## Related Documentation

- [015-api-gitops-deployment.md](015-api-gitops-deployment.md)
- [020-container-build-and-hardening.md](020-container-build-and-hardening.md)
- [033-image-admission-policies.md](033-image-admission-policies.md)
