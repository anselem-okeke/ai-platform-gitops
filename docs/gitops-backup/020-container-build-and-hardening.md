# Container Build and Hardening

## Purpose

Documents hardened operator/API container builds.

## Images
```text
ghcr.io/anselem-okeke/ai-platform-operator
ghcr.io/anselem-okeke/ai-platform-api
```

## Build
Both images use multi-stage builds with Go `1.26.6`, `CGO_ENABLED=0`, `-trimpath`, and stripped binaries.

## Runtime
```text
gcr.io/distroless/static-debian13:nonroot
USER 65532:65532
```
Operator binary: `/manager`. API binary: `/platform-api`.

The runtime image intentionally excludes a shell, compiler, package manager, and source tree. This reduces attack surface and runtime patch burden.

## Verification
```bash
docker inspect <image> --format '{{.Config.User}}'
kubectl get deployment -A -o jsonpath='{range .items[*]}{.metadata.namespace}/{.metadata.name}{" -> "}{.spec.template.spec.containers[*].image}{"\n"}{end}'
```

Final deployment identity is an immutable registry digest.

## Official References
- https://docs.docker.com/build/building/multi-stage/
- https://github.com/GoogleContainerTools/distroless
- https://pkg.go.dev/cmd/go
- https://kubernetes.io/docs/tasks/configure-pod-container/security-context/

## Documentation Note

Commands, versions, resource names, and behavior in this document reflect the implemented AI Platform development environment. Re-validate version-specific upstream behavior before applying the same procedure to a later release or production environment.
