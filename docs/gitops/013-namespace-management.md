# Namespace Management

## Purpose

This document describes how platform namespaces and security-critical namespace labels are managed through GitOps.

## GitOps Path

```text
platform/namespaces/
├── base/
└── overlays/dev/
```

Argo Application:

```text
ai-platform-namespaces
```

## Important Namespaces

```text
ai-platform
ai-platform-operator-system
argocd
keycloak
gateway-system
envoy-gateway-system
monitoring
cosign-system
```

Not every namespace must be created by the same Kustomization; ownership is defined by the GitOps manifests.

## Policy Controller Enforcement Labels

Protected workload namespaces:

```text
ai-platform
ai-platform-operator-system
```

must contain:

```text
policy.sigstore.dev/include=true
```

## Why Labels Are GitOps-Managed

The label changes the security posture of a namespace.

If manually removed:

```text
Sigstore enforcement may no longer apply
```

Therefore it is treated as desired state and protected by Argo self-heal.

## Render

```bash
cd /mnt/data/ai-platform-gitops

kubectl kustomize \
  platform/namespaces/overlays/dev \
  >/tmp/namespaces.yaml
```

## Validate

```bash
kubectl apply \
  --dry-run=server \
  -f /tmp/namespaces.yaml
```

## Live Verification

```bash
kubectl get namespace ai-platform \
  --show-labels
```

```bash
kubectl get namespace ai-platform-operator-system \
  --show-labels
```

Expected:

```text
policy.sigstore.dev/include=true
```

## Argo Verification

```bash
argocd app get \
  ai-platform-namespaces \
  --refresh
```

Expected:

```text
Synced
Healthy
```

## Drift Test

Remove a non-critical test label only in a controlled development validation or use an approved test field.

For the security label itself, do not casually remove enforcement just to test Argo.

If a security-label drift test is explicitly required:

1. schedule test
2. record current labels
3. remove only in dev
4. observe Argo restore it
5. immediately verify admission remains active

## Security Considerations

Do not bypass an admission problem by removing:

```text
policy.sigstore.dev/include=true
```

Fix the artifact, trust policy, or controller.

## Official References

- Kubernetes namespaces: https://kubernetes.io/docs/concepts/overview/working-with-objects/namespaces/
- Kubernetes labels: https://kubernetes.io/docs/concepts/overview/working-with-objects/labels/
- Sigstore Policy Controller: https://docs.sigstore.dev/policy-controller/overview/
