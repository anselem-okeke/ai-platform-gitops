# AI Platform API GitOps Deployment

## Purpose

This document describes how the AI Platform REST API is deployed, validated, routed, and reconciled through GitOps.

## GitOps Path

```text
platform/api/
├── base/
└── overlays/dev/
```

## Argo Application

```text
ai-platform-api
```

## Namespace

```text
ai-platform
```

## Image

```text
ghcr.io/anselem-okeke/ai-platform-api@sha256:<digest>
```

## Runtime Characteristics

```text
Go 1.26.6 builder
CGO_ENABLED=0
distroless static Debian 13
USER 65532:65532
binary /platform-api
```

## API Endpoint

```text
https://api.ai-platform.local
```

## Request Path

```text
Client
  |
  v
Envoy Gateway
  |
  v
HTTPRoute
  |
  v
Service
  |
  v
ai-platform-api Deployment
```

## Render Desired State

```bash
cd /mnt/data/ai-platform-gitops

kubectl kustomize \
  platform/api/overlays/dev \
  >/tmp/api.yaml
```

Inspect image:

```bash
grep -n 'image:' /tmp/api.yaml
```

Expected:

```text
ghcr.io/anselem-okeke/ai-platform-api@sha256:
```

## Server Validation

```bash
kubectl apply \
  --dry-run=server \
  -f /tmp/api.yaml
```

## Argo Validation

```bash
argocd app get \
  ai-platform-api \
  --refresh
```

```bash
argocd app wait \
  ai-platform-api \
  --sync \
  --health \
  --timeout 300
```

## Live Workload

```bash
kubectl get deployment,pods,svc \
  -n ai-platform
```

## Live Image

```bash
kubectl get deployment \
  ai-platform-api \
  -n ai-platform \
  -o jsonpath='{.spec.template.spec.containers[*].image}{"\n"}'
```

Expected:

```text
@sha256:
```

## Rollout

```bash
kubectl rollout status \
  deployment/ai-platform-api \
  -n ai-platform \
  --timeout=300s
```

## API Reachability

```bash
curl -I \
  https://api.ai-platform.local
```

Use the actual API health endpoint if one exists in the implementation.

## Model Deployment Request

Conceptual API request:

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

The API converts user-facing intent into a `ModelService` resource.

## Drift Self-Heal Test

Record current replica count:

```bash
ORIGINAL_REPLICAS="$(
  kubectl get deployment ai-platform-api \
    -n ai-platform \
    -o jsonpath='{.spec.replicas}'
)"
```

Create drift:

```bash
kubectl scale \
  deployment/ai-platform-api \
  -n ai-platform \
  --replicas=3
```

Argo should restore the Git-defined count.

## Logs

```bash
kubectl logs \
  -n ai-platform \
  deployment/ai-platform-api \
  --tail=200
```

## Known Failure: ErrImageNeverPull

If a Pod reports:

```text
ErrImageNeverPull
```

check:

```bash
kubectl describe pod <pod> -n ai-platform
```

Inspect:

- image reference
- imagePullPolicy
- registry reachability
- credentials
- kind image availability

Current GitOps deployment uses GHCR immutable digest references.

## Official References

- Kubernetes Deployments: https://kubernetes.io/docs/concepts/workloads/controllers/deployment/
- Kubernetes Services: https://kubernetes.io/docs/concepts/services-networking/service/
- Argo automated sync: https://argo-cd.readthedocs.io/en/stable/user-guide/auto_sync/
