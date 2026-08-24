# Kustomize Architecture

## Purpose

This document defines how reusable Kubernetes bases and environment-specific overlays are structured in the GitOps repository.

## Directory Pattern

```text
component/
├── base/
│   ├── kustomization.yaml
│   └── ...
└── overlays/
    └── dev/
        ├── kustomization.yaml
        └── ...
```

Used for:

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

A base contains configuration shared across environments.

It should avoid unnecessary environment-specific duplication.

## Overlay Responsibility

The development overlay applies environment-specific values such as:

- image digest
- namespace
- patches
- environment labels
- routing or deployment differences

## Rendered State Is Authoritative

An important implementation lesson:

Raw bases may contain placeholders:

```text
controller:latest
ai-platform-api:dev
```

These are not the final runtime image references.

The dev overlays replace them with immutable GHCR digests.

Therefore CI validates:

```bash
kubectl kustomize <overlay>
```

rather than applying the deployment-image policy to the raw base alone.

## Validation

Render each major dev overlay:

```bash
kubectl kustomize platform/operator/overlays/dev >/tmp/operator.yaml
kubectl kustomize platform/api/overlays/dev >/tmp/api.yaml
kubectl kustomize platform/gateway/overlays/dev >/tmp/gateway.yaml
kubectl kustomize platform/monitoring/overlays/dev >/tmp/monitoring.yaml
kubectl kustomize platform/policies/overlays/dev >/tmp/policies.yaml
kubectl kustomize modelservices/overlays/dev >/tmp/modelservices.yaml
```

Validate server-side where the required CRDs already exist:

```bash
kubectl apply --dry-run=server -f /tmp/monitoring.yaml
```

CI additionally uses kubeconform for schema-oriented validation.

## Image Digest Model

The operator and API overlays are updated by release automation.

The expected final image form is:

```text
ghcr.io/anselem-okeke/<image>@sha256:<64 lowercase hexadecimal characters>
```

No runtime deployment should rely on a floating tag.

## Why Kustomize

- native Kubernetes object model
- no template language required
- clear base/overlay inheritance
- environment changes remain visible as YAML
- supported directly by `kubectl`
- directly supported by Argo CD

## Troubleshooting

### Strategic merge target not found

An earlier bootstrap configuration failed because a patch expected a unique resource target that was not present in the Kustomization input.

Diagnosis:

- render the base
- verify resource group/version/kind/name/namespace
- confirm exactly one patch target exists

### Render succeeds but Argo differs

Compare:

```bash
kubectl kustomize <path>
```

with:

```bash
argocd app manifests <application>
```

and the live object.

## Official References

- Kubernetes Kustomize: https://kubernetes.io/docs/tasks/manage-kubernetes-objects/kustomization/
- Kustomize project: https://github.com/kubernetes-sigs/kustomize
- Argo CD Kustomize support: https://argo-cd.readthedocs.io/en/stable/user-guide/kustomize/

## Related Documentation

- [005-gitops-architecture.md](005-gitops-architecture.md)
- [014-operator-gitops-deployment.md](014-operator-gitops-deployment.md)
- [015-api-gitops-deployment.md](015-api-gitops-deployment.md)
