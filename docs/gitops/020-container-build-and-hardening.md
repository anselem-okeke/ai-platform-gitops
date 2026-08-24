# Container Build and Hardening

## Purpose

This document records the container build design for the AI Platform operator and API.

The final runtime images are intentionally minimal, static, and non-root.

## Repository

```text
/mnt/data/ai-platform-operator
```

## Images

```text
ghcr.io/anselem-okeke/ai-platform-operator
ghcr.io/anselem-okeke/ai-platform-api
```

## Build Architecture

```text
Go builder stage
      |
      v
compile static binary
      |
      v
distroless non-root runtime
```

## Builder Version

Validated builder:

```text
golang:1.26.6
```

Pinning the toolchain improves reproducibility and prevents unrelated builds from silently changing compiler behavior.

## Build Flags

The hardened build uses settings including:

```text
CGO_ENABLED=0
-trimpath
linker stripping flags
```

The goal is:

- static binary
- reduced build-path leakage
- reduced unnecessary binary metadata
- compatibility with distroless static runtime

## Runtime Image

Validated runtime:

```text
gcr.io/distroless/static-debian13:nonroot
```

## Runtime User

Explicit runtime identity:

```text
65532:65532
```

Dockerfile:

```dockerfile
USER 65532:65532
```

## Runtime Binaries

Operator:

```text
/manager
```

API:

```text
/platform-api
```

## Why Distroless

The runtime intentionally does not contain:

```text
shell
package manager
compiler
source tree
debugging toolchain
```

Benefits:

- smaller attack surface
- smaller image
- fewer packages to patch
- reduced post-exploitation tooling
- clearer runtime dependency boundary

## Build Cache

Build-stage cache mounts are used where appropriate.

Caches must remain in the builder layer and must not be copied into the runtime image.

## Build Validation

Build operator image using repository Makefile target where available.

Example pattern:

```bash
make docker-build
```

API build target:

```bash
make docker-build-api
```

If target names differ, use the Makefile committed in the repository.

## Local Image Inspection

```bash
docker inspect \
  <image> \
  --format '{{.Config.User}}'
```

Expected:

```text
65532:65532
```

Inspect runtime metadata:

```bash
docker inspect <image>
```

Verify no accidental shell/entrypoint dependency exists.

## Runtime Validation

Operator:

```bash
kubectl get deployment \
  ai-platform-operator-controller-manager \
  -n ai-platform-operator-system \
  -o yaml
```

API:

```bash
kubectl get deployment \
  ai-platform-api \
  -n ai-platform \
  -o yaml
```

Inspect images and securityContext.

## Image Identity

The build tag is not the deployment identity.

After GHCR push, the workflow captures:

```text
sha256:<digest>
```

GitOps deploys:

```text
<registry>/<image>@sha256:<digest>
```

## Security Considerations

### Do not add a shell just for debugging

Use:

- logs
- metrics
- ephemeral debug containers
- Kubernetes events
- temporary diagnostic workloads

rather than permanently increasing the production runtime attack surface.

### Do not run as root

Rootless runtime is a baseline security property.

### Keep builder and runtime dependencies separate

Build-time tools must not leak into runtime.

## Official References

- Docker multi-stage builds: https://docs.docker.com/build/building/multi-stage/
- Distroless: https://github.com/GoogleContainerTools/distroless
- Go build: https://pkg.go.dev/cmd/go
- Kubernetes security context: https://kubernetes.io/docs/tasks/configure-pod-container/security-context/
