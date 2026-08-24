# Pod, Init Container, and Ephemeral Container Policy

## Purpose

Documents Pod-level hardening so alternate container paths cannot bypass image policy.

## Coverage
The Pod policy combines:
```text
containers
initContainers
ephemeralContainers
```
and matches `CREATE`, `UPDATE`, `pods`, and `pods/ephemeralcontainers`. Binding scopes enforcement to `ai-platform` and `ai-platform-operator-system` with `Deny`.

## Validated Negative Tests
- direct Pod with `nginx:latest` denied
- invalid init container with otherwise valid main image denied
- ephemeral-container dry-run patch using `nginx:latest` denied

This prevents bypassing a Deployment-focused policy through direct Pod or debug-container paths.

## Official References
- https://kubernetes.io/docs/concepts/workloads/pods/
- https://kubernetes.io/docs/concepts/workloads/pods/init-containers/
- https://kubernetes.io/docs/concepts/workloads/pods/ephemeral-containers/
- https://kubernetes.io/docs/reference/access-authn-authz/validating-admission-policy/

## Documentation Note

Commands, versions, resource names, and behavior in this document reflect the implemented AI Platform development environment. Re-validate version-specific upstream behavior before applying the same procedure to a later release or production environment.
