# AI Platform API GitOps Deployment

## Purpose

This document records how the AI Platform REST API is deployed through GitOps.

## GitOps Path

```text
platform/api/
├── base/
└── overlays/
    └── dev/
```

Argo Application:

```text
ai-platform-api
```

Namespace:

```text
ai-platform
```

## Image

```text
ghcr.io/anselem-okeke/ai-platform-api@sha256:<digest>
```

The digest is updated through the automated source-to-GitOps pull request.

## Runtime Image

The API uses the same hardened container principles as the operator:

- Go 1.26.6 builder
- static build
- `CGO_ENABLED=0`
- trimpath/linker hardening
- distroless static Debian 13
- UID/GID `65532:65532`

Runtime binary:

```text
/platform-api
```

## Request Path

Conceptually:

```text
Client
   |
   v
https://api.ai-platform.local
   |
   v
Envoy Gateway / HTTPRoute
   |
   v
AI Platform API Service
   |
   v
API Deployment
```

The API interacts with Kubernetes to create/manage the higher-level platform resource model.

## Model Deployment API

A conceptual request:

```bash
curl -X POST \
  https://api.ai-platform.local/models \
  -H 'Content-Type: application/json' \
  -d '{
    "name": "fraud-model",
    "image": "fraud-model:v3",
    "replicas": 2
  }'
```

The platform uses these high-level parameters to produce `ModelService` desired state.

## Delivery Flow

```text
source main
   |
   v
build-api
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
API digest
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
admission
   |
   v
API Deployment
```

## Validation

Render:

```bash
kubectl kustomize platform/api/overlays/dev
```

Check image:

```bash
kubectl get deployment ai-platform-api \
  -n ai-platform \
  -o jsonpath='{.spec.template.spec.containers[*].image}{"\n"}'
```

Expected form:

```text
ghcr.io/anselem-okeke/ai-platform-api@sha256:<digest>
```

Rollout:

```bash
kubectl rollout status \
  deployment/ai-platform-api \
  -n ai-platform \
  --timeout=300s
```

Argo:

```bash
argocd app get ai-platform-api --refresh
```

## Drift Test

A controlled manual replica change can be used to demonstrate Argo self-heal:

```bash
kubectl scale deployment ai-platform-api \
  -n ai-platform \
  --replicas=3
```

Argo should restore the Git-defined value.

## Known Operational Symptom

A previous rollout exposed:

```text
ErrImageNeverPull
```

This can occur in kind when the image reference/pull policy does not match how the image is made available.

The current GitOps release model uses GHCR immutable digests and should be diagnosed by checking:

```bash
kubectl describe pod <pod> -n ai-platform
kubectl get deployment ai-platform-api -n ai-platform -o yaml
```

## Official References

- Kubernetes Deployments: https://kubernetes.io/docs/concepts/workloads/controllers/deployment/
- Kubernetes Services: https://kubernetes.io/docs/concepts/services-networking/service/
- Argo CD automated sync: https://argo-cd.readthedocs.io/en/stable/user-guide/auto_sync/
- Kustomize: https://kubernetes.io/docs/tasks/manage-kubernetes-objects/kustomization/

## Related Documentation

- [014-operator-gitops-deployment.md](014-operator-gitops-deployment.md)
- [016-modelservice-gitops-deployment.md](016-modelservice-gitops-deployment.md)
- [017-gateway-and-routing.md](017-gateway-and-routing.md)
