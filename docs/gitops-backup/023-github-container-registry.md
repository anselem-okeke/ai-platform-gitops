# GitHub Container Registry

## Purpose

Documents GHCR publication and digest-based deployment identity.

## Registry
```text
ghcr.io/anselem-okeke/ai-platform-operator
ghcr.io/anselem-okeke/ai-platform-api
```

## Deployment Identity
```text
ghcr.io/anselem-okeke/<image>@sha256:<64-hex-digest>
```
Tags are names; digests identify exact artifact content. Promotion and rollback use digests.

## Flow
```text
build -> scan -> GHCR login -> push -> capture digest -> attest -> GitOps PR
```

Registry credentials must never be committed. If cluster pull authentication is required, deliver it through the platform secret-management path.

## Verification
```bash
kubectl get deployment ai-platform-api -n ai-platform -o jsonpath='{.spec.template.spec.containers[*].image}{"\n"}'
```

## Official References
- https://docs.github.com/packages/working-with-a-github-packages-registry/working-with-the-container-registry
- https://docs.github.com/actions/use-cases-and-examples/publishing-packages/publishing-docker-images
- https://kubernetes.io/docs/concepts/containers/images/

## Documentation Note

Commands, versions, resource names, and behavior in this document reflect the implemented AI Platform development environment. Re-validate version-specific upstream behavior before applying the same procedure to a later release or production environment.
