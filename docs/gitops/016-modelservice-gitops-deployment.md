# ModelService GitOps Deployment

## Purpose

This document explains how the `ModelService` custom resource represents model deployment intent and how the Go operator reconciles that intent into Kubernetes resources.

## API

```text
apiVersion: platform.anselem.dev/v1alpha1
kind: ModelService
```

## GitOps Path

```text
modelservices/
├── base/
└── overlays/dev/
```

## Argo Application

```text
ai-platform-modelservices
```

## ModelService Abstraction

A user supplies a small platform-facing model configuration.

Conceptually:

```json
{
  "name": "fraud-model",
  "image": "fraud-model:v3",
  "replicas": 2
}
```

The platform creates a `ModelService`.

The Go operator reconciles lower-level resources such as:

```text
Deployment
Service
PVC
ServiceAccount
Policies
HTTPRoute
```

based on the current operator implementation.

## Control Loop

```text
ModelService desired state
        |
        v
Go Operator
        |
        v
Kubernetes resources
        |
        v
drift/delete
        |
        v
operator observes mismatch
        |
        v
reconcile
```

## Render GitOps

```bash
cd /mnt/data/ai-platform-gitops

kubectl kustomize \
  modelservices/overlays/dev \
  >/tmp/modelservices.yaml
```

## Server Validation

Because `ModelService` is a CRD, ensure the CRD is installed first.

Then:

```bash
kubectl apply \
  --dry-run=server \
  -f /tmp/modelservices.yaml
```

## Argo Validation

```bash
argocd app get \
  ai-platform-modelservices \
  --refresh
```

## Live Resources

```bash
kubectl get modelservices -A
```

Describe:

```bash
kubectl describe modelservice \
  <name> \
  -n ai-platform
```

## Related Reconciled Objects

```bash
kubectl get deployment,service,pvc,serviceaccount \
  -n ai-platform
```

Inspect owner references where relevant:

```bash
kubectl get deployment <name> \
  -n ai-platform \
  -o yaml
```

## Reconciliation Test

Use only a disposable development workload.

1. identify operator-owned Deployment
2. record manifest/status
3. delete that child Deployment
4. watch operator recreate it
5. verify desired `ModelService` remains unchanged

Example:

```bash
kubectl delete deployment \
  <operator-owned-deployment> \
  -n ai-platform
```

Watch:

```bash
kubectl get deployment \
  -n ai-platform \
  -w
```

## Distinguish Argo vs Operator Reconciliation

Argo:

```text
Git -> ModelService
```

Operator:

```text
ModelService -> derived Kubernetes resources
```

This distinction is critical when troubleshooting drift.

## Security Considerations

The abstraction must not bypass admission.

Any Pod eventually created by the operator remains subject to:

```text
approved registry
digest policy
Sigstore trust verification
```

## Official References

- Kubernetes custom resources: https://kubernetes.io/docs/concepts/extend-kubernetes/api-extension/custom-resources/
- Operator pattern: https://kubernetes.io/docs/concepts/extend-kubernetes/operator/
- Kubebuilder book: https://book.kubebuilder.io/
