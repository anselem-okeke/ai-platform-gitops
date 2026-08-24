# GitOps Pull-Request Validation

## Purpose

Documents the `Validate GitOps` workflow and required manifest gate.

## Workflow
`.github/workflows/validate.yml` provides required check `Validate GitOps Manifests`. It uses `permissions: {}` and SHA-pinned checkout.

## Validation
It renders operator, API, gateway, monitoring, policies, modelservices, and `clusters/dev/apps`; validates with kubeconform `0.7.0`; enforces approved GHCR digest references; runs lightweight secret checks; and executes `git diff --check`.

## Important Lesson
Raw bases may contain placeholders such as `controller:latest` or `ai-platform-api:dev`. Final security policy must validate **rendered overlays**, because overlays replace those placeholders with immutable digests.

## Local Reproduction
```bash
kubectl kustomize platform/api/overlays/dev >/tmp/api.yaml
kubectl apply --dry-run=server -f /tmp/api.yaml
git diff --check
```

## Official References
- https://github.com/yannh/kubeconform
- https://kubernetes.io/docs/tasks/manage-kubernetes-objects/kustomization/
- https://docs.github.com/actions/security-for-github-actions/security-guides/security-hardening-for-github-actions

## Documentation Note

Commands, versions, resource names, and behavior in this document reflect the implemented AI Platform development environment. Re-validate version-specific upstream behavior before applying the same procedure to a later release or production environment.
