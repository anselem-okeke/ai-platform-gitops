# Image Digest Update Workflow

## Purpose

Documents automated release-to-GitOps promotion.

## Trigger
```yaml
on:
  push:
    branches: [main]
```

## Dependency
```yaml
update-gitops:
  needs:
    - build-operator
    - build-api
```
Both artifacts must succeed before promotion automation starts.

## Branch and Files
Branch: `automation/image-<source-sha>`

Files changed:
```text
platform/operator/overlays/dev/kustomization.yaml
platform/api/overlays/dev/kustomization.yaml
```

Commit/PR title:
```text
chore(dev): deploy images from <source-sha>
```

Expected semantic diff: exactly two digest changes.

## Flow
```text
operator digest + API digest -> GitHub App -> bot branch -> Kustomize validation -> PR -> human merge
```

## Official References
- https://docs.github.com/actions/using-workflows/workflow-syntax-for-github-actions
- https://kubernetes.io/docs/concepts/containers/images/
- https://kubectl.docs.kubernetes.io/references/kustomize/kustomization/images/

## Documentation Note

Commands, versions, resource names, and behavior in this document reflect the implemented AI Platform development environment. Re-validate version-specific upstream behavior before applying the same procedure to a later release or production environment.
