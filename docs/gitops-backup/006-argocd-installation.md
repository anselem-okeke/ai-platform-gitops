# Argo CD Installation

## Purpose

This document records the Argo CD installation used by the development AI Platform and the commands used to verify the control plane.

## Implemented Version

```text
Argo CD v3.5.1
```

Namespace:

```text
argocd
```

The platform uses Argo CD as the Kubernetes GitOps reconciliation engine.

## Installation Model

Argo CD runs inside the same development Kubernetes cluster it manages.

The installation includes the standard Argo CD control-plane components, including the API/server, repository processing, controllers, and Application/ApplicationSet CRDs.

## Production Guidance

The development environment uses the installed v3.5.1 control plane.

For reproducible environments, always pin a specific Argo CD release rather than depending on a floating `stable` manifest at deployment time.

The official Argo CD installation documentation explicitly recommends pinned versions for production-grade installation.

## Namespace Verification

```bash
kubectl get namespace argocd
```

## Pod Verification

```bash
kubectl get pods -n argocd
```

All required control-plane pods should become `Running`/ready.

## Service Verification

```bash
kubectl get svc -n argocd
```

Important service:

```text
argocd-server
```

Observed service configuration:

```text
Type: ClusterIP
ClusterIP: 10.96.128.244
Ports: 80/TCP, 443/TCP
```

The service intentionally remains `ClusterIP`.

## CRD Verification

```bash
kubectl get crd | grep argoproj.io
```

Important CRDs include:

```text
applications.argoproj.io
applicationsets.argoproj.io
appprojects.argoproj.io
```

## CLI

The Argo CD CLI is installed on the administration host.

Verify:

```bash
argocd version --client
```

Use a version compatible with the server version.

## Bootstrap Access

For initial administration, the server can be reached without changing its service type:

```bash
kubectl port-forward \
  -n argocd \
  svc/argocd-server \
  8080:443
```

This keeps `argocd-server` internal while allowing bootstrap administration.

The steady-state access model is documented separately in `007-argocd-secure-access.md`.

## Application Project

The project is:

```text
ai-platform
```

Verify:

```bash
kubectl get appproject -n argocd
```

or:

```bash
argocd proj get ai-platform
```

## Applications

Verify:

```bash
argocd app list
```

Important Applications include:

```text
ai-platform-root
ai-platform-api
ai-platform-operator
ai-platform-gateway
ai-platform-monitoring
ai-platform-modelservices
ai-platform-policies
ai-platform-namespaces
policy-controller
trust-policies
```

## Health Validation

```bash
argocd app get ai-platform-root --refresh
```

For a child:

```bash
argocd app wait \
  ai-platform-monitoring \
  --sync \
  --health \
  --timeout 300
```

## Upgrade Principle

An Argo CD upgrade should be treated as a platform change:

1. review upstream release notes
2. review supported Kubernetes versions
3. pin the target version
4. render/validate manifests
5. back up critical declarative configuration
6. upgrade in development
7. verify Applications and AppProjects
8. verify OIDC/RBAC
9. verify sync and repository access
10. document the result

## Official References

- Argo CD installation: https://argo-cd.readthedocs.io/en/stable/operator-manual/installation/
- Argo CD getting started: https://argo-cd.readthedocs.io/en/stable/getting_started/
- Argo CD CLI installation: https://argo-cd.readthedocs.io/en/stable/cli_installation/
- Argo CD releases: https://github.com/argoproj/argo-cd/releases

## Related Documentation

- [005-gitops-architecture.md](005-gitops-architecture.md)
- [007-argocd-secure-access.md](007-argocd-secure-access.md)
- [010-argocd-project.md](010-argocd-project.md)
- [011-app-of-apps.md](011-app-of-apps.md)
