# Namespace Management

## Purpose

This document defines how platform namespaces and security labels are represented as GitOps-managed desired state.

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

Not every namespace is necessarily created by the same Application; the namespace GitOps component manages the platform namespaces assigned to it.

## Sigstore Enforcement Labels

Two key workload namespaces are labeled:

```text
policy.sigstore.dev/include=true
```

Applied to:

```text
ai-platform
ai-platform-operator-system
```

This opt-in label causes the Sigstore Policy Controller to enforce policy in those namespaces.

## Why Manage Labels Through Git

A namespace security label is part of the security posture.

If applied manually, it can be lost or changed without Git history.

When managed by Argo CD:

```text
Git label
  |
  v
Argo CD
  |
  v
Namespace
```

manual removal becomes detectable drift and can be repaired.

## Validation

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

Check Argo:

```bash
argocd app get ai-platform-namespaces --refresh
```

Expected:

```text
Synced
Healthy
```

## Security Considerations

Changing a namespace's policy opt-in label may alter admission enforcement.

Treat such changes as security-sensitive GitOps changes.

Do not manually remove the label to bypass admission. Fix the artifact or policy configuration instead.

## Official References

- Kubernetes namespaces: https://kubernetes.io/docs/concepts/overview/working-with-objects/namespaces/
- Kubernetes labels: https://kubernetes.io/docs/concepts/overview/working-with-objects/labels/
- Sigstore Policy Controller: https://docs.sigstore.dev/policy-controller/overview/

## Related Documentation

- [031-sigstore-policy-controller.md](031-sigstore-policy-controller.md)
- [033-image-admission-policies.md](033-image-admission-policies.md)
