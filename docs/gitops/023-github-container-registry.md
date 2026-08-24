# GitHub Container Registry

## Purpose

This document describes how release images are published to GHCR and how immutable registry digests become the deployment identity.

## Registry

```text
ghcr.io
```

## Images

```text
ghcr.io/anselem-okeke/ai-platform-operator
ghcr.io/anselem-okeke/ai-platform-api
```

## Authentication

GitHub Actions authenticates to GHCR using GitHub-provided credentials and workflow permissions.

Use minimal package permissions.

Do not store Docker registry credentials in Git.

## Publish Flow

```text
build
 |
 v
Trivy
 |
 v
GHCR login
 |
 v
push
 |
 v
capture digest
 |
 v
attest
 |
 v
GitOps update
```

## Immutable Deployment

GitOps image references use:

```text
ghcr.io/anselem-okeke/ai-platform-api@sha256:<digest>
```

and:

```text
ghcr.io/anselem-okeke/ai-platform-operator@sha256:<digest>
```

## Why Tags Are Not Sufficient

A tag can be moved:

```text
v1 -> digest A
later
v1 -> digest B
```

A digest remains tied to exact content.

## Verify Live Deployment

API:

```bash
kubectl get deployment ai-platform-api \
  -n ai-platform \
  -o jsonpath='{.spec.template.spec.containers[*].image}{"\n"}'
```

Operator:

```bash
kubectl get deployment \
  ai-platform-operator-controller-manager \
  -n ai-platform-operator-system \
  -o jsonpath='{.spec.template.spec.containers[*].image}{"\n"}'
```

Expected:

```text
@sha256:
```

## Pull Authentication

If private package access is required, Kubernetes must receive registry credentials through the approved secret-management path.

Never commit:

```text
.dockerconfigjson
password
PAT
registry token
```

into Git.

## Official References

- GHCR: https://docs.github.com/packages/working-with-a-github-packages-registry/working-with-the-container-registry
- Publishing Docker images: https://docs.github.com/actions/use-cases-and-examples/publishing-packages/publishing-docker-images
- Kubernetes images: https://kubernetes.io/docs/concepts/containers/images/
