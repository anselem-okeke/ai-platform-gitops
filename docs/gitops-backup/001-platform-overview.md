# AI Platform Overview

## Purpose

The AI Platform is a Kubernetes-based control plane for deploying and operating AI model workloads through a higher-level REST API and the `ModelService` custom resource.

The goal is to let application or ML engineers express model intent without manually assembling every low-level Kubernetes resource.

## User-Facing Model

Conceptually:

```text
ML Engineer
    |
    v
AI Platform REST API
    |
    v
ModelService
    |
    v
Go Operator
    |
    v
Kubernetes Resources
```

A model request may include a small set of inputs such as:

```json
{
  "name": "fraud-model",
  "image": "fraud-model:v3",
  "replicas": 2
}
```

The platform is responsible for reconciling supporting Kubernetes resources such as Deployments, Services, storage, identity, policies, and routing.

## Project Goals

- Simple model deployment interface
- Kubernetes-native reconciliation
- GitOps-controlled platform delivery
- Secure authentication and authorization
- Immutable container deployment
- CI and software supply-chain security
- Admission-time artifact trust verification
- Automated drift detection and repair
- Centralized monitoring and alerting
- Reproducible environment configuration
- Clear recovery and troubleshooting knowledge

## Kubernetes Reconciliation

`ModelService` represents desired state. The Go operator continuously compares desired and actual state.

```text
ModelService
Desired State
      |
      v
Go Operator
      |
      v
Deployment
Actual State
      |
      v
Deleted / Drift
      |
      v
Operator Reconciles
      |
      v
Deployment Restored
```

## GitOps Operating Model

The platform separates software production from deployment.

```text
Source Repository
    |
    v
CI / Release
    |
    v
GHCR immutable digest
    |
    v
GitOps PR
    |
    v
Human merge
    |
    v
Argo CD
    |
    v
Kubernetes
```

CI does not normally run `kubectl apply` against the platform cluster.

## Source-to-Cluster Security Chain

```text
Source PR
  |
  +-- Lint
  +-- Tests
  +-- E2E
  +-- govulncheck
  +-- CodeQL
  +-- Gitleaks
  |
  v
Protected main
  |
  v
Build operator/API
  |
  +-- Trivy
  +-- SBOM
  +-- GHCR
  +-- provenance/SBOM attestations
  |
  v
Immutable SHA-256 digests
  |
  v
GitHub App
  |
  v
GitOps PR
  |
  +-- Kustomize rendering
  +-- kubeconform
  +-- digest validation
  +-- secret checks
  |
  v
Human merge
  |
  v
Argo CD
  |
  v
Kubernetes Admission
  |
  +-- approved registry
  +-- mandatory digest
  +-- Sigstore attestation verification
  |
  v
Running workload
```

## Security Layers

### Source
- required PR checks
- lint/test/E2E
- govulncheck
- CodeQL
- Gitleaks

### Container
- multi-stage Go build
- distroless runtime
- non-root user
- Trivy
- immutable digest

### Supply Chain
- SBOM
- provenance
- GitHub Artifact Attestations
- Sigstore Policy Controller

### Admission
- approved GHCR organization
- full SHA-256 digest
- normal containers
- init containers
- ephemeral containers

### GitOps
- separate repository
- protected branch
- validation
- human-controlled merge
- Argo self-heal
- Git rollback

### Secrets
- credentials excluded from Git
- `.gitignore` protections
- Gitleaks CI/history scanning
- Vault as the secret-management foundation

## Identity

Keycloak provides OIDC identity. Platform groups include:

```text
platform-viewer
platform-deployer
platform-admin
```

Argo CD maps identity groups into RBAC roles.

## Networking

Envoy Gateway provides controlled HTTP(S) exposure.

Development endpoints include:

```text
https://auth.ai-platform.local
https://argocd.ai-platform.local
https://api.ai-platform.local
```

Argo CD remains a `ClusterIP` service.

## Monitoring

Prometheus and Grafana provide observability. Policy Controller has:

- a `ServiceMonitor`
- a `PrometheusRule`
- target-up monitoring
- reconcile failure monitoring
- webhook certificate reconciliation monitoring

## Immutable Deployment Principle

Final deployment references use:

```text
ghcr.io/anselem-okeke/<image>@sha256:<digest>
```

This gives deterministic deployment and exact rollback identity.

## Current Environment

The implemented environment is development. Future staging/production should promote the same immutable digest rather than rebuild artifacts.

```text
Build once
Verify once
Promote the same digest
```

## Core Technologies

Kubernetes, kind, Argo CD, Kustomize, Go, Envoy Gateway, Keycloak, Vault, Prometheus, Grafana, kube-prometheus-stack, Sigstore Policy Controller, GitHub Artifact Attestations, GitHub Actions, GHCR, Trivy, Gitleaks, CodeQL, govulncheck, and kubeconform.

## Related Documentation

- [000-documentation-index.md](000-documentation-index.md)
- [002-architecture.md](002-architecture.md)
- [003-repository-architecture.md](003-repository-architecture.md)
- [004-cluster-and-environment.md](004-cluster-and-environment.md)
