# Promotion Workflow

## Purpose

Defines current dev promotion and the future multi-environment model.

## Principle
```text
Build once -> verify once -> promote the same immutable digest
```

Current environment: `dev`. Future environments may include `staging` and `prod`.

```text
source merge -> build/scan/attest -> GHCR digest -> dev GitOps PR -> human merge -> Argo
```

Future:
```text
digest X -> dev -> staging PR -> same digest X -> prod PR -> same digest X
```
Environment configuration may differ; artifact bytes should not. Promotion PRs should expose source SHA, old/new digest, image, target environment, and validation status.

## Official References
- https://opengitops.dev/
- https://argo-cd.readthedocs.io/en/stable/
- https://kubernetes.io/docs/concepts/containers/images/

## Documentation Note

Commands, versions, resource names, and behavior in this document reflect the implemented AI Platform development environment. Re-validate version-specific upstream behavior before applying the same procedure to a later release or production environment.
