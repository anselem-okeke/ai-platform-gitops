# Image Admission Policies

## Purpose

Documents native Kubernetes registry and digest enforcement.

## GitOps
Policies live under `platform/policies/` and are managed by `ai-platform-policies`.

## Requirement
Images must match:
```text
ghcr.io/anselem-okeke/<image>@sha256:<64 lowercase hex>
```

Approved prefix: `ghcr.io/anselem-okeke/`
Digest regex:
```text
^ghcr\.io/anselem-okeke/.+@sha256:[0-9a-f]{64}$
```

Native admission answers “is this reference structurally allowed?” Sigstore answers “is this exact artifact trusted?”

`nginx:latest` was denied by native policy. A malformed digest may be rejected by Kubernetes parsing even before CEL policy evaluation. A syntactically valid fake digest reaches Sigstore and is denied for missing trusted evidence.

## Official References
- https://kubernetes.io/docs/reference/access-authn-authz/validating-admission-policy/
- https://kubernetes.io/docs/reference/access-authn-authz/admission-controllers/
- https://kubernetes.io/docs/reference/using-api/cel/

## Documentation Note

Commands, versions, resource names, and behavior in this document reflect the implemented AI Platform development environment. Re-validate version-specific upstream behavior before applying the same procedure to a later release or production environment.
