# ModelService GitOps Deployment

## Purpose

This document explains how `ModelService` resources represent model deployment intent and how GitOps can manage example/declarative model workloads.

## API

```text
apiVersion: platform.anselem.dev/v1alpha1
kind: ModelService
```

## GitOps Path

```text
modelservices/
├── base/
└── overlays/
    └── dev/
```

Argo Application:

```text
ai-platform-modelservices
```

## Role of ModelService

`ModelService` is a platform abstraction.

Instead of asking an ML engineer to directly maintain every lower-level Kubernetes resource:

```text
Deployment
Service
PVC
ServiceAccount
Policies
HTTPRoute
```

the user expresses higher-level intent.

Conceptually:

```text
ModelService
     |
     v
Go Operator
     |
     +--> Deployment
     +--> Service
     +--> storage
     +--> identity
     +--> policies
     +--> routing
```

## Reconciliation

The operator observes `ModelService`.

If a managed resource is deleted or drifts:

```text
desired ModelService
       |
       v
operator observes mismatch
       |
       v
recreates/updates child resource
```

This is separate from Argo self-heal:

- Argo reconciles Git-managed resources.
- The Go operator reconciles resources derived from `ModelService`.

## Validation

List:

```bash
kubectl get modelservices -A
```

Describe:

```bash
kubectl describe modelservice <name> -n ai-platform
```

Inspect related Deployments/Services:

```bash
kubectl get deployment,service \
  -n ai-platform
```

Render GitOps:

```bash
kubectl kustomize modelservices/overlays/dev
```

Argo:

```bash
argocd app get ai-platform-modelservices --refresh
```

## Control-Loop Validation

A safe validation pattern:

1. identify a disposable/known test `ModelService`
2. identify an operator-owned child Deployment
3. delete that child resource
4. observe the operator recreate it
5. verify the `ModelService` remains the source of desired state

Do not use this test on a critical production workload without a maintenance plan.

## Security Considerations

The operator-generated Pod images are still subject to Kubernetes admission.

Platform abstraction must never be a way to bypass:

- registry restrictions
- digest requirements
- Sigstore trust verification

## Official References

- Kubernetes custom resources: https://kubernetes.io/docs/concepts/extend-kubernetes/api-extension/custom-resources/
- Kubernetes operator pattern: https://kubernetes.io/docs/concepts/extend-kubernetes/operator/
- Kubebuilder book: https://book.kubebuilder.io/

## Related Documentation

- [001-platform-overview.md](001-platform-overview.md)
- [014-operator-gitops-deployment.md](014-operator-gitops-deployment.md)
- [015-api-gitops-deployment.md](015-api-gitops-deployment.md)
